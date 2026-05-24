import importlib
import json
import py_compile
import sys
import tempfile
import types
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def install_import_stubs():
    """Provide lightweight stubs for optional runtime dependencies."""
    entsoe = types.ModuleType("entsoe")

    class FakeEntsoePandasClient:
        def __init__(self, *args, **kwargs):
            pass

    entsoe.EntsoePandasClient = FakeEntsoePandasClient
    sys.modules.setdefault("entsoe", entsoe)

    dotenv = types.ModuleType("dotenv")
    dotenv.load_dotenv = lambda *args, **kwargs: None
    sys.modules.setdefault("dotenv", dotenv)

    pandas = types.ModuleType("pandas")
    sys.modules.setdefault("pandas", pandas)

    matplotlib = types.ModuleType("matplotlib")
    pyplot = types.ModuleType("matplotlib.pyplot")
    matplotlib.pyplot = pyplot
    sys.modules.setdefault("matplotlib", matplotlib)
    sys.modules.setdefault("matplotlib.pyplot", pyplot)


class MainEntrypointTests(unittest.TestCase):
    def test_main_py_compiles(self):
        py_compile.compile(str(REPO_ROOT / "main.py"), doraise=True)


class TelegramUpdaterStateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        install_import_stubs()
        sys.modules.pop("TelegramUpdaterBot", None)
        cls.bot = importlib.import_module("TelegramUpdaterBot")

    def test_corrupt_state_file_is_ignored(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            old_state_path = self.bot.STATE_PATH
            self.bot.STATE_PATH = Path(tmpdir) / "last_price_state.json"
            try:
                self.bot.STATE_PATH.write_text("{")

                self.assertEqual({}, self.bot.load_state())
            finally:
                self.bot.STATE_PATH = old_state_path

    def test_state_is_written_as_valid_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            old_state_path = self.bot.STATE_PATH
            self.bot.STATE_PATH = Path(tmpdir) / "last_price_state.json"
            try:
                state = {"price": 42.5, "ts": "2026-05-24T10:00:00+00:00"}

                self.bot.save_state(state)

                self.assertEqual(state, json.loads(self.bot.STATE_PATH.read_text()))
                self.assertFalse((Path(tmpdir) / ".last_price_state.json.tmp").exists())
            finally:
                self.bot.STATE_PATH = old_state_path


if __name__ == "__main__":
    unittest.main()
