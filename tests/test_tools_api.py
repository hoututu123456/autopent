import unittest


class ToolsApiTests(unittest.TestCase):
    def test_tools_endpoint_marks_enabled_tools_runnable(self):
        from fastapi.testclient import TestClient
        from src.api import server

        client = TestClient(server.app)
        r = client.get("/api/tools")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        tools = data.get("tools", [])
        self.assertTrue(isinstance(tools, list) and len(tools) > 10)

        names = [t.get("name") for t in tools if isinstance(t, dict)]
        self.assertIn("nmap", names)

        for t in tools:
            if not isinstance(t, dict):
                continue
            if t.get("enabled", True) is False:
                continue
            if t.get("internal"):
                continue
            self.assertTrue(t.get("agent_allowed") is True)

