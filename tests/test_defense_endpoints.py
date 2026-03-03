import unittest


class DefenseEndpointsTests(unittest.TestCase):
    def test_defense_endpoints_empty_ok(self):
        from fastapi.testclient import TestClient
        from src.api import server

        client = TestClient(server.app)

        r1 = client.get("/api/defense/repos")
        self.assertEqual(r1.status_code, 200)
        self.assertIn("repos", r1.json())

        r2 = client.get("/api/defense/search?q=APT&limit=2")
        self.assertEqual(r2.status_code, 200)
        self.assertIn("results", r2.json())

        r3 = client.get("/api/mitre/search?q=T1059&limit=2")
        self.assertEqual(r3.status_code, 200)
        self.assertIn("results", r3.json())

        r4 = client.get("/api/sigma/search?q=T1059&limit=2")
        self.assertEqual(r4.status_code, 200)
        self.assertIn("results", r4.json())

