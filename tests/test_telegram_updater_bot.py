import importlib
import os
import sys
import types
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock


class _Iloc:
    def __getitem__(self, index):
        if index != -1:
            raise IndexError(index)
        return 51.25


class _Prices:
    empty = False
    iloc = _Iloc()
    index = [datetime(2026, 5, 23, 12, 0, tzinfo=timezone.utc)]


def import_bot():
    """Import TelegramUpdaterBot with network/data dependencies stubbed."""
    sys.modules.pop("TelegramUpdaterBot", None)

    dotenv = types.ModuleType("dotenv")
    dotenv.load_dotenv = lambda: None
    sys.modules["dotenv"] = dotenv

    entsoe = types.ModuleType("entsoe")
    entsoe.EntsoePandasClient = object
    sys.modules["entsoe"] = entsoe

    pandas = types.ModuleType("pandas")
    sys.modules["pandas"] = pandas

    requests = types.ModuleType("requests")
    sys.modules["requests"] = requests

    matplotlib = types.ModuleType("matplotlib")
    pyplot = types.ModuleType("matplotlib.pyplot")
    pyplot.close = Mock()
    matplotlib.pyplot = pyplot
    sys.modules["matplotlib"] = matplotlib
    sys.modules["matplotlib.pyplot"] = pyplot

    return importlib.import_module("TelegramUpdaterBot")


class TelegramUpdaterBotTests(unittest.TestCase):
    def setUp(self):
        self.bot = import_bot()
        self.bot.API_KEY = "entsoe-key"
        self.bot.TOKEN = "telegram-token"
        self.bot.CHAT_ID = "telegram-chat"

    def test_corrupt_state_file_is_ignored(self):
        with TemporaryDirectory() as tmpdir:
            self.bot.STATE_PATH = Path(tmpdir) / "last_price_state.json"
            self.bot.STATE_PATH.write_text("{not-json")

            self.assertEqual(self.bot.load_state(), {})

    def test_clear_chart_files_removes_stale_outputs(self):
        with TemporaryDirectory() as tmpdir:
            old_cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                for chart_path in self.bot.CHART_PATHS:
                    chart_path.write_text("stale image")

                self.bot.clear_chart_files()

                for chart_path in self.bot.CHART_PATHS:
                    self.assertFalse(chart_path.exists())
            finally:
                os.chdir(old_cwd)

    def test_main_does_not_save_state_when_chart_send_fails(self):
        with TemporaryDirectory() as tmpdir:
            self.bot.STATE_PATH = Path(tmpdir) / "last_price_state.json"
            self.bot.fetch_energy_data = Mock(return_value=(_Prices(), None, None))
            self.bot.create_comprehensive_report = Mock(return_value="<b>report</b>")
            self.bot.generate_charts = Mock(return_value=[(Path("fresh.png"), "fresh chart")])
            self.bot.send_telegram = Mock()
            self.bot.send_photo = Mock(side_effect=RuntimeError("telegram upload failed"))
            self.bot.save_state = Mock()

            self.bot.main("AT", "CH", "DE_LU")

            self.bot.send_telegram.assert_called_once_with("<b>report</b>", parse_mode="HTML")
            self.bot.send_photo.assert_called_once_with("fresh.png", "fresh chart")
            self.bot.save_state.assert_not_called()

    def test_main_saves_state_after_report_and_generated_charts_send(self):
        with TemporaryDirectory() as tmpdir:
            self.bot.STATE_PATH = Path(tmpdir) / "last_price_state.json"
            self.bot.fetch_energy_data = Mock(return_value=(_Prices(), None, None))
            self.bot.create_comprehensive_report = Mock(return_value="<b>report</b>")
            self.bot.generate_charts = Mock(return_value=[(Path("fresh.png"), "fresh chart")])
            self.bot.send_telegram = Mock()
            self.bot.send_photo = Mock()
            self.bot.save_state = Mock()

            self.bot.main("AT", "CH", "DE_LU")

            self.bot.send_telegram.assert_called_once_with("<b>report</b>", parse_mode="HTML")
            self.bot.send_photo.assert_called_once_with("fresh.png", "fresh chart")
            self.bot.save_state.assert_called_once_with(
                {"price": 51.25, "ts": "2026-05-23T12:00:00+00:00"}
            )


if __name__ == "__main__":
    unittest.main()
