import ast
import fnmatch
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class MainEntrypointTests(unittest.TestCase):
    def test_main_guard_only_calls_main(self):
        tree = ast.parse((ROOT / "main.py").read_text())
        main_guard = None

        for node in tree.body:
            if isinstance(node, ast.If) and self._is_main_guard(node.test):
                main_guard = node
                break

        self.assertIsNotNone(main_guard, "main.py must keep a __main__ guard")
        self.assertEqual(len(main_guard.body), 1)
        self.assertIsInstance(main_guard.body[0], ast.Expr)
        call = main_guard.body[0].value
        self.assertIsInstance(call, ast.Call)
        self.assertIsInstance(call.func, ast.Name)
        self.assertEqual(call.func.id, "main")

    def test_no_top_level_csv_reads_after_main_guard(self):
        tree = ast.parse((ROOT / "main.py").read_text())
        seen_main_guard = False

        for node in tree.body:
            if isinstance(node, ast.If) and self._is_main_guard(node.test):
                seen_main_guard = True
                continue

            if seen_main_guard:
                for child in ast.walk(node):
                    if self._is_pandas_read_csv(child):
                        self.fail("top-level CSV reads after main() can crash handled early exits")

    @staticmethod
    def _is_main_guard(test):
        return (
            isinstance(test, ast.Compare)
            and isinstance(test.left, ast.Name)
            and test.left.id == "__name__"
            and len(test.ops) == 1
            and isinstance(test.ops[0], ast.Eq)
            and len(test.comparators) == 1
            and isinstance(test.comparators[0], ast.Constant)
            and test.comparators[0].value == "__main__"
        )

    @staticmethod
    def _is_pandas_read_csv(node):
        return (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "read_csv"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "pd"
        )


class GitignoreTests(unittest.TestCase):
    def test_local_secret_and_state_files_are_ignored(self):
        patterns = [
            line.strip()
            for line in (ROOT / ".gitignore").read_text().splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]

        for path in ["admin.txt", "admin.local.txt", "last_price_state.json"]:
            with self.subTest(path=path):
                self.assertTrue(
                    any(fnmatch.fnmatch(path, pattern) for pattern in patterns),
                    f"{path} must remain ignored",
                )


if __name__ == "__main__":
    unittest.main()
