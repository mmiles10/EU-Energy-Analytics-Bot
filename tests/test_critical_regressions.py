import ast
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class MainEntrypointTests(unittest.TestCase):
    def test_main_guard_only_invokes_main(self):
        tree = ast.parse((REPO_ROOT / "main.py").read_text())

        main_guards = [
            node for node in tree.body
            if isinstance(node, ast.If) and _is_main_guard(node.test)
        ]
        self.assertEqual(len(main_guards), 1)

        body = main_guards[0].body
        self.assertEqual(
            len(body),
            1,
            "main.py must not run stale chart-generation code after main() returns",
        )
        self.assertTrue(_is_main_call(body[0]))


class IgnoreFileTests(unittest.TestCase):
    def test_local_secret_and_runtime_files_are_ignored(self):
        ignored_paths = {
            line.strip()
            for line in (REPO_ROOT / ".gitignore").read_text().splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }

        self.assertIn("admin.txt", ignored_paths)
        self.assertIn("admin.local.txt", ignored_paths)
        self.assertIn("last_price_state.json", ignored_paths)


def _is_main_guard(test):
    if not isinstance(test, ast.Compare):
        return False
    if len(test.ops) != 1 or not isinstance(test.ops[0], ast.Eq):
        return False
    if len(test.comparators) != 1:
        return False
    return _constant_value(test.left) == "__name__" and _constant_value(test.comparators[0]) == "__main__"


def _is_main_call(node):
    return (
        isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "main"
        and not node.value.args
        and not node.value.keywords
    )


def _constant_value(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Constant):
        return node.value
    return None


if __name__ == "__main__":
    unittest.main()
