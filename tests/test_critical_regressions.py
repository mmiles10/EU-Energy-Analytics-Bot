import ast
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from contextlib import contextmanager
from datetime import datetime, timezone


REPO_ROOT = Path(__file__).resolve().parents[1]


class FakeSeries:
    empty = False

    def __init__(self, value=42.0):
        self._value = value
        self.index = [datetime(2026, 1, 1, tzinfo=timezone.utc)]

    @property
    def iloc(self):
        return self

    def __getitem__(self, index):
        return self._value


class FakeDataset:
    def __init__(self, empty=False):
        self.empty = empty


@contextmanager
def chdir(path):
    previous = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


def load_updater_module():
    stubs = {
        "dotenv": types.ModuleType("dotenv"),
        "entsoe": types.ModuleType("entsoe"),
        "pandas": types.ModuleType("pandas"),
        "requests": types.ModuleType("requests"),
        "matplotlib": types.ModuleType("matplotlib"),
        "matplotlib.pyplot": types.ModuleType("matplotlib.pyplot"),
    }
    stubs["dotenv"].load_dotenv = lambda: None
    stubs["entsoe"].EntsoePandasClient = object
    stubs["matplotlib"].__path__ = []

    previous_modules = {name: sys.modules.get(name) for name in stubs}
    sys.modules.update(stubs)
    module_name = f"_telegram_updater_under_test_{id(stubs)}"
    try:
        spec = importlib.util.spec_from_file_location(
            module_name, REPO_ROOT / "TelegramUpdaterBot.py"
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module
    finally:
        for name, previous in previous_modules.items():
            if previous is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous


class CriticalRegressionTests(unittest.TestCase):
    def test_main_entrypoint_has_no_extra_chart_side_effects(self):
        tree = ast.parse((REPO_ROOT / "main.py").read_text())
        entrypoints = [
            node
            for node in tree.body
            if isinstance(node, ast.If)
            and isinstance(node.test, ast.Compare)
            and isinstance(node.test.left, ast.Name)
            and node.test.left.id == "__name__"
        ]

        self.assertEqual(len(entrypoints), 1)
        self.assertEqual(len(entrypoints[0].body), 1)
        statement = entrypoints[0].body[0]
        self.assertIsInstance(statement, ast.Expr)
        self.assertIsInstance(statement.value, ast.Call)
        self.assertIsInstance(statement.value.func, ast.Name)
        self.assertEqual(statement.value.func.id, "main")

    def test_gitignore_protects_local_secrets_and_runtime_state(self):
        ignored = set((REPO_ROOT / ".gitignore").read_text().splitlines())

        self.assertIn("admin.txt", ignored)
        self.assertIn("admin.local.txt", ignored)
        self.assertIn("last_price_state.json", ignored)

    def test_corrupt_updater_state_is_ignored(self):
        module = load_updater_module()

        with tempfile.TemporaryDirectory() as temp_dir:
            module.STATE_PATH = Path(temp_dir) / "last_price_state.json"
            module.STATE_PATH.write_text("{not json")

            self.assertEqual(module.load_state(), {})

    def test_failed_chart_delivery_does_not_advance_state(self):
        module = load_updater_module()

        with tempfile.TemporaryDirectory() as temp_dir, chdir(temp_dir):
            module.STATE_PATH = Path(temp_dir) / "last_price_state.json"
            module.API_KEY = "api-key"
            module.TOKEN = "token"
            module.CHAT_ID = "chat"
            module.fetch_energy_data = lambda *args: (
                FakeSeries(),
                FakeDataset(),
                FakeDataset(),
            )
            module.create_comprehensive_report = lambda *args: "report"

            def generate_charts(*args):
                for chart_path in module.CHART_FILES.values():
                    chart_path.write_text("current")
                return True

            module.generate_charts = generate_charts
            module.send_telegram = lambda *args, **kwargs: None

            def fail_load_photo(path, caption=""):
                if path.endswith("chart_load.png"):
                    raise RuntimeError("send failed")

            module.send_photo = fail_load_photo

            module.main("AT", "CH", "DE_LU")

            self.assertFalse(module.STATE_PATH.exists())

    def test_stale_charts_are_removed_before_sending_current_report(self):
        module = load_updater_module()

        with tempfile.TemporaryDirectory() as temp_dir, chdir(temp_dir):
            module.STATE_PATH = Path(temp_dir) / "last_price_state.json"
            module.API_KEY = "api-key"
            module.TOKEN = "token"
            module.CHAT_ID = "chat"
            Path("chart_load.png").write_text("stale")
            module.fetch_energy_data = lambda *args: (
                FakeSeries(),
                FakeDataset(empty=True),
                FakeDataset(empty=True),
            )
            module.create_comprehensive_report = lambda *args: "report"
            module.generate_charts = lambda *args: (
                Path("chart_day_ahead_prices.png").write_text("current") or True
            )
            module.send_telegram = lambda *args, **kwargs: None
            sent_photos = []
            module.send_photo = lambda path, caption="": sent_photos.append(path)

            module.main("AT", "CH", "DE_LU")

            self.assertEqual(sent_photos, ["chart_day_ahead_prices.png"])
            self.assertFalse(Path("chart_load.png").exists())
            self.assertTrue(module.STATE_PATH.exists())


if __name__ == "__main__":
    unittest.main()
