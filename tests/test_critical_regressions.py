import ast
import subprocess
from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]


class MainEntrypointTests(unittest.TestCase):
    def test_main_guard_only_calls_main(self):
        tree = ast.parse((REPO_ROOT / "main.py").read_text(), filename="main.py")

        guard_index = next(
            i
            for i, node in enumerate(tree.body)
            if isinstance(node, ast.If)
            and isinstance(node.test, ast.Compare)
            and isinstance(node.test.left, ast.Name)
            and node.test.left.id == "__name__"
        )
        guard = tree.body[guard_index]

        self.assertEqual(len(guard.body), 1)
        self.assertIsInstance(guard.body[0], ast.Expr)
        call = guard.body[0].value
        self.assertIsInstance(call, ast.Call)
        self.assertIsInstance(call.func, ast.Name)
        self.assertEqual(call.func.id, "main")

        executable_tail = [
            node
            for node in tree.body[guard_index + 1 :]
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        ]
        self.assertEqual(executable_tail, [])


class GitignoreTests(unittest.TestCase):
    def test_local_secrets_and_runtime_state_are_ignored(self):
        required_ignored_paths = {
            "admin.txt",
            "admin.local.txt",
            "last_price_state.json",
            "EnergyScraper.py",
            "LegacyTerminal/file.py",
            "INTERVIEW_TALKING_POINTS.md",
        }

        result = subprocess.run(
            ["git", "check-ignore", "--stdin"],
            cwd=REPO_ROOT,
            input="\n".join(sorted(required_ignored_paths)),
            text=True,
            capture_output=True,
            check=False,
        )

        ignored_paths = set(result.stdout.splitlines())
        self.assertEqual(required_ignored_paths, ignored_paths, result.stderr)


if __name__ == "__main__":
    unittest.main()
