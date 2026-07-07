import ast
import subprocess
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class MainEntrypointTests(unittest.TestCase):
    def test_main_guard_only_calls_main(self):
        tree = ast.parse((REPO_ROOT / "main.py").read_text())
        main_guards = [
            node
            for node in tree.body
            if isinstance(node, ast.If)
            and isinstance(node.test, ast.Compare)
            and ast.unparse(node.test) == "__name__ == '__main__'"
        ]

        self.assertEqual(len(main_guards), 1)
        self.assertEqual(len(main_guards[0].body), 1)
        self.assertEqual(ast.unparse(main_guards[0].body[0]), "main()")

    def test_deleted_sample_csvs_are_not_read_after_main_returns(self):
        tree = ast.parse((REPO_ROOT / "main.py").read_text())
        main_guard = next(
            node
            for node in tree.body
            if isinstance(node, ast.If)
            and isinstance(node.test, ast.Compare)
            and ast.unparse(node.test) == "__name__ == '__main__'"
        )

        stale_csv_reads = [
            call
            for call in ast.walk(main_guard)
            if isinstance(call, ast.Call)
            and isinstance(call.func, ast.Attribute)
            and call.func.attr == "read_csv"
        ]
        self.assertEqual(stale_csv_reads, [])


class GitIgnoreTests(unittest.TestCase):
    def test_local_secret_and_state_files_are_ignored(self):
        paths = ["admin.txt", "admin.local.txt", "last_price_state.json"]
        result = subprocess.run(
            ["git", "check-ignore", *paths],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=True,
        )

        self.assertEqual(result.stdout.splitlines(), paths)


if __name__ == "__main__":
    unittest.main()
