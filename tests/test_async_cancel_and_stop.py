import os
import threading
import time
import unittest


class _FakeToolManager:
    def __init__(self, tool_def):
        self._tool_def = tool_def

    def get_tool(self, name):
        if name == self._tool_def.get("name"):
            return self._tool_def
        return None


class AsyncCancelAndStopTests(unittest.TestCase):
    def test_tool_executor_cancel_stops_long_process(self):
        from src.tools.executor import ToolExecutor

        tool_def = {
            "name": "python_sleep",
            "command": "python",
            "args": ["-c"],
            "timeout_seconds": 900,
            "parameters": [
                {
                    "name": "script",
                    "type": "string",
                    "required": True,
                    "position": 0,
                    "format": "positional",
                }
            ],
        }

        tm = _FakeToolManager(tool_def)
        ex = ToolExecutor(tm, base_dir=None)

        result_holder = {}

        def _run():
            stdout, stderr, code = ex.execute(
                "python_sleep",
                {"script": "import time; time.sleep(60)"},
                task_id="t1",
            )
            result_holder["stdout"] = stdout
            result_holder["stderr"] = stderr
            result_holder["code"] = code

        t = threading.Thread(target=_run)
        start = time.time()
        t.start()
        time.sleep(0.8)
        cancelled = ex.cancel("t1")
        self.assertTrue(cancelled)
        t.join(timeout=6)
        self.assertFalse(t.is_alive())
        self.assertIn(result_holder.get("code"), (-2, -1))
        self.assertLess(time.time() - start, 10)

    def test_scan_stop_accepts_query_or_json_body(self):
        os.environ.setdefault("DEEPSEEK_API_KEY", "sk-test")

        from fastapi.testclient import TestClient
        from src.api import server

        client = TestClient(server.app)

        server.active_tasks["t"] = {
            "agent": None,
            "listeners": [],
            "status": "running",
            "history": [],
            "bg_task": None,
        }

        r1 = client.post("/api/scan/stop?target=t")
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r1.json().get("ok"), True)

        server.active_tasks["t2"] = {
            "agent": None,
            "listeners": [],
            "status": "running",
            "history": [],
            "bg_task": None,
        }

        r2 = client.post("/api/scan/stop", json={"target": "t2"})
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.json().get("ok"), True)

