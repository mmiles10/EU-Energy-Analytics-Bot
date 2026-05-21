import ast
from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]


def is_main_guard(node):
    if not isinstance(node, ast.Compare) or len(node.ops) != 1 or len(node.comparators) != 1:
        return False
    if not isinstance(node.ops[0], ast.Eq):
        return False

    left = node.left
    right = node.comparators[0]
    return (
        isinstance(left, ast.Name)
        and left.id == "__name__"
        and isinstance(right, ast.Constant)
        and right.value == "__main__"
    )


class MainEntrypointTest(unittest.TestCase):
    def test_main_guard_only_invokes_main(self):
        tree = ast.parse((REPO_ROOT / "main.py").read_text())
        guards = [
            node
            for node in tree.body
            if isinstance(node, ast.If) and is_main_guard(node.test)
        ]

        self.assertEqual(len(guards), 1)
        self.assertEqual(guards[0].orelse, [])
        self.assertEqual(len(guards[0].body), 1)

        entrypoint = guards[0].body[0]
        self.assertIsInstance(entrypoint, ast.Expr)
        self.assertIsInstance(entrypoint.value, ast.Call)
        self.assertIsInstance(entrypoint.value.func, ast.Name)
        self.assertEqual(entrypoint.value.func.id, "main")
        self.assertEqual(entrypoint.value.args, [])
        self.assertEqual(entrypoint.value.keywords, [])


if __name__ == "__main__":
    unittest.main()
