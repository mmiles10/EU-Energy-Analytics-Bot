import importlib
import sys
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def install_import_stubs():
    dotenv = types.ModuleType("dotenv")
    dotenv.load_dotenv = lambda: None
    sys.modules["dotenv"] = dotenv

    entsoe = types.ModuleType("entsoe")
    entsoe.EntsoePandasClient = object
    sys.modules["entsoe"] = entsoe

    pandas = types.ModuleType("pandas")

    class Timestamp:
        @staticmethod
        def now(tz=None):
            return Timestamp()

        def __sub__(self, other):
            return self

        def replace(self, **kwargs):
            return self

    class Timedelta:
        def __init__(self, days=0):
            self.days = days

    pandas.Timestamp = Timestamp
    pandas.Timedelta = Timedelta
    sys.modules["pandas"] = pandas

    matplotlib = types.ModuleType("matplotlib")
    pyplot = types.ModuleType("matplotlib.pyplot")
    matplotlib.pyplot = pyplot
    sys.modules["matplotlib"] = matplotlib
    sys.modules["matplotlib.pyplot"] = pyplot

    sys.modules["requests"] = types.ModuleType("requests")


class FlowSeries:
    def __init__(self, values):
        self.values = [float(value) for value in values]

    @property
    def empty(self):
        return not self.values

    def dropna(self):
        return self

    def abs(self):
        return FlowSeries([abs(value) for value in self.values])

    def max(self):
        return max(self.values)

    def astype(self, _dtype):
        return FlowSeries(self.values)

    def __neg__(self):
        return FlowSeries([-value for value in self.values])


class PriceSeries:
    def __init__(self, values):
        self.values = list(values)

    def dropna(self):
        return self


class FetchEnergyDataTests(unittest.TestCase):
    def setUp(self):
        install_import_stubs()
        sys.modules.pop("TelegramUpdaterBot", None)
        self.bot = importlib.import_module("TelegramUpdaterBot")
        self.bot.API_KEY = "test-key"
        self.calls = []

    def test_forward_no_data_error_uses_reverse_and_keeps_prices(self):
        prices = PriceSeries([40.0, 55.0])
        load = object()
        reverse = FlowSeries([100.0, 80.0])

        class Client:
            def query_day_ahead_prices(self, country, start, end):
                return prices

            def query_load(self, country, start, end):
                return load

            def query_crossborder_flows(self, origin, dest, start, end):
                self_calls.append((origin, dest))
                if (origin, dest) == ("CH", "DE_LU"):
                    raise RuntimeError("No matching data found")
                return reverse

        self_calls = self.calls
        self.bot.client = Client()

        fetched_prices, fetched_load, flows = self.bot.fetch_energy_data("AT", "CH", "DE_LU")

        self.assertIs(fetched_prices, prices)
        self.assertIs(fetched_load, load)
        self.assertEqual(flows.values, [-100.0, -80.0])
        self.assertEqual(self.calls, [("CH", "DE_LU"), ("DE_LU", "CH")])

    def test_load_and_both_flow_directions_failing_still_returns_prices(self):
        prices = PriceSeries([42.0])

        class Client:
            def query_day_ahead_prices(self, country, start, end):
                return prices

            def query_load(self, country, start, end):
                raise RuntimeError("No matching data found")

            def query_crossborder_flows(self, origin, dest, start, end):
                raise RuntimeError("No matching data found")

        self.bot.client = Client()

        fetched_prices, load, flows = self.bot.fetch_energy_data("AT", "CH", "DE_LU")

        self.assertIs(fetched_prices, prices)
        self.assertIsNone(load)
        self.assertIsNone(flows)

    def test_all_zero_forward_series_uses_reverse(self):
        prices = PriceSeries([42.0])
        reverse = FlowSeries([15.0])

        class Client:
            def query_day_ahead_prices(self, country, start, end):
                return prices

            def query_load(self, country, start, end):
                return object()

            def query_crossborder_flows(self, origin, dest, start, end):
                if origin == "CH":
                    return FlowSeries([0.0, 0.0])
                return reverse

        self.bot.client = Client()

        _prices, _load, flows = self.bot.fetch_energy_data("AT", "CH", "DE_LU")

        self.assertEqual(flows.values, [-15.0])

    def test_published_forward_series_does_not_query_reverse(self):
        prices = PriceSeries([42.0])
        forward = FlowSeries([25.0, -5.0])

        class Client:
            def query_day_ahead_prices(self, country, start, end):
                return prices

            def query_load(self, country, start, end):
                return object()

            def query_crossborder_flows(self, origin, dest, start, end):
                self_calls.append((origin, dest))
                return forward

        self_calls = self.calls
        self.bot.client = Client()

        _prices, _load, flows = self.bot.fetch_energy_data("AT", "CH", "DE_LU")

        self.assertEqual(flows.values, [25.0, -5.0])
        self.assertEqual(self.calls, [("CH", "DE_LU")])

    def test_price_failure_still_returns_no_data(self):
        class Client:
            def query_day_ahead_prices(self, country, start, end):
                raise RuntimeError("prices unavailable")

            def query_load(self, country, start, end):
                raise AssertionError("load should not be queried")

            def query_crossborder_flows(self, origin, dest, start, end):
                raise AssertionError("flows should not be queried")

        self.bot.client = Client()

        self.assertEqual(self.bot.fetch_energy_data("AT", "CH", "DE_LU"), (None, None, None))


if __name__ == "__main__":
    unittest.main()
