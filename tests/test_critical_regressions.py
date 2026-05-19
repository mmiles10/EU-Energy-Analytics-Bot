import importlib
import os
import sys
import tempfile
import types
import unittest


REPO_ROOT = os.path.dirname(os.path.dirname(__file__))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


class FakeIloc:
    def __init__(self, values):
        self.values = values

    def __getitem__(self, index):
        return self.values[index]


class FakeTimestamp:
    def __init__(self, value):
        self.value = value

    def isoformat(self):
        return self.value


class FakeSeries:
    def __init__(self, values, index=None):
        self.values = list(values)
        self.index = index or list(range(len(self.values)))
        self.iloc = FakeIloc(self.values)

    @property
    def empty(self):
        return len(self.values) == 0

    def dropna(self):
        values = []
        index = []
        for idx, value in zip(self.index, self.values):
            if value is not None:
                values.append(value)
                index.append(idx)
        return FakeSeries(values, index)

    def abs(self):
        return FakeSeries([abs(value) for value in self.values], self.index)

    def max(self):
        return max(self.values) if self.values else float("nan")

    def astype(self, _type):
        return FakeSeries([_type(value) for value in self.values], self.index)

    def tolist(self):
        return list(self.values)

    def __neg__(self):
        return FakeSeries([-value for value in self.values], self.index)


class FakeDataFrame:
    def __init__(self, values):
        self.values = values

    @property
    def empty(self):
        return False


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

    pandas = types.ModuleType("pandas")
    pandas.notna = lambda value: value == value
    sys.modules["pandas"] = pandas


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
                    return FakeSeries([])
                if (from_country, to_country) == ("DE_LU", "CH"):
                    return FakeSeries([10.0, 25.0])
                raise AssertionError("unexpected country pair")

        client = FakeClient()
        flows = main.fetch_crossborder_flows(client, "CH", "DE_LU", start=None, end=None)

        self.assertEqual(client.calls, [("CH", "DE_LU"), ("DE_LU", "CH")])
        self.assertEqual(flows.tolist(), [-10.0, -25.0])


class TelegramUpdaterStateTests(unittest.TestCase):
    def test_partial_photo_delivery_does_not_advance_state(self):
        bot = import_fresh("TelegramUpdaterBot")

        prices = FakeSeries(
            [50.0, 55.0],
            index=[
                FakeTimestamp("2026-05-19T10:00:00Z"),
                FakeTimestamp("2026-05-19T11:00:00Z"),
            ],
        )
        load = FakeDataFrame({"load": [1000.0, 1100.0]})
        flows = FakeSeries([100.0, 150.0], index=prices.index)
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
