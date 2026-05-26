import importlib.util
import json
import os
import py_compile
import sys
import tempfile
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def install_dependency_stubs():
    dotenv = types.ModuleType("dotenv")
    dotenv.load_dotenv = lambda: None
    sys.modules["dotenv"] = dotenv

    entsoe = types.ModuleType("entsoe")
    entsoe.EntsoePandasClient = object
    sys.modules["entsoe"] = entsoe

    sys.modules.setdefault("requests", types.ModuleType("requests"))
    sys.modules.setdefault("pandas", types.ModuleType("pandas"))

    matplotlib = types.ModuleType("matplotlib")
    pyplot = types.ModuleType("matplotlib.pyplot")
    matplotlib.pyplot = pyplot
    sys.modules["matplotlib"] = matplotlib
    sys.modules["matplotlib.pyplot"] = pyplot


def import_updater_bot():
    install_dependency_stubs()
    module_name = "_test_telegram_updater_bot"
    sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(module_name, ROOT / "TelegramUpdaterBot.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    module.API_KEY = "entsoe-key"
    module.TOKEN = "telegram-token"
    module.CHAT_ID = "telegram-chat"
    return module


class FakeTimestamp:
    def __init__(self, value):
        self.value = value

    def isoformat(self):
        return self.value


class FakePrices:
    empty = False

    def __init__(self, price, timestamp):
        self.price = price
        self.iloc = self
        self.index = [FakeTimestamp(timestamp)]

    def __getitem__(self, index):
        if index != -1:
            raise IndexError(index)
        return self.price


class CriticalRegressionTests(unittest.TestCase):
    def test_main_entrypoint_compiles(self):
        py_compile.compile(str(ROOT / "main.py"), doraise=True)

    def test_corrupt_state_file_does_not_stop_bot(self):
        bot = import_updater_bot()

        with tempfile.TemporaryDirectory() as tmpdir:
            bot.STATE_PATH = Path(tmpdir) / "last_price_state.json"
            bot.STATE_PATH.write_text("{invalid json")

            self.assertEqual(bot.load_state(), {})

    def test_save_state_replaces_file_atomically(self):
        bot = import_updater_bot()

        with tempfile.TemporaryDirectory() as tmpdir:
            bot.STATE_PATH = Path(tmpdir) / "last_price_state.json"

            bot.save_state({"price": 12.3, "ts": "2026-05-26T10:00:00+00:00"})

            self.assertEqual(
                json.loads(bot.STATE_PATH.read_text()),
                {"price": 12.3, "ts": "2026-05-26T10:00:00+00:00"},
            )
            self.assertFalse((bot.STATE_PATH.parent / ".last_price_state.json.tmp").exists())

    def test_same_timestamp_price_correction_sends_update(self):
        bot = import_updater_bot()
        sent_messages = []

        with tempfile.TemporaryDirectory() as tmpdir:
            old_cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                bot.STATE_PATH = Path(tmpdir) / "last_price_state.json"
                bot.save_state({"price": 10.0, "ts": "2026-05-26T10:00:00+00:00"})
                bot.fetch_energy_data = lambda *_args: (
                    FakePrices(15.5, "2026-05-26T10:00:00+00:00"),
                    None,
                    None,
                )
                bot.create_comprehensive_report = lambda *_args: "report"
                bot.generate_charts = lambda *_args: True
                bot.send_telegram = lambda text, parse_mode="HTML": sent_messages.append(text)
                bot.send_photo = lambda *_args, **_kwargs: None

                bot.main("AT", "CH", "DE_LU")
            finally:
                os.chdir(old_cwd)

            self.assertEqual(sent_messages, ["report"])
            self.assertEqual(
                json.loads(bot.STATE_PATH.read_text()),
                {"price": 15.5, "ts": "2026-05-26T10:00:00+00:00"},
            )

    def test_state_not_advanced_when_generated_chart_send_fails(self):
        bot = import_updater_bot()

        with tempfile.TemporaryDirectory() as tmpdir:
            old_cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                bot.STATE_PATH = Path(tmpdir) / "last_price_state.json"
                original_state = {"price": 10.0, "ts": "2026-05-26T10:00:00+00:00"}
                bot.save_state(original_state)
                bot.fetch_energy_data = lambda *_args: (
                    FakePrices(20.0, "2026-05-26T11:00:00+00:00"),
                    None,
                    None,
                )
                bot.create_comprehensive_report = lambda *_args: "report"

                def generate_chart(*_args):
                    Path("chart_day_ahead_prices.png").write_bytes(b"new chart")
                    return True

                bot.generate_charts = generate_chart
                bot.send_telegram = lambda *_args, **_kwargs: None

                def fail_photo(*_args, **_kwargs):
                    raise RuntimeError("telegram upload failed")

                bot.send_photo = fail_photo

                with self.assertRaises(RuntimeError):
                    bot.main("AT", "CH", "DE_LU")
            finally:
                os.chdir(old_cwd)

            self.assertEqual(json.loads(bot.STATE_PATH.read_text()), original_state)


if __name__ == "__main__":
    unittest.main()
