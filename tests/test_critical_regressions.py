import ast
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class MainEntrypointTests(unittest.TestCase):
    def test_main_entrypoint_only_calls_main(self):
        tree = ast.parse((ROOT / "main.py").read_text())
        entrypoints = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.If) and ast.unparse(node.test) == "__name__ == '__main__'"
        ]

        self.assertEqual(len(entrypoints), 1)
        self.assertEqual(len(entrypoints[0].body), 1)

        entrypoint_call = entrypoints[0].body[0]
        self.assertIsInstance(entrypoint_call, ast.Expr)
        self.assertIsInstance(entrypoint_call.value, ast.Call)
        self.assertIsInstance(entrypoint_call.value.func, ast.Name)
        self.assertEqual(entrypoint_call.value.func.id, "main")


class GitignoreTests(unittest.TestCase):
    def test_local_secret_and_state_files_are_ignored(self):
        paths = ["admin.txt", "admin.local.txt", "last_price_state.json"]
        result = subprocess.run(
            ["git", "check-ignore", *paths],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), paths)


if __name__ == "__main__":
    unittest.main()
