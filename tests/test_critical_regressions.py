import ast
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class MainEntrypointTests(unittest.TestCase):
    def test_main_guard_only_invokes_main(self):
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

        call = main_guards[0].body[0]
        self.assertIsInstance(call, ast.Expr)
        self.assertIsInstance(call.value, ast.Call)
        self.assertIsInstance(call.value.func, ast.Name)
        self.assertEqual(call.value.func.id, "main")


class GitIgnoreTests(unittest.TestCase):
    def test_local_secret_and_state_files_are_ignored(self):
        ignore_lines = {
            line.strip()
            for line in (REPO_ROOT / ".gitignore").read_text().splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }

        self.assertIn("admin.txt", ignore_lines)
        self.assertIn("admin.local.txt", ignore_lines)
        self.assertIn("last_price_state.json", ignore_lines)


if __name__ == "__main__":
    unittest.main()
