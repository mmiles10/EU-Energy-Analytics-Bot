import importlib.util
import json
import os
import py_compile
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]


def import_updater_module():
    """Import TelegramUpdaterBot with external services stubbed out."""
    dotenv_stub = types.SimpleNamespace(load_dotenv=lambda: None)
    entsoe_stub = types.SimpleNamespace(EntsoePandasClient=object)
    pandas_stub = types.SimpleNamespace()
    pyplot_stub = types.SimpleNamespace(close=lambda: None)
    matplotlib_stub = types.SimpleNamespace(pyplot=pyplot_stub)

    class RequestException(Exception):
        pass

    requests_stub = types.SimpleNamespace(RequestException=RequestException)

    module_name = "TelegramUpdaterBot_under_test"
    spec = importlib.util.spec_from_file_location(module_name, REPO_ROOT / "TelegramUpdaterBot.py")
    module = importlib.util.module_from_spec(spec)

    with mock.patch.dict(
        sys.modules,
        {
            "dotenv": dotenv_stub,
            "entsoe": entsoe_stub,
            "pandas": pandas_stub,
            "matplotlib": matplotlib_stub,
            "matplotlib.pyplot": pyplot_stub,
            "requests": requests_stub,
        },
    ):
        spec.loader.exec_module(module)

    return module


class FakeIloc:
    def __getitem__(self, index):
        return 42.0


class FakeTimestamp:
    def isoformat(self):
        return "2026-05-27T11:00:00+02:00"


class FakePrices:
    empty = False
    iloc = FakeIloc()
    index = [FakeTimestamp()]


class CriticalRegressionTests(unittest.TestCase):
    def test_main_py_compiles(self):
        py_compile.compile(str(REPO_ROOT / "main.py"), doraise=True)

    def test_corrupt_state_is_ignored(self):
        module = import_updater_module()

        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch.object(module, "STATE_PATH", Path(tmpdir) / "last_price_state.json"):
                module.STATE_PATH.write_text("{not json")

                self.assertEqual(module.load_state(), {})

    def test_save_state_writes_atomically(self):
        module = import_updater_module()

        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "last_price_state.json"
            with mock.patch.object(module, "STATE_PATH", state_path):
                module.save_state({"price": 42.0, "ts": "2026-05-27T11:00:00+02:00"})

                self.assertEqual(json.loads(state_path.read_text()), {"price": 42.0, "ts": "2026-05-27T11:00:00+02:00"})
                self.assertFalse(state_path.with_name(f"{state_path.name}.tmp").exists())

    def test_generate_charts_deletes_stale_files_when_no_current_data(self):
        module = import_updater_module()

        with tempfile.TemporaryDirectory() as tmpdir:
            chart_paths = tuple(Path(tmpdir) / chart.name for chart in module.CHART_FILES)
            for chart_path in chart_paths:
                chart_path.write_text("stale")

            with mock.patch.object(module, "CHART_FILES", chart_paths):
                generated = module.generate_charts(None, None, None, "AT", "CH", "DE_LU")

            self.assertEqual(generated, [])
            self.assertFalse(any(chart_path.exists() for chart_path in chart_paths))

    def test_chart_upload_failure_does_not_advance_state(self):
        module = import_updater_module()
        saved_states = []

        module.API_KEY = "entsoe-key"
        module.TOKEN = "telegram-token"
        module.CHAT_ID = "chat-id"
        module.fetch_energy_data = lambda *args: (FakePrices(), None, None)
        module.create_comprehensive_report = lambda *args: "fresh report"
        module.load_state = lambda: {}
        module.generate_charts = lambda *args: [module.CHART_FILES[0]]
        module.send_telegram = lambda *args, **kwargs: None
        module.send_photo = mock.Mock(side_effect=RuntimeError("upload failed"))
        module.save_state = lambda state: saved_states.append(state)

        with self.assertRaisesRegex(RuntimeError, "upload failed"):
            module.main("AT", "CH", "DE_LU")

        self.assertEqual(saved_states, [])

    def test_stale_chart_is_not_sent_or_marked_sent(self):
        module = import_updater_module()
        saved_states = []

        module.API_KEY = "entsoe-key"
        module.TOKEN = "telegram-token"
        module.CHAT_ID = "chat-id"
        module.fetch_energy_data = lambda *args: (FakePrices(), None, None)
        module.create_comprehensive_report = lambda *args: "fresh report"
        module.load_state = lambda: {}
        module.generate_charts = lambda *args: [module.CHART_FILES[0]]
        module.send_telegram = lambda *args, **kwargs: None
        module.send_photo = mock.Mock()
        module.save_state = lambda state: saved_states.append(state)

        with tempfile.TemporaryDirectory() as tmpdir:
            stale_load_chart = Path(tmpdir) / module.CHART_FILES[1].name
            stale_load_chart.write_text("stale")
            chart_files = (
                Path(tmpdir) / module.CHART_FILES[0].name,
                stale_load_chart,
                Path(tmpdir) / module.CHART_FILES[2].name,
            )

            with mock.patch.object(module, "CHART_FILES", chart_files):
                module.generate_charts = lambda *args: [chart_files[0]]
                with self.assertRaisesRegex(RuntimeError, "Refusing to send stale chart"):
                    module.main("AT", "CH", "DE_LU")

        module.send_photo.assert_called_once_with(str(chart_files[0]), mock.ANY)
        self.assertEqual(saved_states, [])


if __name__ == "__main__":
    unittest.main()
