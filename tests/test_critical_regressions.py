import ast
from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]


class MainEntrypointTests(unittest.TestCase):
    def test_main_guard_only_calls_main(self):
        tree = ast.parse((REPO_ROOT / "main.py").read_text())

        main_guards = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.If)
            and isinstance(node.test, ast.Compare)
            and isinstance(node.test.left, ast.Name)
            and node.test.left.id == "__name__"
        ]

        self.assertEqual(len(main_guards), 1)
        guard_body = main_guards[0].body
        self.assertEqual(len(guard_body), 1)
        call = guard_body[0]
        self.assertIsInstance(call, ast.Expr)
        self.assertIsInstance(call.value, ast.Call)
        self.assertIsInstance(call.value.func, ast.Name)
        self.assertEqual(call.value.func.id, "main")


class GitignoreTests(unittest.TestCase):
    def test_local_secret_and_state_files_are_ignored(self):
        ignored = {
            line.strip()
            for line in (REPO_ROOT / ".gitignore").read_text().splitlines()
            if line.strip() and not line.startswith("#")
        }

        self.assertIn("admin.txt", ignored)
        self.assertIn("admin.local.txt", ignored)
        self.assertIn("last_price_state.json", ignored)


if __name__ == "__main__":
    unittest.main()
