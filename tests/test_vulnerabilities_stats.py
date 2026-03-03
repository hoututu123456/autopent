import unittest


class VulnerabilitiesStatsTests(unittest.TestCase):
    def test_vulnerabilities_stats_shape(self):
        from fastapi.testclient import TestClient
        from src.api import server

        client = TestClient(server.app)
        r = client.get("/api/vulnerabilities/stats")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("exploitdb_available", data)
        self.assertIn("exploitdb_total", data)
        self.assertIn("sources", data)

