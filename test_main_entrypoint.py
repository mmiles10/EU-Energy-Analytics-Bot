import builtins
import contextlib
import io
import os
import runpy
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parent


class MainEntrypointTests(unittest.TestCase):
    def test_missing_api_key_exits_before_artifact_reads(self):
        fake_dotenv = types.ModuleType("dotenv")
        fake_dotenv.load_dotenv = lambda: None

        fake_entsoe = types.ModuleType("entsoe")

        def fail_client(*_args, **_kwargs):
            raise AssertionError("ENTSOE client should not be created without an API key")

        fake_entsoe.EntsoePandasClient = fail_client

        fake_pandas = types.ModuleType("pandas")

        def fail_read_csv(*_args, **_kwargs):
            raise AssertionError("main.py read CSV artifacts after main() returned")

        fake_pandas.read_csv = fail_read_csv

        fake_matplotlib = types.ModuleType("matplotlib")
        fake_matplotlib.__path__ = []
        fake_pyplot = types.ModuleType("matplotlib.pyplot")
        fake_matplotlib.pyplot = fake_pyplot

        modules = {
            "dotenv": fake_dotenv,
            "entsoe": fake_entsoe,
            "pandas": fake_pandas,
            "matplotlib": fake_matplotlib,
            "matplotlib.pyplot": fake_pyplot,
        }

        with (
            patch.dict(sys.modules, modules),
            patch.dict(os.environ, {"ENTSOE_API_KEY": ""}),
            patch.object(builtins, "input", lambda _prompt="": ""),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            runpy.run_path(str(ROOT / "main.py"), run_name="__main__")


if __name__ == "__main__":
    unittest.main()
