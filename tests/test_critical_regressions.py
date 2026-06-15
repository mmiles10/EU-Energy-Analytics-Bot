import ast
import importlib
import json
import os
import sys
import tempfile
import types
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]


def import_updater():
    dotenv = types.ModuleType("dotenv")
    dotenv.load_dotenv = lambda: None

    entsoe = types.ModuleType("entsoe")
    entsoe.EntsoePandasClient = object

    pandas = types.ModuleType("pandas")

    matplotlib = types.ModuleType("matplotlib")
    matplotlib.__path__ = []
    pyplot = types.ModuleType("matplotlib.pyplot")

    with mock.patch.dict(
        sys.modules,
        {
            "dotenv": dotenv,
            "entsoe": entsoe,
            "pandas": pandas,
            "matplotlib": matplotlib,
            "matplotlib.pyplot": pyplot,
        },
    ):
        sys.modules.pop("TelegramUpdaterBot", None)
        return importlib.import_module("TelegramUpdaterBot")


@contextmanager
def temporary_cwd(path):
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


class FakeIloc:
    def __getitem__(self, index):
        return 50.0


class FakeTimestamp:
    def isoformat(self):
        return "2026-06-15T11:00:00+00:00"


class FakeSeries:
    empty = False
    iloc = FakeIloc()
    index = [FakeTimestamp()]

    def mean(self):
        return 50.0

    def min(self):
        return 40.0

    def max(self):
        return 70.0

    def std(self):
        return 5.0

    def __len__(self):
        return 1


class CriticalRegressionTests(unittest.TestCase):
    def test_main_entrypoint_has_no_dead_chart_block(self):
        tree = ast.parse((ROOT / "main.py").read_text())
        main_guards = [
            node
            for node in tree.body
            if isinstance(node, ast.If)
            and isinstance(node.test, ast.Compare)
            and isinstance(node.test.left, ast.Name)
            and node.test.left.id == "__name__"
        ]

        self.assertEqual(1, len(main_guards))
        self.assertEqual(1, len(main_guards[0].body))
        call = main_guards[0].body[0]
        self.assertIsInstance(call, ast.Expr)
        self.assertIsInstance(call.value, ast.Call)
        self.assertEqual("main", call.value.func.id)

    def test_local_secret_and_state_files_are_ignored(self):
        ignore_rules = (ROOT / ".gitignore").read_text().splitlines()

        for filename in ("admin.txt", "admin.local.txt", "last_price_state.json"):
            self.assertIn(filename, ignore_rules)

    def test_corrupt_state_is_ignored_and_state_writes_are_atomic(self):
        bot = import_updater()

        with tempfile.TemporaryDirectory() as tmpdir:
            bot.STATE_PATH = Path(tmpdir) / "last_price_state.json"
            bot.STATE_PATH.write_text("{")

            self.assertEqual({}, bot.load_state())

            bot.save_state({"price": 10.5, "ts": "2026-06-15T10:00:00+00:00"})

            self.assertEqual(
                {"price": 10.5, "ts": "2026-06-15T10:00:00+00:00"},
                json.loads(bot.STATE_PATH.read_text()),
            )
            self.assertFalse(bot.STATE_PATH.with_name("last_price_state.json.tmp").exists())

    def test_stale_charts_are_removed_and_failed_photo_blocks_state_advance(self):
        bot = import_updater()
        bot.API_KEY = "api-key"
        bot.TOKEN = "telegram-token"
        bot.CHAT_ID = "chat-id"
        saved_states = []

        with tempfile.TemporaryDirectory() as tmpdir, temporary_cwd(tmpdir):
            for chart_file in bot.CHART_FILES:
                Path(chart_file).write_text("stale")

            def generate_current_charts(*_args):
                for chart_file in bot.CHART_FILES:
                    self.assertFalse(Path(chart_file).exists(), chart_file)
                    Path(chart_file).write_text("fresh")
                return True

            def fail_one_photo(photo_path, _caption):
                if photo_path == "chart_load.png":
                    raise RuntimeError("upload failed")

            with mock.patch.object(bot, "fetch_energy_data", return_value=(FakeSeries(), FakeSeries(), FakeSeries())), \
                mock.patch.object(bot, "load_state", return_value={}), \
                mock.patch.object(bot, "save_state", side_effect=saved_states.append), \
                mock.patch.object(bot, "generate_charts", side_effect=generate_current_charts), \
                mock.patch.object(bot, "send_telegram"), \
                mock.patch.object(bot, "send_photo", side_effect=fail_one_photo):
                bot.main("AT", "CH", "DE_LU")

            self.assertEqual([], saved_states)
            for chart_file in bot.CHART_FILES:
                self.assertEqual("fresh", Path(chart_file).read_text())

    def test_missing_generated_chart_blocks_text_send_and_state_advance(self):
        bot = import_updater()
        bot.API_KEY = "api-key"
        bot.TOKEN = "telegram-token"
        bot.CHAT_ID = "chat-id"
        saved_states = []

        with tempfile.TemporaryDirectory() as tmpdir, temporary_cwd(tmpdir):
            def generate_partial_charts(*_args):
                Path("chart_day_ahead_prices.png").write_text("fresh")
                Path("chart_load.png").write_text("fresh")
                return True

            with mock.patch.object(bot, "fetch_energy_data", return_value=(FakeSeries(), FakeSeries(), FakeSeries())), \
                mock.patch.object(bot, "load_state", return_value={}), \
                mock.patch.object(bot, "save_state", side_effect=saved_states.append), \
                mock.patch.object(bot, "generate_charts", side_effect=generate_partial_charts), \
                mock.patch.object(bot, "send_telegram") as send_telegram, \
                mock.patch.object(bot, "send_photo") as send_photo:
                bot.main("AT", "CH", "DE_LU")

            send_telegram.assert_not_called()
            send_photo.assert_not_called()
            self.assertEqual([], saved_states)

    def test_same_timestamp_price_change_sends_update(self):
        bot = import_updater()
        bot.API_KEY = "api-key"
        bot.TOKEN = "telegram-token"
        bot.CHAT_ID = "chat-id"
        saved_states = []

        with tempfile.TemporaryDirectory() as tmpdir, temporary_cwd(tmpdir):
            def generate_current_charts(*_args):
                for chart_file in bot.CHART_FILES:
                    Path(chart_file).write_text("fresh")
                return True

            with mock.patch.object(bot, "fetch_energy_data", return_value=(FakeSeries(), FakeSeries(), FakeSeries())), \
                mock.patch.object(
                    bot,
                    "load_state",
                    return_value={"price": 49.0, "ts": "2026-06-15T11:00:00+00:00"},
                ), \
                mock.patch.object(bot, "save_state", side_effect=saved_states.append), \
                mock.patch.object(bot, "generate_charts", side_effect=generate_current_charts), \
                mock.patch.object(bot, "send_telegram"), \
                mock.patch.object(bot, "send_photo"):
                bot.main("AT", "CH", "DE_LU")

            self.assertEqual(
                [{"price": 50.0, "ts": "2026-06-15T11:00:00+00:00"}],
                saved_states,
            )


if __name__ == "__main__":
    unittest.main()
