import ast
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class MainEntrypointTests(unittest.TestCase):
    def test_entrypoint_does_not_run_stale_chart_tail(self):
        tree = ast.parse((REPO_ROOT / "main.py").read_text())

        main_guards = [
            node
            for node in tree.body
            if isinstance(node, ast.If) and self._is_main_guard(node.test)
        ]

        self.assertEqual(len(main_guards), 1)
        guard_body = main_guards[0].body
        self.assertEqual(len(guard_body), 1)
        self.assertTrue(self._is_main_call(guard_body[0]))

    def _is_main_guard(self, test):
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

    def _is_main_call(self, node):
        return (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id == "main"
        )


class GitignoreTests(unittest.TestCase):
    def test_local_secret_and_state_files_remain_ignored(self):
        ignored_paths = {
            line.strip()
            for line in (REPO_ROOT / ".gitignore").read_text().splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }

        self.assertTrue(
            {
                "admin.txt",
                "admin.local.txt",
                "last_price_state.json",
                "EnergyScraper.py",
                "LegacyTerminal/",
                "INTERVIEW_TALKING_POINTS.md",
            }.issubset(ignored_paths)
        )


if __name__ == "__main__":
    unittest.main()
