import os
import runpy
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock


class FakeAxes:
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


class FakePyplot(types.ModuleType):
    def __init__(self):
        super().__init__("matplotlib.pyplot")

    def subplots(self, *args, **kwargs):
        return object(), FakeAxes()

    def tight_layout(self, *args, **kwargs):
        pass

    def savefig(self, path, *args, **kwargs):
        Path(path).write_bytes(b"fresh chart")

    def close(self, *args, **kwargs):
        pass

    def ylabel(self, *args, **kwargs):
        pass


class FakeSeries:
    empty = False

    def plot(self, *args, **kwargs):
        pass


class FakeIloc:
    def __getitem__(self, key):
        return 42.0


class FakeTimestamp:
    def isoformat(self):
        return "2026-05-29T10:00:00+00:00"


class FakePrices:
    empty = False
    iloc = FakeIloc()
    index = [FakeTimestamp()]


def dependency_stubs():
    pandas = types.ModuleType("pandas")

    def fail_read_csv(*args, **kwargs):
        raise AssertionError("main.py should not read CSVs after a clean no-key exit")

    pandas.read_csv = fail_read_csv

    matplotlib = types.ModuleType("matplotlib")
    matplotlib.__path__ = []
    matplotlib.use = lambda *args, **kwargs: None

    dotenv = types.ModuleType("dotenv")
    dotenv.load_dotenv = lambda *args, **kwargs: None

    entsoe = types.ModuleType("entsoe")
    entsoe.EntsoePandasClient = object

    return {
        "pandas": pandas,
        "matplotlib": matplotlib,
        "matplotlib.pyplot": FakePyplot(),
        "dotenv": dotenv,
        "entsoe": entsoe,
    }


def import_updater():
    sys.modules.pop("TelegramUpdaterBot", None)
    with mock.patch.dict(sys.modules, dependency_stubs()):
        import TelegramUpdaterBot

    return TelegramUpdaterBot


class CriticalRegressionTests(unittest.TestCase):
    def test_main_no_key_exit_does_not_run_stale_chart_block(self):
        with mock.patch.dict(sys.modules, dependency_stubs()):
            with mock.patch.dict(os.environ, {"ENTSOE_API_KEY": ""}):
                with mock.patch("builtins.input", return_value=""):
                    runpy.run_path("/workspace/main.py", run_name="__main__")

    def test_corrupt_state_is_ignored_and_save_is_atomic(self):
        bot = import_updater()
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "last_price_state.json"
            bot.STATE_PATH = state_path
            state_path.write_text("{bad")

            self.assertEqual(bot.load_state(), {})

            bot.save_state({"price": 42.0, "ts": "2026-05-29T10:00:00+00:00"})

            self.assertEqual(bot.load_state()["price"], 42.0)
            self.assertFalse((Path(tmpdir) / ".last_price_state.json.tmp").exists())

    def test_generate_charts_removes_stale_files_and_returns_created_charts(self):
        bot = import_updater()
        with tempfile.TemporaryDirectory() as tmpdir:
            old_cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                Path("chart_load.png").write_bytes(b"stale load")
                Path("chart_crossborder_flows.png").write_bytes(b"stale flows")

                created = bot.generate_charts(FakeSeries(), None, None, "AT", "CH", "DE_LU")

                self.assertEqual([path for path, _ in created], ["chart_day_ahead_prices.png"])
                self.assertTrue(Path("chart_day_ahead_prices.png").exists())
                self.assertFalse(Path("chart_load.png").exists())
                self.assertFalse(Path("chart_crossborder_flows.png").exists())
            finally:
                os.chdir(old_cwd)

    def test_partial_photo_failure_does_not_advance_state(self):
        bot = import_updater()
        with tempfile.TemporaryDirectory() as tmpdir:
            old_cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                bot.API_KEY = "key"
                bot.TOKEN = "token"
                bot.CHAT_ID = "chat"
                bot.STATE_PATH = Path(tmpdir) / "last_price_state.json"
                Path("chart_day_ahead_prices.png").write_bytes(b"price")
                Path("chart_load.png").write_bytes(b"load")

                def fail_on_load(path, caption=""):
                    if path.endswith("chart_load.png"):
                        raise RuntimeError("telegram upload failed")

                with mock.patch.object(bot, "fetch_energy_data", return_value=(FakePrices(), None, None)):
                    with mock.patch.object(bot, "create_comprehensive_report", return_value="report"):
                        with mock.patch.object(
                            bot,
                            "generate_charts",
                            return_value=[
                                ("chart_day_ahead_prices.png", "price"),
                                ("chart_load.png", "load"),
                            ],
                        ):
                            with mock.patch.object(bot, "send_telegram", return_value=None):
                                with mock.patch.object(bot, "send_photo", side_effect=fail_on_load):
                                    bot.main("AT", "CH", "DE_LU")

                self.assertFalse(bot.STATE_PATH.exists())
            finally:
                os.chdir(old_cwd)

    def test_gitignore_keeps_local_secrets_and_state_untracked(self):
        gitignore = Path("/workspace/.gitignore").read_text()

        self.assertIn("admin.txt", gitignore)
        self.assertIn("admin.local.txt", gitignore)
        self.assertIn("last_price_state.json", gitignore)


if __name__ == "__main__":
    unittest.main()
