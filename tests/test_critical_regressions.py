import importlib
import py_compile
import sys
import tempfile
import types
import unittest
from contextlib import contextmanager
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@contextmanager
def working_directory(path):
    import os

    old_cwd = Path.cwd()
    try:
        os.chdir(path)
        yield
    finally:
        os.chdir(old_cwd)


def install_import_stubs():
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
    matplotlib.pyplot = pyplot
    sys.modules["matplotlib"] = matplotlib
    sys.modules["matplotlib.pyplot"] = pyplot

    requests = types.ModuleType("requests")
    sys.modules["requests"] = requests


def import_updater():
    install_import_stubs()
    sys.modules.pop("TelegramUpdaterBot", None)
    return importlib.import_module("TelegramUpdaterBot")


class FakeIloc:
    def __init__(self, values):
        self.values = values

    def __getitem__(self, index):
        return self.values[index]


class FakeTimestamp:
    def isoformat(self):
        return "2026-05-30T10:00:00+00:00"


class FakeSeries:
    def __init__(self, values):
        self.values = values
        self.iloc = FakeIloc(values)
        self.index = [FakeTimestamp() for _ in values]

    @property
    def empty(self):
        return not self.values

    def __len__(self):
        return len(self.values)

    def mean(self):
        return sum(self.values) / len(self.values)

    def min(self):
        return min(self.values)

    def max(self):
        return max(self.values)

    def std(self):
        return 0.0


class CriticalRegressionTests(unittest.TestCase):
    def test_main_py_compiles(self):
        py_compile.compile(str(ROOT / "main.py"), doraise=True)

    def test_gitignore_protects_local_secret_and_state_files(self):
        ignored = (ROOT / ".gitignore").read_text().splitlines()
        self.assertIn("admin.txt", ignored)
        self.assertIn("admin.local.txt", ignored)
        self.assertIn("last_price_state.json", ignored)

    def test_load_state_ignores_corrupt_state_file(self):
        updater = import_updater()
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "last_price_state.json"
            state_path.write_text("{not-json")
            updater.STATE_PATH = state_path

            self.assertEqual(updater.load_state(), {})

    def test_state_not_advanced_when_chart_upload_fails(self):
        updater = import_updater()
        updater.API_KEY = "key"
        updater.TOKEN = "token"
        updater.CHAT_ID = "chat"
        prices = FakeSeries([45.0, 47.0])
        load = FakeSeries([1000.0, 1100.0])
        flows = FakeSeries([10.0, 20.0])
        sent_photos = []

        with tempfile.TemporaryDirectory() as tmpdir, working_directory(Path(tmpdir)):
            updater.STATE_PATH = Path("last_price_state.json")
            updater.fetch_energy_data = lambda *_: (prices, load, flows)
            updater.send_telegram = lambda *_args, **_kwargs: None

            def generate_charts(*_args):
                for chart_file in updater.CHART_FILES:
                    Path(chart_file).write_text("fresh")
                return list(updater.CHART_FILES)

            def send_photo(photo_path, _caption=""):
                sent_photos.append(Path(photo_path).name)
                if Path(photo_path).name == updater.LOAD_CHART:
                    raise RuntimeError("upload failed")

            updater.generate_charts = generate_charts
            updater.send_photo = send_photo

            updater.main("AT", "CH", "DE_LU")

            self.assertIn(updater.LOAD_CHART, sent_photos)
            self.assertFalse(updater.STATE_PATH.exists())

    def test_missing_fresh_chart_blocks_stale_delivery_and_state_update(self):
        updater = import_updater()
        updater.API_KEY = "key"
        updater.TOKEN = "token"
        updater.CHAT_ID = "chat"
        prices = FakeSeries([45.0, 47.0])
        load = FakeSeries([1000.0, 1100.0])
        flows = FakeSeries([10.0, 20.0])
        sent = []

        with tempfile.TemporaryDirectory() as tmpdir, working_directory(Path(tmpdir)):
            updater.STATE_PATH = Path("last_price_state.json")
            Path(updater.FLOWS_CHART).write_text("stale")
            updater.fetch_energy_data = lambda *_: (prices, load, flows)
            updater.send_telegram = lambda *_args, **_kwargs: sent.append("text")
            updater.send_photo = lambda *_args, **_kwargs: sent.append("photo")

            def generate_charts(*_args):
                Path(updater.PRICE_CHART).write_text("fresh")
                Path(updater.LOAD_CHART).write_text("fresh")
                return [updater.PRICE_CHART, updater.LOAD_CHART]

            updater.generate_charts = generate_charts

            updater.main("AT", "CH", "DE_LU")

            self.assertFalse(Path(updater.FLOWS_CHART).exists())
            self.assertEqual(sent, [])
            self.assertFalse(updater.STATE_PATH.exists())


if __name__ == "__main__":
    unittest.main()
