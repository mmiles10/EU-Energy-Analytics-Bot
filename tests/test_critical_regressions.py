import ast
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import sys
import types
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]


class CriticalRegressionTests(unittest.TestCase):
    def test_main_entrypoint_only_calls_main(self):
        tree = ast.parse((REPO_ROOT / "main.py").read_text())
        entrypoints = [
            node
            for node in tree.body
            if isinstance(node, ast.If)
            and isinstance(node.test, ast.Compare)
            and isinstance(node.test.left, ast.Name)
            and node.test.left.id == "__name__"
        ]

        self.assertEqual(len(entrypoints), 1)
        self.assertEqual(len(entrypoints[0].body), 1)
        call = entrypoints[0].body[0]
        self.assertIsInstance(call, ast.Expr)
        self.assertIsInstance(call.value, ast.Call)
        self.assertIsInstance(call.value.func, ast.Name)
        self.assertEqual(call.value.func.id, "main")

    def test_local_secret_and_state_files_are_ignored(self):
        for path in ("admin.txt", "admin.local.txt", "last_price_state.json"):
            with self.subTest(path=path):
                result = subprocess.run(
                    ["git", "check-ignore", "--quiet", path],
                    cwd=REPO_ROOT,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, f"{path} is not ignored")

    def test_send_telegram_chat_id_helper_formats_message_time(self):
        class FakeResponse:
            def json(self):
                return {
                    "ok": True,
                    "result": [
                        {
                            "message": {
                                "chat": {"id": 12345},
                                "from": {"first_name": "Test", "username": "tester"},
                                "text": "hello",
                                "date": 1_700_000_000,
                            }
                        }
                    ],
                }

        fake_requests = types.SimpleNamespace(get=lambda url: FakeResponse())
        fake_dotenv = types.SimpleNamespace(load_dotenv=lambda: None)
        old_requests = sys.modules.get("requests")
        old_dotenv = sys.modules.get("dotenv")
        old_token = os.environ.get("TELEGRAM_TOKEN")
        module_name = "_send_telegram_regression"

        try:
            sys.modules["requests"] = fake_requests
            sys.modules["dotenv"] = fake_dotenv
            os.environ["TELEGRAM_TOKEN"] = "dummy-token"

            spec = importlib.util.spec_from_file_location(
                module_name, REPO_ROOT / "send_telegram.py"
            )
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(module.get_chat_id(), 12345)
        finally:
            sys.modules.pop(module_name, None)
            if old_requests is None:
                sys.modules.pop("requests", None)
            else:
                sys.modules["requests"] = old_requests
            if old_dotenv is None:
                sys.modules.pop("dotenv", None)
            else:
                sys.modules["dotenv"] = old_dotenv
            if old_token is None:
                os.environ.pop("TELEGRAM_TOKEN", None)
            else:
                os.environ["TELEGRAM_TOKEN"] = old_token


if __name__ == "__main__":
    unittest.main()
