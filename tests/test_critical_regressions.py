import ast
import importlib.util
import json
import os
import sys
import tempfile
import types
import unittest
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _is_main_guard(test):
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


@contextmanager
def _stub_updater_dependencies():
    dotenv = types.ModuleType("dotenv")
    dotenv.load_dotenv = lambda: None

    entsoe = types.ModuleType("entsoe")
    entsoe.EntsoePandasClient = object

    pandas = types.ModuleType("pandas")

    matplotlib = types.ModuleType("matplotlib")
    pyplot = types.ModuleType("matplotlib.pyplot")
    matplotlib.pyplot = pyplot

    requests = types.ModuleType("requests")

    modules = {
        "dotenv": dotenv,
        "entsoe": entsoe,
        "pandas": pandas,
        "matplotlib": matplotlib,
        "matplotlib.pyplot": pyplot,
        "requests": requests,
    }
    old_modules = {name: sys.modules.get(name) for name in modules}
    sys.modules.update(modules)
    try:
        yield
    finally:
        for name, old_module in old_modules.items():
            if old_module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = old_module


def _load_updater_module():
    with _stub_updater_dependencies():
        spec = importlib.util.spec_from_file_location(
            "telegram_updater_under_test", ROOT / "TelegramUpdaterBot.py"
        )
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module


@contextmanager
def _temporary_cwd(path):
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


class _FakeIloc:
    def __init__(self, value):
        self.value = value

    def __getitem__(self, index):
        return self.value


class _FakePrices:
    empty = False

    def __init__(self, value=42.5):
        self.iloc = _FakeIloc(value)
        self.index = [datetime(2026, 6, 26, tzinfo=timezone.utc)]


class CriticalRegressionTests(unittest.TestCase):
    def test_main_guard_only_invokes_main(self):
        tree = ast.parse((ROOT / "main.py").read_text())
        guards = [node for node in tree.body if isinstance(node, ast.If) and _is_main_guard(node.test)]

        self.assertEqual(len(guards), 1)
        self.assertEqual(len(guards[0].body), 1)
        call = guards[0].body[0]
        self.assertIsInstance(call, ast.Expr)
        self.assertIsInstance(call.value, ast.Call)
        self.assertIsInstance(call.value.func, ast.Name)
        self.assertEqual(call.value.func.id, "main")

    def test_secret_and_runtime_files_are_ignored(self):
        ignored = set((ROOT / ".gitignore").read_text().splitlines())

        self.assertIn("admin.txt", ignored)
        self.assertIn("admin.local.txt", ignored)
        self.assertIn("last_price_state.json", ignored)
        self.assertIn("EnergyScraper.py", ignored)
        self.assertIn("LegacyTerminal/", ignored)

    def test_updater_load_state_treats_corrupt_state_as_missing(self):
        updater = _load_updater_module()

        with tempfile.TemporaryDirectory() as tmpdir:
            updater.STATE_PATH = Path(tmpdir) / "last_price_state.json"

            updater.STATE_PATH.write_text("{not json")
            self.assertEqual(updater.load_state(), {})

            updater.STATE_PATH.write_text("[]")
            self.assertEqual(updater.load_state(), {})

            updater.STATE_PATH.write_text(json.dumps({"price": 7, "ts": "now"}))
            self.assertEqual(updater.load_state(), {"price": 7, "ts": "now"})

    def test_updater_save_state_replaces_json_file(self):
        updater = _load_updater_module()

        with tempfile.TemporaryDirectory() as tmpdir:
            updater.STATE_PATH = Path(tmpdir) / "last_price_state.json"

            updater.save_state({"price": 1})
            updater.save_state({"price": 2})

            self.assertEqual(json.loads(updater.STATE_PATH.read_text()), {"price": 2})
            self.assertFalse(updater.STATE_PATH.with_name("last_price_state.json.tmp").exists())

    def test_updater_does_not_advance_state_when_current_chart_missing(self):
        updater = _load_updater_module()

        with tempfile.TemporaryDirectory() as tmpdir, _temporary_cwd(tmpdir):
            updater.STATE_PATH = Path(tmpdir) / "last_price_state.json"
            updater.API_KEY = "api-key"
            updater.TOKEN = "telegram-token"
            updater.CHAT_ID = "chat-id"
            Path("chart_load.png").write_text("stale chart")

            prices = _FakePrices()
            updater.fetch_energy_data = lambda *args: (prices, object(), object())
            updater.create_comprehensive_report = lambda *args: "<b>report</b>"
            updater.send_telegram = lambda *args, **kwargs: None
            updater.send_photo = lambda *args, **kwargs: None

            def generate_only_some_charts(*args):
                Path("chart_day_ahead_prices.png").write_text("fresh price chart")
                Path("chart_crossborder_flows.png").write_text("fresh flow chart")
                return True

            updater.generate_charts = generate_only_some_charts

            updater.main("AT", "CH", "DE_LU")

            self.assertFalse(Path("chart_load.png").exists())
            self.assertFalse(updater.STATE_PATH.exists())


if __name__ == "__main__":
    unittest.main()
