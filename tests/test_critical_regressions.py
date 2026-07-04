import ast
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class EntrypointRegressionTests(unittest.TestCase):
    def test_main_entrypoint_only_calls_main(self):
        tree = ast.parse((ROOT / "main.py").read_text())
        entrypoint_guards = [
            node
            for node in tree.body
            if isinstance(node, ast.If)
            and isinstance(node.test, ast.Compare)
            and isinstance(node.test.left, ast.Name)
            and node.test.left.id == "__name__"
            and any(
                isinstance(comparator, ast.Constant)
                and comparator.value == "__main__"
                for comparator in node.test.comparators
            )
        ]

        self.assertEqual(len(entrypoint_guards), 1)
        guard_body = entrypoint_guards[0].body
        self.assertEqual(len(guard_body), 1)
        self.assertIsInstance(guard_body[0], ast.Expr)
        call = guard_body[0].value
        self.assertIsInstance(call, ast.Call)
        self.assertIsInstance(call.func, ast.Name)
        self.assertEqual(call.func.id, "main")
        self.assertEqual(call.args, [])
        self.assertEqual(call.keywords, [])


class IgnoreRegressionTests(unittest.TestCase):
    def test_local_secret_and_state_files_are_ignored(self):
        paths = ["admin.txt", "admin.local.txt", "last_price_state.json"]
        result = subprocess.run(
            ["git", "check-ignore", *paths],
            cwd=ROOT,
            check=True,
            text=True,
            capture_output=True,
        )

        self.assertEqual(result.stdout.splitlines(), paths)


if __name__ == "__main__":
    unittest.main()
