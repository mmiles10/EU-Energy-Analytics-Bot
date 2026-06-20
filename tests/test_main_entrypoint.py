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


class MainEntrypointTests(unittest.TestCase):
    def test_missing_entsoe_key_exits_without_reading_generated_csvs(self):
        dotenv = types.ModuleType("dotenv")
        dotenv.load_dotenv = lambda: None

        entsoe = types.ModuleType("entsoe")
        entsoe.EntsoePandasClient = object

        pandas = types.ModuleType("pandas")

        def fail_read_csv(*_args, **_kwargs):
            raise AssertionError("main.py should not read generated CSVs after missing API key")

        pandas.read_csv = fail_read_csv

        matplotlib = types.ModuleType("matplotlib")
        matplotlib.__path__ = []
        pyplot = types.ModuleType("matplotlib.pyplot")

        fake_modules = {
            "dotenv": dotenv,
            "entsoe": entsoe,
            "pandas": pandas,
            "matplotlib": matplotlib,
            "matplotlib.pyplot": pyplot,
        }

        main_path = Path(__file__).resolve().parents[1] / "main.py"

        with patch.dict(sys.modules, fake_modules):
            with patch.dict(os.environ, {}, clear=True):
                with patch.object(builtins, "input", side_effect=["", "", ""]):
                    stdout = io.StringIO()
                    with contextlib.redirect_stdout(stdout):
                        runpy.run_path(str(main_path), run_name="__main__")

        self.assertIn("ENTSOE_API_KEY not set", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
