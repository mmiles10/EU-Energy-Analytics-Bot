import ast
import importlib.util
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]


class FakeAxes:
    def set_title(self, *args, **kwargs):
        pass

    def set_ylabel(self, *args, **kwargs):
        pass

    def set_xlabel(self, *args, **kwargs):
        pass

    def grid(self, *args, **kwargs):
        pass

    def axhline(self, *args, **kwargs):
        pass

    def legend(self, *args, **kwargs):
        pass


class FakePyplot(types.ModuleType):
    def __init__(self):
        super().__init__("matplotlib.pyplot")

    def subplots(self, *args, **kwargs):
        return object(), FakeAxes()

    def tight_layout(self, *args, **kwargs):
        pass

    def savefig(self, path, *args, **kwargs):
        Path(path).write_bytes(b"fresh chart")

    def close(self, *args, **kwargs):
        pass


class FakeSeries:
    def __init__(self, empty=False):
        self.empty = empty

    def plot(self, *args, **kwargs):
        pass


class FakeIloc:
    def __getitem__(self, item):
        return 42.0


class FakePrices:
    empty = False
    iloc = FakeIloc()
    index = [datetime(2026, 1, 1, tzinfo=timezone.utc)]


@contextmanager
def chdir(path):
    previous = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


def load_updater_module():
    dotenv = types.ModuleType("dotenv")
    dotenv.load_dotenv = lambda: None

    entsoe = types.ModuleType("entsoe")
    entsoe.EntsoePandasClient = object

    pandas = types.ModuleType("pandas")

    matplotlib = types.ModuleType("matplotlib")
    pyplot = FakePyplot()
    matplotlib.pyplot = pyplot

    module_name = "TelegramUpdaterBot_under_test"
    spec = importlib.util.spec_from_file_location(module_name, ROOT / "TelegramUpdaterBot.py")
    module = importlib.util.module_from_spec(spec)

    fake_modules = {
        "dotenv": dotenv,
        "entsoe": entsoe,
        "pandas": pandas,
        "matplotlib": matplotlib,
        "matplotlib.pyplot": pyplot,
    }
    env = {
        "TELEGRAM_TOKEN": "secret-token",
        "TELEGRAM_CHAT_ID": "12345",
        "ENTSOE_API_KEY": "entsoe-key",
    }
    with mock.patch.dict(sys.modules, fake_modules), mock.patch.dict(os.environ, env, clear=False):
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
    return module


class MainEntrypointTests(unittest.TestCase):
    def test_main_entrypoint_does_not_execute_stale_chart_reads(self):
        tree = ast.parse((ROOT / "main.py").read_text())
        entrypoints = [
            node
            for node in tree.body
            if isinstance(node, ast.If)
            and isinstance(node.test, ast.Compare)
            and isinstance(node.test.left, ast.Name)
            and node.test.left.id == "__name__"
        ]

        self.assertEqual(1, len(entrypoints))
        self.assertEqual(1, len(entrypoints[0].body))
        statement = entrypoints[0].body[0]
        self.assertIsInstance(statement, ast.Expr)
        self.assertIsInstance(statement.value, ast.Call)
        self.assertIsInstance(statement.value.func, ast.Name)
        self.assertEqual("main", statement.value.func.id)


class IgnoreAndDocsTests(unittest.TestCase):
    def test_local_secret_and_state_files_are_ignored(self):
        ignore_text = (ROOT / ".gitignore").read_text()
        for entry in ("admin.txt", "admin.local.txt", "last_price_state.json"):
            self.assertIn(entry, ignore_text)

    def test_real_chat_id_is_not_tracked_in_docs(self):
        self.assertNotIn("8466265605", (ROOT / "docs" / "overview.txt").read_text())


class TelegramUpdaterTests(unittest.TestCase):
    def test_generate_charts_removes_stale_files_and_returns_only_fresh_outputs(self):
        module = load_updater_module()

        with tempfile.TemporaryDirectory() as tmpdir, chdir(tmpdir):
            Path("chart_load.png").write_bytes(b"stale load")
            Path("chart_crossborder_flows.png").write_bytes(b"stale flows")

            generated = module.generate_charts(
                prices=FakeSeries(empty=False),
                load=FakeSeries(empty=True),
                flows=FakeSeries(empty=True),
                primary_country="AT",
                from_country="CH",
                to_country="DE_LU",
            )

            self.assertEqual(["chart_day_ahead_prices.png"], generated)
            self.assertTrue(Path("chart_day_ahead_prices.png").exists())
            self.assertFalse(Path("chart_load.png").exists())
            self.assertFalse(Path("chart_crossborder_flows.png").exists())

    def test_failed_chart_delivery_does_not_advance_state(self):
        module = load_updater_module()

        sent_text = []
        saved_states = []
        module.fetch_energy_data = lambda *args: (FakePrices(), None, None)
        module.create_comprehensive_report = lambda *args: "report"
        module.load_state = lambda: {"price": 41.0, "ts": "older"}
        module.generate_charts = lambda *args: ["chart_day_ahead_prices.png"]
        module.send_telegram = lambda text, parse_mode="HTML": sent_text.append(text)
        module.send_photo = mock.Mock(side_effect=RuntimeError("upload failed"))
        module.save_state = lambda state: saved_states.append(state)

        with tempfile.TemporaryDirectory() as tmpdir, chdir(tmpdir):
            Path("chart_day_ahead_prices.png").write_bytes(b"chart")
            module.main("AT", "CH", "DE_LU")

        self.assertEqual(["report"], sent_text)
        self.assertEqual([], saved_states)

    def test_corrupt_state_file_is_ignored(self):
        module = load_updater_module()

        with tempfile.TemporaryDirectory() as tmpdir, chdir(tmpdir):
            Path("last_price_state.json").write_text("{not json")
            self.assertEqual({}, module.load_state())

    def test_telegram_error_format_redacts_bot_token(self):
        module = load_updater_module()
        response = types.SimpleNamespace(status_code=401, text="bad token secret-token")

        message = module._format_telegram_error("sendMessage", response)

        self.assertIn("[REDACTED]", message)
        self.assertNotIn("secret-token", message)


if __name__ == "__main__":
    unittest.main()
