import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class MainEntrypointTests(unittest.TestCase):
    def test_entrypoint_only_calls_main(self):
        tree = ast.parse((ROOT / "main.py").read_text())
        entrypoints = [
            node for node in tree.body
            if isinstance(node, ast.If)
            and isinstance(node.test, ast.Compare)
            and isinstance(node.test.left, ast.Name)
            and node.test.left.id == "__name__"
        ]

        self.assertEqual(len(entrypoints), 1)
        body = entrypoints[0].body
        self.assertEqual(len(body), 1)
        self.assertIsInstance(body[0], ast.Expr)
        self.assertIsInstance(body[0].value, ast.Call)
        self.assertIsInstance(body[0].value.func, ast.Name)
        self.assertEqual(body[0].value.func.id, "main")


class GitignoreTests(unittest.TestCase):
    def test_local_secret_and_state_files_are_ignored(self):
        ignored_entries = {
            line.strip()
            for line in (ROOT / ".gitignore").read_text().splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }

        self.assertIn("admin.txt", ignored_entries)
        self.assertIn("admin.local.txt", ignored_entries)
        self.assertIn("last_price_state.json", ignored_entries)


if __name__ == "__main__":
    unittest.main()
