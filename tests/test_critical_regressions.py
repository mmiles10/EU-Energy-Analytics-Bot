import ast
import importlib
import os
import subprocess
import sys
import tempfile
import types
import unittest
from contextlib import contextmanager
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAIN_PY = ROOT / "main.py"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@contextmanager
def working_directory(path):
    old_cwd = Path.cwd()
    try:
        os.chdir(path)
        yield
    finally:
        os.chdir(old_cwd)


def install_import_stubs():
    dotenv = types.ModuleType("dotenv")
    dotenv.load_dotenv = lambda: None
    sys.modules["dotenv"] = dotenv

    entsoe = types.ModuleType("entsoe")
    entsoe.EntsoePandasClient = object
    sys.modules["entsoe"] = entsoe

    pandas = types.ModuleType("pandas")
    sys.modules["pandas"] = pandas

    matplotlib = types.ModuleType("matplotlib")
    pyplot = types.ModuleType("matplotlib.pyplot")
    matplotlib.pyplot = pyplot
    sys.modules["matplotlib"] = matplotlib
    sys.modules["matplotlib.pyplot"] = pyplot

    requests = types.ModuleType("requests")
    sys.modules["requests"] = requests


def import_updater():
    install_import_stubs()
    sys.modules.pop("TelegramUpdaterBot", None)
    return importlib.import_module("TelegramUpdaterBot")


class FakeIloc:
    def __init__(self, values):
        self.values = values

    def __getitem__(self, index):
        return self.values[index]


class FakeTimestamp:
    def isoformat(self):
        return "2026-06-04T10:00:00+00:00"


class FakeSeries:
    def __init__(self, values):
        self.values = values
        self.iloc = FakeIloc(values)
        self.index = [FakeTimestamp() for _ in values]

    @property
    def empty(self):
        return not self.values

    def __len__(self):
        return len(self.values)

    def mean(self):
        return sum(self.values) / len(self.values)

    def min(self):
        return min(self.values)

    def max(self):
        return max(self.values)

    def std(self):
        return 0.0


class MainEntrypointRegressionTests(unittest.TestCase):
    def test_main_guard_only_calls_main(self):
        tree = ast.parse(MAIN_PY.read_text(), filename=str(MAIN_PY))

        guards = [
            node
            for node in tree.body
            if isinstance(node, ast.If)
            and isinstance(node.test, ast.Compare)
            and isinstance(node.test.left, ast.Name)
            and node.test.left.id == "__name__"
        ]

        self.assertEqual(len(guards), 1)
        self.assertEqual(len(guards[0].body), 1)
        statement = guards[0].body[0]
        self.assertIsInstance(statement, ast.Expr)
        self.assertIsInstance(statement.value, ast.Call)
        self.assertIsInstance(statement.value.func, ast.Name)
        self.assertEqual(statement.value.func.id, "main")

    def test_missing_entsoe_key_exits_without_reading_generated_csvs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            stub_root = Path(temp_dir)
            (stub_root / "dotenv.py").write_text("def load_dotenv():\n    return None\n")
            (stub_root / "entsoe.py").write_text(
                "class EntsoePandasClient:\n"
                "    def __init__(self, *args, **kwargs):\n"
                "        pass\n"
            )
            (stub_root / "pandas.py").write_text("")
            matplotlib_dir = stub_root / "matplotlib"
            matplotlib_dir.mkdir()
            (matplotlib_dir / "__init__.py").write_text("")
            (matplotlib_dir / "pyplot.py").write_text("")

            env = os.environ.copy()
            env.pop("ENTSOE_API_KEY", None)
            env["PYTHONPATH"] = temp_dir

            result = subprocess.run(
                [sys.executable, str(MAIN_PY)],
                cwd=temp_dir,
                env=env,
                input="\n\n\n",
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ENTSOE_API_KEY not set", result.stdout)
        self.assertNotIn("Generating charts", result.stdout)
        self.assertNotIn("Traceback", result.stderr)


class GitignoreRegressionTests(unittest.TestCase):
    def test_local_secret_and_state_files_remain_ignored(self):
        ignored = (ROOT / ".gitignore").read_text().splitlines()

        for ignored_path in [
            "admin.txt",
            "admin.local.txt",
            "last_price_state.json",
            "EnergyScraper.py",
            "LegacyTerminal/",
            "INTERVIEW_TALKING_POINTS.md",
        ]:
            with self.subTest(ignored_path=ignored_path):
                self.assertIn(ignored_path, ignored)


class TelegramUpdaterRegressionTests(unittest.TestCase):
    def test_load_state_ignores_corrupt_state_file(self):
        updater = import_updater()
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "last_price_state.json"
            state_path.write_text("{not-json")
            updater.STATE_PATH = state_path

            self.assertEqual(updater.load_state(), {})

    def test_save_state_replaces_file_atomically(self):
        updater = import_updater()
        with tempfile.TemporaryDirectory() as tmpdir:
            updater.STATE_PATH = Path(tmpdir) / "last_price_state.json"

            updater.save_state({"price": 47.0, "ts": "2026-06-04T10:00:00+00:00"})

            self.assertEqual(
                updater.load_state(),
                {"price": 47.0, "ts": "2026-06-04T10:00:00+00:00"},
            )
            self.assertFalse(updater.STATE_PATH.with_name("last_price_state.json.tmp").exists())

    def test_state_not_advanced_when_chart_upload_fails(self):
        updater = import_updater()
        updater.API_KEY = "key"
        updater.TOKEN = "token"
        updater.CHAT_ID = "chat"
        prices = FakeSeries([45.0, 47.0])
        load = FakeSeries([1000.0, 1100.0])
        flows = FakeSeries([10.0, 20.0])
        sent_photos = []

        with tempfile.TemporaryDirectory() as tmpdir, working_directory(Path(tmpdir)):
            updater.STATE_PATH = Path("last_price_state.json")
            updater.fetch_energy_data = lambda *_: (prices, load, flows)
            updater.send_telegram = lambda *_args, **_kwargs: None

            def generate_charts(*_args):
                for chart_file in updater.CHART_FILES:
                    Path(chart_file).write_text("fresh")
                return list(updater.CHART_FILES)

            def send_photo(photo_path, _caption=""):
                sent_photos.append(Path(photo_path).name)
                if Path(photo_path).name == updater.LOAD_CHART:
                    raise RuntimeError("upload failed")

            updater.generate_charts = generate_charts
            updater.send_photo = send_photo

            updater.main("AT", "CH", "DE_LU")

            self.assertIn(updater.LOAD_CHART, sent_photos)
            self.assertFalse(updater.STATE_PATH.exists())

    def test_missing_fresh_chart_blocks_stale_delivery_and_state_update(self):
        updater = import_updater()
        updater.API_KEY = "key"
        updater.TOKEN = "token"
        updater.CHAT_ID = "chat"
        prices = FakeSeries([45.0, 47.0])
        load = FakeSeries([1000.0, 1100.0])
        flows = FakeSeries([10.0, 20.0])
        sent = []

        with tempfile.TemporaryDirectory() as tmpdir, working_directory(Path(tmpdir)):
            updater.STATE_PATH = Path("last_price_state.json")
            Path(updater.FLOWS_CHART).write_text("stale")
            updater.fetch_energy_data = lambda *_: (prices, load, flows)
            updater.send_telegram = lambda *_args, **_kwargs: sent.append("text")
            updater.send_photo = lambda *_args, **_kwargs: sent.append("photo")

            def generate_charts(*_args):
                Path(updater.PRICE_CHART).write_text("fresh")
                Path(updater.LOAD_CHART).write_text("fresh")
                return [updater.PRICE_CHART, updater.LOAD_CHART]

            updater.generate_charts = generate_charts

            updater.main("AT", "CH", "DE_LU")

            self.assertFalse(Path(updater.FLOWS_CHART).exists())
            self.assertEqual(sent, [])
            self.assertFalse(updater.STATE_PATH.exists())

    def test_delivery_errors_redact_bot_token(self):
        updater = import_updater()
        updater.TOKEN = "123456:secret-token"

        message = updater.describe_delivery_error(
            RuntimeError("failed for https://api.telegram.org/bot123456:secret-token/sendPhoto")
        )

        self.assertNotIn("123456:secret-token", message)
        self.assertIn("[redacted-token]", message)


if __name__ == "__main__":
    unittest.main()
