import importlib
import os
import sys
import tempfile
import types
import unittest

import pandas as pd


def stub_optional_modules():
    entsoe = types.ModuleType("entsoe")
    entsoe.EntsoePandasClient = object
    sys.modules["entsoe"] = entsoe

    dotenv = types.ModuleType("dotenv")
    dotenv.load_dotenv = lambda: None
    sys.modules["dotenv"] = dotenv

    if "matplotlib" not in sys.modules:
        sys.modules["matplotlib"] = types.ModuleType("matplotlib")
    if "matplotlib.pyplot" not in sys.modules:
        sys.modules["matplotlib.pyplot"] = types.ModuleType("matplotlib.pyplot")


def import_fresh(module_name):
    stub_optional_modules()
    sys.modules.pop(module_name, None)
    return importlib.import_module(module_name)


class CrossborderFlowFallbackTests(unittest.TestCase):
    def test_fetch_crossborder_flows_uses_negated_reverse_when_direct_is_empty(self):
        main = import_fresh("main")

        class FakeClient:
            def __init__(self):
                self.calls = []

            def query_crossborder_flows(self, from_country, to_country, start, end):
                self.calls.append((from_country, to_country))
                if (from_country, to_country) == ("CH", "DE_LU"):
                    return pd.Series([], dtype=float)
                if (from_country, to_country) == ("DE_LU", "CH"):
                    return pd.Series([10.0, 25.0])
                raise AssertionError("unexpected country pair")

        client = FakeClient()
        flows = main.fetch_crossborder_flows(client, "CH", "DE_LU", start=None, end=None)

        self.assertEqual(client.calls, [("CH", "DE_LU"), ("DE_LU", "CH")])
        self.assertEqual(flows.tolist(), [-10.0, -25.0])


class TelegramUpdaterStateTests(unittest.TestCase):
    def test_partial_photo_delivery_does_not_advance_state(self):
        bot = import_fresh("TelegramUpdaterBot")

        prices = pd.Series(
            [50.0, 55.0],
            index=pd.to_datetime(["2026-05-19T10:00:00Z", "2026-05-19T11:00:00Z"]),
        )
        load = pd.DataFrame({"load": [1000.0, 1100.0]}, index=prices.index)
        flows = pd.Series([100.0, 150.0], index=prices.index)
        saved_states = []

        bot.TOKEN = "token"
        bot.CHAT_ID = "chat"
        bot.API_KEY = "key"
        bot.load_state = lambda: {}
        bot.fetch_energy_data = lambda *args: (prices, load, flows)
        bot.create_comprehensive_report = lambda *args: "report"
        bot.generate_charts = lambda *args: True
        bot.send_telegram = lambda *args, **kwargs: None
        bot.save_state = saved_states.append

        def fail_photo(*args, **kwargs):
            raise RuntimeError("telegram timeout")

        bot.send_photo = fail_photo

        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                os.chdir(tmpdir)
                for chart_file in [
                    "chart_day_ahead_prices.png",
                    "chart_load.png",
                    "chart_crossborder_flows.png",
                ]:
                    open(chart_file, "wb").close()

                bot.main("AT", "CH", "DE_LU")
            finally:
                os.chdir(cwd)

        self.assertEqual(saved_states, [])


if __name__ == "__main__":
    unittest.main()
