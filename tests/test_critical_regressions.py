import ast
import subprocess
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class MainEntrypointRegressionTests(unittest.TestCase):
    def test_main_module_parses(self):
        source = (REPO_ROOT / "main.py").read_text()
        ast.parse(source)

    def test_main_guard_only_calls_main(self):
        source = (REPO_ROOT / "main.py").read_text()
        tree = ast.parse(source)

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
        only_statement = main_guards[0].body[0]
        self.assertIsInstance(only_statement, ast.Expr)
        self.assertIsInstance(only_statement.value, ast.Call)
        self.assertIsInstance(only_statement.value.func, ast.Name)
        self.assertEqual("main", only_statement.value.func.id)


class GitignoreRegressionTests(unittest.TestCase):
    def test_local_secret_and_state_files_are_ignored(self):
        result = subprocess.run(
            [
                "git",
                "check-ignore",
                "admin.txt",
                "admin.local.txt",
                "last_price_state.json",
            ],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(
            0,
            result.returncode,
            msg=f"git check-ignore failed\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )


if __name__ == "__main__":
    unittest.main()
