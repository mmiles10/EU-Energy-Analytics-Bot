import ast
import pathlib
import unittest


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


class MainEntrypointTests(unittest.TestCase):
    def test_main_guard_only_invokes_main(self):
        tree = ast.parse((REPO_ROOT / "main.py").read_text())
        guards = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.If) and self._is_main_guard(node.test)
        ]

        self.assertEqual(len(guards), 1)
        self.assertEqual(len(guards[0].body), 1)

        statement = guards[0].body[0]
        self.assertIsInstance(statement, ast.Expr)
        self.assertIsInstance(statement.value, ast.Call)
        self.assertIsInstance(statement.value.func, ast.Name)
        self.assertEqual(statement.value.func.id, "main")
        self.assertEqual(statement.value.args, [])
        self.assertEqual(statement.value.keywords, [])

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


class GitignoreTests(unittest.TestCase):
    def test_local_secret_and_state_files_are_ignored(self):
        ignored_paths = set((REPO_ROOT / ".gitignore").read_text().splitlines())

        self.assertIn("admin.txt", ignored_paths)
        self.assertIn("admin.local.txt", ignored_paths)
        self.assertIn("last_price_state.json", ignored_paths)


if __name__ == "__main__":
    unittest.main()
