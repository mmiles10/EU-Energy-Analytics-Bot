import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class MainEntrypointTests(unittest.TestCase):
    def test_main_guard_only_calls_main(self):
        tree = ast.parse((ROOT / "main.py").read_text())

        guards = [
            node
            for node in tree.body
            if isinstance(node, ast.If)
            and isinstance(node.test, ast.Compare)
            and isinstance(node.test.left, ast.Name)
            and node.test.left.id == "__name__"
            and any(isinstance(comparator, ast.Constant) and comparator.value == "__main__" for comparator in node.test.comparators)
        ]

        self.assertEqual(len(guards), 1)
        self.assertEqual(len(guards[0].body), 1)

        stmt = guards[0].body[0]
        self.assertIsInstance(stmt, ast.Expr)
        self.assertIsInstance(stmt.value, ast.Call)
        self.assertIsInstance(stmt.value.func, ast.Name)
        self.assertEqual(stmt.value.func.id, "main")


class GitignoreTests(unittest.TestCase):
    def test_local_secret_and_state_files_are_ignored(self):
        ignored_entries = set((ROOT / ".gitignore").read_text().splitlines())

        self.assertTrue(
            {"admin.txt", "admin.local.txt", "last_price_state.json"}.issubset(ignored_entries)
        )


if __name__ == "__main__":
    unittest.main()
