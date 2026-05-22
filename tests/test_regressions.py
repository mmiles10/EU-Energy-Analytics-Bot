import importlib
import os
import runpy
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]


class FakeSeries:
    def __init__(self, values):
        self.values = list(values)
        self.empty = len(self.values) == 0

    def dropna(self):
        return self

    def abs(self):
        return FakeSeries([abs(value) for value in self.values])

    def max(self):
        return max(self.values) if self.values else 0

    def astype(self, _dtype):
        return FakeSeries([float(value) for value in self.values])

    def __neg__(self):
        return FakeSeries([-value for value in self.values])


class FakeClient:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def query_crossborder_flows(self, from_country, to_country, start, end):
        self.calls.append((from_country, to_country))
        return self.responses[(from_country, to_country)]


def install_import_stubs():
    dotenv = types.ModuleType("dotenv")
    dotenv.load_dotenv = lambda *args, **kwargs: None
    sys.modules["dotenv"] = dotenv

    entsoe = types.ModuleType("entsoe")
    entsoe.EntsoePandasClient = object
    sys.modules["entsoe"] = entsoe

    pandas = types.ModuleType("pandas")
    pandas.Timestamp = types.SimpleNamespace(now=lambda tz=None: None)
    pandas.Timedelta = lambda **kwargs: None
    sys.modules["pandas"] = pandas

    pyplot = types.ModuleType("matplotlib.pyplot")
    matplotlib = types.ModuleType("matplotlib")
    matplotlib.pyplot = pyplot
    sys.modules["matplotlib"] = matplotlib
    sys.modules["matplotlib.pyplot"] = pyplot


def import_with_stubs(module_name):
    install_import_stubs()
    sys.modules.pop(module_name, None)
    return importlib.import_module(module_name)


class CriticalRegressionTests(unittest.TestCase):
    def test_main_entrypoint_returns_cleanly_without_api_key(self):
        install_import_stubs()
        with patch.dict(os.environ, {"ENTSOE_API_KEY": ""}, clear=False):
            with patch("builtins.input", return_value=""):
                runpy.run_path(str(REPO_ROOT / "main.py"), run_name="__main__")

    def test_cli_crossborder_flow_uses_reverse_direction_when_forward_is_zero(self):
        app = import_with_stubs("main")
        client = FakeClient(
            {
                ("CH", "DE_LU"): FakeSeries([0, 0]),
                ("DE_LU", "CH"): FakeSeries([10, -5]),
            }
        )

        flows = app.query_crossborder_flows_with_fallback(client, "CH", "DE_LU", "start", "end")

        self.assertEqual(client.calls, [("CH", "DE_LU"), ("DE_LU", "CH")])
        self.assertEqual(flows.values, [-10.0, 5.0])

    def test_updater_does_not_save_state_after_partial_chart_delivery_failure(self):
        bot = import_with_stubs("TelegramUpdaterBot")
        saved_states = []

        class FakePrices:
            iloc = {-1: 42.0}
            index = [types.SimpleNamespace(isoformat=lambda: "2026-05-22T11:00:00+00:00")]

            @property
            def empty(self):
                return False

        with tempfile.TemporaryDirectory() as tmpdir:
            old_cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                Path("chart_day_ahead_prices.png").write_bytes(b"price")
                Path("chart_load.png").write_bytes(b"load")

                bot.API_KEY = "api-key"
                bot.TOKEN = "token"
                bot.CHAT_ID = "chat"
                bot.fetch_energy_data = lambda *args: (FakePrices(), object(), object())
                bot.create_comprehensive_report = lambda *args: "report"
                bot.load_state = lambda: {}
                bot.save_state = saved_states.append
                bot.generate_charts = lambda *args: [
                    Path("chart_day_ahead_prices.png"),
                    Path("chart_load.png"),
                ]
                bot.send_telegram = lambda *args, **kwargs: None

                def send_photo(path, caption):
                    if path == "chart_load.png":
                        raise RuntimeError("telegram upload failed")

                bot.send_photo = send_photo

                bot.main("AT", "CH", "DE_LU")
            finally:
                os.chdir(old_cwd)

        self.assertEqual(saved_states, [])

    def test_updater_chart_generation_removes_stale_missing_series_charts(self):
        bot = import_with_stubs("TelegramUpdaterBot")

        class FakePlotData:
            empty = False

            def plot(self, ax):
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

        class FakePyplot:
            def subplots(self, *args, **kwargs):
                return object(), FakeAx()

            def tight_layout(self):
                pass

            def savefig(self, path, **kwargs):
                Path(path).write_bytes(b"fresh")

            def close(self):
                pass

        with tempfile.TemporaryDirectory() as tmpdir:
            old_cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                Path("chart_load.png").write_bytes(b"stale")
                bot.plt = FakePyplot()

                generated = bot.generate_charts(FakePlotData(), None, None, "AT", "CH", "DE_LU")
                self.assertEqual([path.name for path in generated], ["chart_day_ahead_prices.png"])
                self.assertFalse(Path("chart_load.png").exists())
            finally:
                os.chdir(old_cwd)


if __name__ == "__main__":
    unittest.main()
