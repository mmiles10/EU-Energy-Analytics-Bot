import ast
import subprocess
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class MainEntrypointTests(unittest.TestCase):
    def test_main_guard_only_calls_main(self):
        tree = ast.parse((REPO_ROOT / "main.py").read_text())
        main_guards = [
            node
            for node in tree.body
            if isinstance(node, ast.If)
            and isinstance(node.test, ast.Compare)
            and isinstance(node.test.left, ast.Name)
            and node.test.left.id == "__name__"
        ]

        self.assertEqual(len(main_guards), 1)
        guard_body = main_guards[0].body
        self.assertEqual(len(guard_body), 1)
        self.assertIsInstance(guard_body[0], ast.Expr)
        self.assertIsInstance(guard_body[0].value, ast.Call)
        self.assertIsInstance(guard_body[0].value.func, ast.Name)
        self.assertEqual(guard_body[0].value.func.id, "main")


class GitignoreRegressionTests(unittest.TestCase):
    def test_local_secret_and_state_files_are_ignored(self):
        paths = ["admin.txt", "admin.local.txt", "last_price_state.json"]
        result = subprocess.run(
            ["git", "check-ignore", *paths],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=True,
        )

        ignored_paths = set(result.stdout.splitlines())
        self.assertEqual(ignored_paths, set(paths))


if __name__ == "__main__":
    unittest.main()
