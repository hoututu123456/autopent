import unittest


class SystemMetricsTests(unittest.TestCase):
    def test_system_metrics_endpoint(self):
        from fastapi.testclient import TestClient
        from src.api import server

        client = TestClient(server.app)
        r = client.get("/api/system/metrics")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("available", data)
        self.assertIn("disk", data)
        self.assertIn("timestamp", data)

