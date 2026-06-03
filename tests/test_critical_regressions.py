import ast
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MAIN_PY = REPO_ROOT / "main.py"


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
        gitignore = (REPO_ROOT / ".gitignore").read_text().splitlines()

        for ignored_path in [
            "admin.txt",
            "admin.local.txt",
            "last_price_state.json",
            "EnergyScraper.py",
            "LegacyTerminal/",
            "INTERVIEW_TALKING_POINTS.md",
        ]:
            with self.subTest(ignored_path=ignored_path):
                self.assertIn(ignored_path, gitignore)


if __name__ == "__main__":
    unittest.main()
