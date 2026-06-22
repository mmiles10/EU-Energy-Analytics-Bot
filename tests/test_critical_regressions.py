import ast
import subprocess
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class MainEntrypointTests(unittest.TestCase):
    def test_main_guard_only_calls_main(self):
        tree = ast.parse((REPO_ROOT / "main.py").read_text())
        main_guards = [
            node for node in tree.body
            if isinstance(node, ast.If) and self._is_main_guard(node.test)
        ]

        self.assertEqual(len(main_guards), 1)
        self.assertEqual(len(main_guards[0].body), 1)

        only_statement = main_guards[0].body[0]
        self.assertIsInstance(only_statement, ast.Expr)
        self.assertIsInstance(only_statement.value, ast.Call)
        self.assertIsInstance(only_statement.value.func, ast.Name)
        self.assertEqual(only_statement.value.func.id, "main")
        self.assertFalse(main_guards[0].orelse)

    @staticmethod
    def _is_main_guard(test):
        if not isinstance(test, ast.Compare) or len(test.ops) != 1 or len(test.comparators) != 1:
            return False
        if not isinstance(test.ops[0], ast.Eq):
            return False

        left = test.left
        right = test.comparators[0]
        return (
            isinstance(left, ast.Name)
            and left.id == "__name__"
            and isinstance(right, ast.Constant)
            and right.value == "__main__"
        )


class GitignoreTests(unittest.TestCase):
    def test_local_secret_and_runtime_files_are_ignored(self):
        for path in ("admin.txt", "admin.local.txt", "last_price_state.json"):
            with self.subTest(path=path):
                result = subprocess.run(
                    ["git", "check-ignore", "--quiet", path],
                    cwd=REPO_ROOT,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, f"{path} should be ignored")


if __name__ == "__main__":
    unittest.main()
