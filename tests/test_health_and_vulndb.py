import unittest


class HealthAndVulnDbTests(unittest.TestCase):
    def test_health_endpoint_shape(self):
        from fastapi.testclient import TestClient
        from src.api import server

        client = TestClient(server.app)
        r = client.get("/api/health")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("ok", data)
        self.assertIn("rag_available", data)
        self.assertIn("searchsploit_available", data)
        self.assertIn("db_writable", data)
        self.assertIn("warnings", data)

    def test_vulndb_list_contains_notes(self):
        from fastapi.testclient import TestClient
        from src.api import server

        client = TestClient(server.app)
        r = client.get("/api/vulndb")
        self.assertEqual(r.status_code, 200)
        items = r.json().get("vulndb", [])
        names = [x.get("name") for x in items if isinstance(x, dict)]
        self.assertIn("CVE-2021-44228.md", names)

