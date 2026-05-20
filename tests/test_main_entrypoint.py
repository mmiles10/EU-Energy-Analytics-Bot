import contextlib
import io
import os
import runpy
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def _dependency_stubs():
    dotenv = types.ModuleType("dotenv")
    dotenv.load_dotenv = lambda *args, **kwargs: None

    entsoe = types.ModuleType("entsoe")

    class EntsoePandasClient:
        pass

    entsoe.EntsoePandasClient = EntsoePandasClient

    pandas = types.ModuleType("pandas")

    def fail_read_csv(*args, **kwargs):
        raise AssertionError("main.py should not read generated CSV files without an API key")

    pandas.read_csv = fail_read_csv

    matplotlib = types.ModuleType("matplotlib")
    matplotlib.__path__ = []
    pyplot = types.ModuleType("matplotlib.pyplot")

    return {
        "dotenv": dotenv,
        "entsoe": entsoe,
        "pandas": pandas,
        "matplotlib": matplotlib,
        "matplotlib.pyplot": pyplot,
    }


class MainEntrypointTest(unittest.TestCase):
    def test_missing_entsoe_key_exits_before_chart_tail(self):
        original_cwd = os.getcwd()
        stdout = io.StringIO()

        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                os.chdir(tmpdir)
                with patch.dict(sys.modules, _dependency_stubs()):
                    with patch.dict(os.environ, {}, clear=True):
                        with patch("builtins.input", return_value=""):
                            with contextlib.redirect_stdout(stdout):
                                runpy.run_path(str(ROOT / "main.py"), run_name="__main__")
            finally:
                os.chdir(original_cwd)

        self.assertIn("Error: ENTSOE_API_KEY not set in environment", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
