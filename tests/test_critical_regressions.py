import ast
import contextlib
import importlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]


class CriticalRegressionTests(unittest.TestCase):
    def test_main_entrypoint_only_calls_main(self):
        tree = ast.parse((REPO_ROOT / "main.py").read_text())
        entrypoints = [
            node for node in tree.body
            if isinstance(node, ast.If) and self._is_name_main_guard(node.test)
        ]

        self.assertEqual(len(entrypoints), 1)
        self.assertEqual(len(entrypoints[0].body), 1)
        call = entrypoints[0].body[0]
        self.assertIsInstance(call, ast.Expr)
        self.assertIsInstance(call.value, ast.Call)
        self.assertIsInstance(call.value.func, ast.Name)
        self.assertEqual(call.value.func.id, "main")

    def test_telegram_state_not_saved_after_chart_send_failure(self):
        updater = self._import_updater_with_stubs()

        with tempfile.TemporaryDirectory() as tmpdir:
            previous_cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                updater.API_KEY = "entsoe-key"
                updater.TOKEN = "telegram-secret"
                updater.CHAT_ID = "123"
                updater.STATE_PATH = Path(tmpdir) / "last_price_state.json"
                updater.fetch_energy_data = lambda *_args: (FakePrices(), FakeFrame(), FakeFrame())
                updater.create_comprehensive_report = lambda *_args: "report"
                updater.generate_charts = self._write_expected_charts
                updater.send_telegram = lambda *_args, **_kwargs: None

                def fail_second_chart(photo_path, _caption):
                    if photo_path.endswith("chart_load.png"):
                        raise RuntimeError("failed at https://api.telegram.org/bottelegram-secret/sendPhoto")

                updater.send_photo = fail_second_chart

                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    updater.main("AT", "CH", "DE_LU")

                self.assertFalse(updater.STATE_PATH.exists())
                self.assertIn("State not updated because delivery was incomplete.", output.getvalue())
                self.assertNotIn("telegram-secret", output.getvalue())
            finally:
                os.chdir(previous_cwd)

    def test_telegram_state_saved_after_complete_delivery(self):
        updater = self._import_updater_with_stubs()

        with tempfile.TemporaryDirectory() as tmpdir:
            previous_cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                updater.API_KEY = "entsoe-key"
                updater.TOKEN = "telegram-secret"
                updater.CHAT_ID = "123"
                updater.STATE_PATH = Path(tmpdir) / "last_price_state.json"
                updater.fetch_energy_data = lambda *_args: (FakePrices(), FakeFrame(), FakeFrame())
                updater.create_comprehensive_report = lambda *_args: "report"
                updater.generate_charts = self._write_expected_charts
                updater.send_telegram = lambda *_args, **_kwargs: None
                updater.send_photo = lambda *_args, **_kwargs: None

                with contextlib.redirect_stdout(io.StringIO()):
                    updater.main("AT", "CH", "DE_LU")

                self.assertEqual(
                    json.loads(updater.STATE_PATH.read_text()),
                    {"price": 42.0, "ts": "2026-06-25T11:00:00+00:00"},
                )
            finally:
                os.chdir(previous_cwd)

    def test_local_secret_and_state_files_are_ignored(self):
        ignore_rules = (REPO_ROOT / ".gitignore").read_text().splitlines()

        for expected_rule in ("admin.txt", "admin.local.txt", "last_price_state.json"):
            self.assertIn(expected_rule, ignore_rules)

    def _write_expected_charts(self, *_args):
        for chart_file in (
            "chart_day_ahead_prices.png",
            "chart_load.png",
            "chart_crossborder_flows.png",
        ):
            Path(chart_file).write_bytes(b"png")
        return True

    @staticmethod
    def _is_name_main_guard(test):
        return (
            isinstance(test, ast.Compare)
            and isinstance(test.left, ast.Name)
            and test.left.id == "__name__"
            and len(test.ops) == 1
            and isinstance(test.ops[0], ast.Eq)
            and len(test.comparators) == 1
            and isinstance(test.comparators[0], ast.Constant)
            and test.comparators[0].value == "__main__"
        )

    @staticmethod
    def _import_updater_with_stubs():
        for module_name in ("TelegramUpdaterBot", "dotenv", "entsoe", "matplotlib", "matplotlib.pyplot", "pandas"):
            sys.modules.pop(module_name, None)

        dotenv = types.ModuleType("dotenv")
        dotenv.load_dotenv = lambda: None
        sys.modules["dotenv"] = dotenv

        entsoe = types.ModuleType("entsoe")
        entsoe.EntsoePandasClient = object
        sys.modules["entsoe"] = entsoe

        pandas = types.ModuleType("pandas")
        sys.modules["pandas"] = pandas

        matplotlib = types.ModuleType("matplotlib")
        pyplot = types.ModuleType("matplotlib.pyplot")
        sys.modules["matplotlib"] = matplotlib
        sys.modules["matplotlib.pyplot"] = pyplot

        return importlib.import_module("TelegramUpdaterBot")


class FakeIloc:
    def __getitem__(self, _index):
        return 42.0


class FakeTimestamp:
    def isoformat(self):
        return "2026-06-25T11:00:00+00:00"


class FakePrices:
    empty = False
    iloc = FakeIloc()
    index = [FakeTimestamp()]


class FakeFrame:
    empty = False


if __name__ == "__main__":
    unittest.main()
