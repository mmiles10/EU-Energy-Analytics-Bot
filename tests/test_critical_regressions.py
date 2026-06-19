import ast
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class MainEntrypointRegressionTests(unittest.TestCase):
    def test_main_guard_only_calls_main(self):
        tree = ast.parse((ROOT / "main.py").read_text())
        main_guards = [
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

        self.assertEqual(len(main_guards), 1)
        self.assertEqual(len(main_guards[0].body), 1)
        call = main_guards[0].body[0]
        self.assertIsInstance(call, ast.Expr)
        self.assertIsInstance(call.value, ast.Call)
        self.assertIsInstance(call.value.func, ast.Name)
        self.assertEqual(call.value.func.id, "main")


class GitignoreRegressionTests(unittest.TestCase):
    def test_local_secret_and_state_files_are_ignored(self):
        result = subprocess.run(
            [
                "git",
                "check-ignore",
                "admin.txt",
                "admin.local.txt",
                "last_price_state.json",
            ],
            cwd=ROOT,
            check=True,
            text=True,
            capture_output=True,
        )

        self.assertEqual(
            result.stdout.splitlines(),
            ["admin.txt", "admin.local.txt", "last_price_state.json"],
        )


if __name__ == "__main__":
    unittest.main()
