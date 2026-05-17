import builtins
import os
import runpy
import sys
import types
import unittest
from contextlib import contextmanager
from unittest import mock


@contextmanager
def stub_module(name, module):
    original = sys.modules.get(name)
    sys.modules[name] = module
    try:
        yield
    finally:
        if original is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = original


class MainEntrypointTest(unittest.TestCase):
    def test_missing_entsoe_key_exits_without_reading_csvs(self):
        pandas_stub = types.SimpleNamespace(
            read_csv=mock.Mock(side_effect=AssertionError("CSV files should not be read"))
        )
        pyplot_stub = types.SimpleNamespace()
        matplotlib_stub = types.ModuleType("matplotlib")

        with mock.patch.dict(os.environ, {"ENTSOE_API_KEY": ""}, clear=False), \
                mock.patch.object(builtins, "input", lambda prompt="": ""), \
                stub_module("dotenv", types.SimpleNamespace(load_dotenv=lambda: None)), \
                stub_module("entsoe", types.SimpleNamespace(EntsoePandasClient=mock.Mock())), \
                stub_module("pandas", pandas_stub), \
                stub_module("matplotlib", matplotlib_stub), \
                stub_module("matplotlib.pyplot", pyplot_stub):
            runpy.run_path("main.py", run_name="__main__")

        pandas_stub.read_csv.assert_not_called()


if __name__ == "__main__":
    unittest.main()
