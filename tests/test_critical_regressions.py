import ast
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]


class CriticalRegressionTests(unittest.TestCase):
    def test_main_guard_only_invokes_main(self):
        tree = ast.parse((REPO_ROOT / "main.py").read_text())
        main_guards = [
            node
            for node in tree.body
            if isinstance(node, ast.If)
            and isinstance(node.test, ast.Compare)
            and isinstance(node.test.left, ast.Name)
            and node.test.left.id == "__name__"
        ]

        self.assertEqual(len(main_guards), 1)
        guard_body = main_guards[0].body
        self.assertEqual(len(guard_body), 1)
        self.assertIsInstance(guard_body[0], ast.Expr)
        call = guard_body[0].value
        self.assertIsInstance(call, ast.Call)
        self.assertIsInstance(call.func, ast.Name)
        self.assertEqual(call.func.id, "main")

    def test_main_without_api_key_does_not_fall_through_to_csv_reads(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            stub_dir = temp_path / "stubs"
            (stub_dir / "matplotlib").mkdir(parents=True)
            (stub_dir / "dotenv.py").write_text("def load_dotenv():\n    return None\n")
            (stub_dir / "entsoe.py").write_text("class EntsoePandasClient:\n    pass\n")
            (stub_dir / "pandas.py").write_text(
                "def read_csv(*args, **kwargs):\n"
                "    raise FileNotFoundError(args[0])\n"
            )
            (stub_dir / "matplotlib" / "__init__.py").write_text("")
            (stub_dir / "matplotlib" / "pyplot.py").write_text("")

            env = os.environ.copy()
            env.pop("ENTSOE_API_KEY", None)
            env["PYTHONPATH"] = os.pathsep.join(
                [str(stub_dir), str(REPO_ROOT), env.get("PYTHONPATH", "")]
            )

            result = subprocess.run(
                [sys.executable, str(REPO_ROOT / "main.py")],
                input="\n\n\n",
                cwd=temp_path,
                env=env,
                text=True,
                capture_output=True,
                timeout=10,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Error: ENTSOE_API_KEY not set in environment", result.stdout)
        self.assertNotIn("day_ahead_prices.csv", result.stderr)

    def test_local_secret_and_state_files_are_ignored(self):
        ignored_entries = set((REPO_ROOT / ".gitignore").read_text().splitlines())
        self.assertTrue(
            {"admin.txt", "admin.local.txt", "last_price_state.json"}.issubset(
                ignored_entries
            )
        )

    def test_updater_ignores_corrupt_state_and_saves_atomically(self):
        bot = self._import_updater_with_stubbed_dependencies()

        with tempfile.TemporaryDirectory() as temp_dir:
            bot.STATE_PATH = Path(temp_dir) / "last_price_state.json"
            bot.STATE_PATH.write_text("{")

            self.assertEqual(bot.load_state(), {})

            bot.save_state({"price": 1.23, "ts": "2026-06-09T11:00:00+00:00"})

            self.assertEqual(
                json.loads(bot.STATE_PATH.read_text()),
                {"price": 1.23, "ts": "2026-06-09T11:00:00+00:00"},
            )
            self.assertFalse(bot.STATE_PATH.with_suffix(".json.tmp").exists())

    def test_updater_does_not_advance_state_when_expected_chart_is_missing(self):
        bot = self._import_updater_with_stubbed_dependencies()

        class FakePrices:
            empty = False
            iloc = [42.0]
            index = [_Timestamp("2026-06-09T11:00:00+00:00")]

        with tempfile.TemporaryDirectory() as temp_dir:
            previous_cwd = os.getcwd()
            os.chdir(temp_dir)
            try:
                bot.STATE_PATH = Path(temp_dir) / "last_price_state.json"
                bot.API_KEY = "entsoe-key"
                bot.TOKEN = "telegram-token"
                bot.CHAT_ID = "chat-id"
                sent_reports = []

                bot.fetch_energy_data = lambda *args: (FakePrices(), None, None)
                bot.create_comprehensive_report = lambda *args: "report"
                bot.generate_charts = lambda *args: True
                bot.send_telegram = lambda text, parse_mode="HTML": sent_reports.append(text)
                bot.send_photo = lambda *args: self.fail("missing chart should not be sent")

                bot.main("AT", "CH", "DE_LU")
            finally:
                os.chdir(previous_cwd)

        self.assertEqual(sent_reports, ["report"])
        self.assertFalse(bot.STATE_PATH.exists())

    def _import_updater_with_stubbed_dependencies(self):
        for module_name in [
            "TelegramUpdaterBot",
            "dotenv",
            "entsoe",
            "matplotlib",
            "matplotlib.pyplot",
            "pandas",
            "requests",
        ]:
            sys.modules.pop(module_name, None)

        dotenv = types.ModuleType("dotenv")
        dotenv.load_dotenv = lambda: None

        entsoe = types.ModuleType("entsoe")
        entsoe.EntsoePandasClient = type("EntsoePandasClient", (), {})

        matplotlib = types.ModuleType("matplotlib")
        matplotlib.__path__ = []
        pyplot = types.ModuleType("matplotlib.pyplot")

        pandas = types.ModuleType("pandas")
        requests = types.ModuleType("requests")

        sys.modules["dotenv"] = dotenv
        sys.modules["entsoe"] = entsoe
        sys.modules["matplotlib"] = matplotlib
        sys.modules["matplotlib.pyplot"] = pyplot
        sys.modules["pandas"] = pandas
        sys.modules["requests"] = requests

        return importlib.import_module("TelegramUpdaterBot")


class _Timestamp:
    def __init__(self, value):
        self.value = value

    def isoformat(self):
        return self.value


if __name__ == "__main__":
    unittest.main()
