import ast
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def is_main_guard(node):
    if not isinstance(node, ast.If):
        return False
    test = node.test
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


def is_main_call(node):
    return (
        isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "main"
        and not node.value.args
        and not node.value.keywords
    )


class CriticalRegressionTests(unittest.TestCase):
    def test_main_entrypoint_only_calls_main(self):
        tree = ast.parse((ROOT / "main.py").read_text(encoding="utf-8"))
        guards = [node for node in tree.body if is_main_guard(node)]

        self.assertEqual(1, len(guards))
        self.assertEqual(1, len(guards[0].body))
        self.assertTrue(is_main_call(guards[0].body[0]))
        self.assertEqual([], guards[0].orelse)

    def test_local_secret_and_state_files_are_ignored(self):
        ignored = {
            line.strip()
            for line in (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }

        for path in ("admin.txt", "admin.local.txt", "last_price_state.json"):
            with self.subTest(path=path):
                self.assertIn(path, ignored)

    def test_docs_do_not_publish_numeric_telegram_chat_id(self):
        overview = (ROOT / "docs" / "overview.txt").read_text(encoding="utf-8")

        self.assertNotIn("8466265605", overview)
        self.assertIsNone(re.search(r"(?i)\bchat id:\s*\d+\b", overview))


if __name__ == "__main__":
    unittest.main()
