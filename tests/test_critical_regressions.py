import contextlib
import importlib
import io
import json
import os
import runpy
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]


@contextlib.contextmanager
def stub_external_modules():
    """Provide just enough optional dependencies for credential-free tests."""
    sentinel = object()
    module_names = [
        "dotenv",
        "entsoe",
        "pandas",
        "matplotlib",
        "matplotlib.pyplot",
        "requests",
    ]
    saved = {name: sys.modules.get(name, sentinel) for name in module_names}

    dotenv = types.ModuleType("dotenv")
    dotenv.load_dotenv = lambda: None

    entsoe = types.ModuleType("entsoe")

    class EntsoePandasClient:
        def __init__(self, *args, **kwargs):
            pass

    entsoe.EntsoePandasClient = EntsoePandasClient

    pandas = types.ModuleType("pandas")

    def fail_read_csv(*args, **kwargs):
        raise AssertionError("stale chart block attempted to read CSV files")

    pandas.read_csv = fail_read_csv

    matplotlib = types.ModuleType("matplotlib")
    pyplot = types.ModuleType("matplotlib.pyplot")
    matplotlib.pyplot = pyplot

    requests = types.ModuleType("requests")

    sys.modules.update(
        {
            "dotenv": dotenv,
            "entsoe": entsoe,
            "pandas": pandas,
            "matplotlib": matplotlib,
            "matplotlib.pyplot": pyplot,
            "requests": requests,
        }
    )

    try:
        yield
    finally:
        for name, module in saved.items():
            if module is sentinel:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module


@contextlib.contextmanager
def temporary_cwd(path):
    old_cwd = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old_cwd)


def import_updater():
    sys.modules.pop("TelegramUpdaterBot", None)
    with stub_external_modules():
        return importlib.import_module("TelegramUpdaterBot")


class FakeTimestamp:
    def __init__(self, value):
        self.value = value

    def isoformat(self):
        return self.value


class FakeIloc:
    def __init__(self, latest_value):
        self.latest_value = latest_value

    def __getitem__(self, index):
        if index != -1:
            raise AssertionError(f"unexpected iloc index: {index}")
        return self.latest_value


class FakePrices:
    empty = False

    def __init__(self, latest_value, timestamp):
        self.iloc = FakeIloc(latest_value)
        self.index = [FakeTimestamp(timestamp)]


class CriticalRegressionTests(unittest.TestCase):
    def test_main_missing_api_key_returns_without_reading_removed_csv_outputs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            stdout = io.StringIO()
            with (
                stub_external_modules(),
                temporary_cwd(tmpdir),
                mock.patch.dict(os.environ, {}, clear=True),
                mock.patch("builtins.input", side_effect=["", "", ""]),
                mock.patch("sys.stdout", stdout),
            ):
                runpy.run_path(str(ROOT / "main.py"), run_name="__main__")

        self.assertIn("ENTSOE_API_KEY not set", stdout.getvalue())

    def test_updater_sends_when_latest_price_changes_at_same_timestamp(self):
        bot = import_updater()
        timestamp = "2026-06-10T10:00:00+02:00"

        with tempfile.TemporaryDirectory() as tmpdir, temporary_cwd(tmpdir):
            state_path = Path(tmpdir) / "last_price_state.json"
            state_path.write_text(json.dumps({"price": 50.0, "ts": timestamp}))
            sent = []

            def generate_all_charts(*args):
                for chart_file in (
                    "chart_day_ahead_prices.png",
                    "chart_load.png",
                    "chart_crossborder_flows.png",
                ):
                    Path(chart_file).write_bytes(b"png")
                return True

            with (
                mock.patch.object(bot, "STATE_PATH", state_path),
                mock.patch.object(bot, "API_KEY", "api-key"),
                mock.patch.object(bot, "TOKEN", "telegram-token"),
                mock.patch.object(bot, "CHAT_ID", "chat-id"),
                mock.patch.object(
                    bot,
                    "fetch_energy_data",
                    return_value=(FakePrices(55.0, timestamp), object(), object()),
                ),
                mock.patch.object(bot, "create_comprehensive_report", return_value="<b>report</b>"),
                mock.patch.object(bot, "generate_charts", side_effect=generate_all_charts),
                mock.patch.object(bot, "send_telegram", side_effect=lambda *args, **kwargs: sent.append("text")),
                mock.patch.object(bot, "send_photo", side_effect=lambda path, caption: sent.append(Path(path).name)),
            ):
                bot.main("AT", "CH", "DE_LU")

            self.assertEqual(
                sent,
                [
                    "text",
                    "chart_day_ahead_prices.png",
                    "chart_load.png",
                    "chart_crossborder_flows.png",
                ],
            )
            self.assertEqual(json.loads(state_path.read_text()), {"price": 55.0, "ts": timestamp})

    def test_updater_does_not_advance_state_when_expected_chart_is_missing(self):
        bot = import_updater()
        timestamp = "2026-06-10T11:00:00+02:00"

        with tempfile.TemporaryDirectory() as tmpdir, temporary_cwd(tmpdir):
            state_path = Path(tmpdir) / "last_price_state.json"
            original_state = {"price": 50.0, "ts": "2026-06-10T10:00:00+02:00"}
            state_path.write_text(json.dumps(original_state))
            sent = []

            def generate_incomplete_charts(*args):
                Path("chart_day_ahead_prices.png").write_bytes(b"png")
                return True

            with (
                mock.patch.object(bot, "STATE_PATH", state_path),
                mock.patch.object(bot, "API_KEY", "api-key"),
                mock.patch.object(bot, "TOKEN", "telegram-token"),
                mock.patch.object(bot, "CHAT_ID", "chat-id"),
                mock.patch.object(
                    bot,
                    "fetch_energy_data",
                    return_value=(FakePrices(55.0, timestamp), object(), object()),
                ),
                mock.patch.object(bot, "create_comprehensive_report", return_value="<b>report</b>"),
                mock.patch.object(bot, "generate_charts", side_effect=generate_incomplete_charts),
                mock.patch.object(bot, "send_telegram", side_effect=lambda *args, **kwargs: sent.append("text")),
                mock.patch.object(bot, "send_photo", side_effect=lambda path, caption: sent.append(Path(path).name)),
            ):
                with self.assertRaisesRegex(RuntimeError, "chart_load.png"):
                    bot.main("AT", "CH", "DE_LU")

            self.assertEqual(sent, [])
            self.assertEqual(json.loads(state_path.read_text()), original_state)

    def test_updater_does_not_advance_state_when_photo_delivery_fails(self):
        bot = import_updater()
        timestamp = "2026-06-10T11:00:00+02:00"

        with tempfile.TemporaryDirectory() as tmpdir, temporary_cwd(tmpdir):
            state_path = Path(tmpdir) / "last_price_state.json"
            original_state = {"price": 50.0, "ts": "2026-06-10T10:00:00+02:00"}
            state_path.write_text(json.dumps(original_state))

            def generate_all_charts(*args):
                for chart_file in (
                    "chart_day_ahead_prices.png",
                    "chart_load.png",
                    "chart_crossborder_flows.png",
                ):
                    Path(chart_file).write_bytes(b"png")
                return True

            def fail_on_load_chart(path, caption):
                if Path(path).name == "chart_load.png":
                    raise RuntimeError("photo upload failed")

            with (
                mock.patch.object(bot, "STATE_PATH", state_path),
                mock.patch.object(bot, "API_KEY", "api-key"),
                mock.patch.object(bot, "TOKEN", "telegram-token"),
                mock.patch.object(bot, "CHAT_ID", "chat-id"),
                mock.patch.object(
                    bot,
                    "fetch_energy_data",
                    return_value=(FakePrices(55.0, timestamp), object(), object()),
                ),
                mock.patch.object(bot, "create_comprehensive_report", return_value="<b>report</b>"),
                mock.patch.object(bot, "generate_charts", side_effect=generate_all_charts),
                mock.patch.object(bot, "send_telegram", return_value=None),
                mock.patch.object(bot, "send_photo", side_effect=fail_on_load_chart),
            ):
                with self.assertRaisesRegex(RuntimeError, "photo upload failed"):
                    bot.main("AT", "CH", "DE_LU")

            self.assertEqual(json.loads(state_path.read_text()), original_state)

    def test_corrupt_updater_state_is_ignored(self):
        bot = import_updater()

        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "last_price_state.json"
            state_path.write_text("{not json")
            with mock.patch.object(bot, "STATE_PATH", state_path):
                self.assertEqual(bot.load_state(), {})


if __name__ == "__main__":
    unittest.main()
