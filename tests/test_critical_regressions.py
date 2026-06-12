import ast
import pathlib
import unittest


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


class MainEntrypointTests(unittest.TestCase):
    def test_main_guard_only_calls_main(self):
        """The entrypoint must not fall through into stale CSV/chart work."""
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

        self.assertEqual(len(main_guards), 1)
        self.assertEqual(len(main_guards[0].body), 1)

        call_expr = main_guards[0].body[0]
        self.assertIsInstance(call_expr, ast.Expr)
        self.assertIsInstance(call_expr.value, ast.Call)
        self.assertIsInstance(call_expr.value.func, ast.Name)
        self.assertEqual(call_expr.value.func.id, "main")


class GitignoreTests(unittest.TestCase):
    def test_local_secret_and_state_files_are_ignored(self):
        ignored_entries = {
            line.strip()
            for line in (REPO_ROOT / ".gitignore").read_text().splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }

        self.assertIn("admin.txt", ignored_entries)
        self.assertIn("admin.local.txt", ignored_entries)
        self.assertIn("last_price_state.json", ignored_entries)


if __name__ == "__main__":
    unittest.main()
