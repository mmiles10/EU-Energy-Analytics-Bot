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
        self.assertEqual(len(main_guards[0].body), 1)

        only_stmt = main_guards[0].body[0]
        self.assertIsInstance(only_stmt, ast.Expr)
        self.assertIsInstance(only_stmt.value, ast.Call)
        self.assertIsInstance(only_stmt.value.func, ast.Name)
        self.assertEqual(only_stmt.value.func.id, "main")


class GitignoreTests(unittest.TestCase):
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
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        self.assertEqual(
            result.stdout.splitlines(),
            ["admin.txt", "admin.local.txt", "last_price_state.json"],
        )


if __name__ == "__main__":
    unittest.main()
