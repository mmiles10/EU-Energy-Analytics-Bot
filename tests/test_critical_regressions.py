import contextlib
import importlib.util
import os
import py_compile
import sys
import tempfile
import types
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]


@contextlib.contextmanager
def temporary_cwd(path):
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


@contextlib.contextmanager
def stub_import_dependencies():
    module_names = [
        "dotenv",
        "entsoe",
        "matplotlib",
        "matplotlib.pyplot",
        "pandas",
        "requests",
    ]
    previous_modules = {name: sys.modules.get(name) for name in module_names}

    dotenv = types.ModuleType("dotenv")
    dotenv.load_dotenv = lambda: None

    entsoe = types.ModuleType("entsoe")

    class EntsoePandasClient:
        def __init__(self, api_key):
            self.api_key = api_key

    entsoe.EntsoePandasClient = EntsoePandasClient

    matplotlib = types.ModuleType("matplotlib")
    pyplot = types.ModuleType("matplotlib.pyplot")
    pandas = types.ModuleType("pandas")
    requests = types.ModuleType("requests")

    sys.modules.update(
        {
            "dotenv": dotenv,
            "entsoe": entsoe,
            "matplotlib": matplotlib,
            "matplotlib.pyplot": pyplot,
            "pandas": pandas,
            "requests": requests,
        }
    )

    try:
        yield
    finally:
        for name, module in previous_modules.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module


def load_updater_module():
    module_name = "TelegramUpdaterBot_under_test"
    sys.modules.pop(module_name, None)

    with stub_import_dependencies(), mock.patch.dict(
        os.environ,
        {
            "ENTSOE_API_KEY": "test-entsoe-key",
            "TELEGRAM_TOKEN": "test-telegram-token",
            "TELEGRAM_CHAT_ID": "12345",
        },
    ):
        spec = importlib.util.spec_from_file_location(
            module_name, REPO_ROOT / "TelegramUpdaterBot.py"
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module


class FakeIloc:
    def __getitem__(self, index):
        return 42.0


class FakeIndex:
    def __getitem__(self, index):
        return datetime(2026, 5, 28, 10, 0, tzinfo=timezone.utc)


class FakePrices:
    empty = False
    iloc = FakeIloc()
    index = FakeIndex()

    def plot(self, ax=None):
        return ax


class FakeAx:
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


class FakePlot:
    def subplots(self, *args, **kwargs):
        return object(), FakeAx()

    def tight_layout(self):
        pass

    def savefig(self, path, *args, **kwargs):
        Path(path).write_bytes(b"current-chart")

    def close(self):
        pass


class CriticalRegressionTests(unittest.TestCase):
    def test_main_script_compiles(self):
        py_compile.compile(str(REPO_ROOT / "main.py"), doraise=True)

    def test_corrupt_state_file_does_not_crash_updater(self):
        updater = load_updater_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            updater.STATE_PATH = Path(tmpdir) / "last_price_state.json"
            updater.STATE_PATH.write_text("{not json")

            self.assertEqual({}, updater.load_state())

    def test_chart_upload_failure_does_not_advance_state(self):
        updater = load_updater_module()
        sent_messages = []

        with tempfile.TemporaryDirectory() as tmpdir:
            updater.STATE_PATH = Path(tmpdir) / "last_price_state.json"
            updater.fetch_energy_data = lambda *args: (FakePrices(), object(), object())
            updater.create_comprehensive_report = lambda *args: "<b>report</b>"
            updater.generate_charts = lambda *args: ["chart_day_ahead_prices.png"]
            updater.send_telegram = lambda message, parse_mode="HTML": sent_messages.append(message)

            def fail_photo(*args, **kwargs):
                raise RuntimeError("network failed")

            updater.send_photo = fail_photo

            updater.main("AT", "CH", "DE_LU")

            self.assertEqual(["<b>report</b>"], sent_messages)
            self.assertFalse(updater.STATE_PATH.exists())

    def test_stale_charts_are_removed_before_generating_current_charts(self):
        updater = load_updater_module()
        updater.plt = FakePlot()

        with tempfile.TemporaryDirectory() as tmpdir, temporary_cwd(tmpdir):
            Path("chart_load.png").write_bytes(b"old-load")
            Path("chart_crossborder_flows.png").write_bytes(b"old-flows")

            generated = updater.generate_charts(FakePrices(), None, None, "AT", "CH", "DE_LU")

            self.assertEqual(["chart_day_ahead_prices.png"], generated)
            self.assertTrue(Path("chart_day_ahead_prices.png").exists())
            self.assertFalse(Path("chart_load.png").exists())
            self.assertFalse(Path("chart_crossborder_flows.png").exists())


if __name__ == "__main__":
    unittest.main()
