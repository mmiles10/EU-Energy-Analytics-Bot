import ast
from contextlib import contextmanager
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]


@contextmanager
def load_updater_module():
    saved_modules = {
        name: sys.modules.get(name)
        for name in ("dotenv", "entsoe", "pandas", "matplotlib", "matplotlib.pyplot", "requests")
    }

    dotenv = types.ModuleType("dotenv")
    dotenv.load_dotenv = lambda: None

    entsoe = types.ModuleType("entsoe")
    entsoe.EntsoePandasClient = lambda api_key: None

    pandas = types.ModuleType("pandas")

    matplotlib = types.ModuleType("matplotlib")
    pyplot = types.ModuleType("matplotlib.pyplot")
    matplotlib.pyplot = pyplot

    requests = types.ModuleType("requests")

    class HTTPError(Exception):
        pass

    requests.HTTPError = HTTPError

    sys.modules.update(
        {
            "dotenv": dotenv,
            "entsoe": entsoe,
            "pandas": pandas,
            "matplotlib": matplotlib,
            "matplotlib.pyplot": pyplot,
            "requests": requests,
        }
    )

    module_name = "_telegram_updater_under_test"
    spec = importlib.util.spec_from_file_location(module_name, REPO_ROOT / "TelegramUpdaterBot.py")
    module = importlib.util.module_from_spec(spec)
    try:
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        yield module
    finally:
        sys.modules.pop(module_name, None)
        for name, saved_module in saved_modules.items():
            if saved_module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = saved_module


class MainEntrypointTests(unittest.TestCase):
    def test_main_guard_only_calls_main(self):
        tree = ast.parse((REPO_ROOT / "main.py").read_text())

        main_guards = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.If)
            and isinstance(node.test, ast.Compare)
            and isinstance(node.test.left, ast.Name)
            and node.test.left.id == "__name__"
        ]

        self.assertEqual(len(main_guards), 1)
        guard_body = main_guards[0].body
        self.assertEqual(len(guard_body), 1)
        call = guard_body[0]
        self.assertIsInstance(call, ast.Expr)
        self.assertIsInstance(call.value, ast.Call)
        self.assertIsInstance(call.value.func, ast.Name)
        self.assertEqual(call.value.func.id, "main")


class GitignoreTests(unittest.TestCase):
    def test_local_secret_and_state_files_are_ignored(self):
        ignored = {
            line.strip()
            for line in (REPO_ROOT / ".gitignore").read_text().splitlines()
            if line.strip() and not line.startswith("#")
        }

        self.assertIn("admin.txt", ignored)
        self.assertIn("admin.local.txt", ignored)
        self.assertIn("last_price_state.json", ignored)
        self.assertIn("last_price_state.json.tmp", ignored)


class TelegramUpdaterStateTests(unittest.TestCase):
    def test_corrupt_state_is_ignored_and_state_write_is_atomic(self):
        with load_updater_module() as updater, tempfile.TemporaryDirectory() as tmpdir:
            updater.STATE_PATH = Path(tmpdir) / "last_price_state.json"
            updater.STATE_PATH.write_text("{")

            self.assertEqual(updater.load_state(), {})

            updater.save_state({"price": 42.5, "ts": "2026-07-10T11:00:00+00:00"})

            self.assertEqual(
                updater.load_state(),
                {"price": 42.5, "ts": "2026-07-10T11:00:00+00:00"},
            )
            self.assertFalse((Path(tmpdir) / "last_price_state.json.tmp").exists())

    def test_telegram_http_error_does_not_expose_bot_token(self):
        with load_updater_module() as updater:
            updater.TOKEN = "super-secret-token"
            updater.CHAT_ID = "12345"

            class Response:
                status_code = 401
                text = '{"ok":false,"description":"Unauthorized"}'

                def raise_for_status(self):
                    raise updater.requests.HTTPError(
                        "401 Client Error: Unauthorized for url: "
                        "https://api.telegram.org/botsuper-secret-token/sendMessage"
                    )

            updater.requests.post = lambda *args, **kwargs: Response()

            with self.assertRaises(RuntimeError) as raised:
                updater.send_telegram("hello")

            self.assertIn("401", str(raised.exception))
            self.assertNotIn("super-secret-token", str(raised.exception))

    def test_chart_delivery_failure_does_not_advance_state(self):
        class FakeIloc:
            def __getitem__(self, _index):
                return 50.0

        class FakePrices:
            empty = False
            iloc = FakeIloc()
            index = ["2026-07-10T11:00:00+00:00"]

        with load_updater_module() as updater, tempfile.TemporaryDirectory() as tmpdir:
            previous_cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                updater.API_KEY = "entsoe-key"
                updater.TOKEN = "telegram-token"
                updater.CHAT_ID = "12345"
                updater.STATE_PATH = Path(tmpdir) / "last_price_state.json"
                updater.fetch_energy_data = lambda *args: (FakePrices(), None, None)
                updater.create_comprehensive_report = lambda *args: "report"

                def generate_chart(*_args):
                    Path("chart_day_ahead_prices.png").write_text("chart")
                    return True

                updater.generate_charts = generate_chart
                updater.send_telegram = lambda *args, **kwargs: None
                updater.send_photo = lambda *args, **kwargs: (_ for _ in ()).throw(
                    RuntimeError("photo upload failed")
                )

                with self.assertRaises(RuntimeError):
                    updater.main("AT", "CH", "DE_LU")

                self.assertFalse(updater.STATE_PATH.exists())
            finally:
                os.chdir(previous_cwd)


if __name__ == "__main__":
    unittest.main()
