import ast
import fnmatch
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class MainEntrypointTests(unittest.TestCase):
    def test_main_guard_only_invokes_main(self):
        tree = ast.parse((REPO_ROOT / "main.py").read_text())
        guards = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.If)
            and isinstance(node.test, ast.Compare)
            and isinstance(node.test.left, ast.Name)
            and node.test.left.id == "__name__"
        ]

        self.assertEqual(len(guards), 1)
        guard = guards[0]
        self.assertEqual(len(guard.body), 1)
        self.assertIsInstance(guard.body[0], ast.Expr)
        call = guard.body[0].value
        self.assertIsInstance(call, ast.Call)
        self.assertIsInstance(call.func, ast.Name)
        self.assertEqual(call.func.id, "main")


class GitignoreTests(unittest.TestCase):
    def test_local_secret_and_state_files_remain_ignored(self):
        patterns = [
            line.strip()
            for line in (REPO_ROOT / ".gitignore").read_text().splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]

        for path in ("admin.txt", "admin.local.txt", "last_price_state.json"):
            with self.subTest(path=path):
                self.assertTrue(
                    any(fnmatch.fnmatch(path, pattern) for pattern in patterns),
                    f"{path} must remain ignored",
                )


if __name__ == "__main__":
    unittest.main()
