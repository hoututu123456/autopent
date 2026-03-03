import unittest


class ImportScanResultsTests(unittest.TestCase):
    def test_import_fscan_184_creates_vuln(self):
        from fastapi.testclient import TestClient
        from src.api import server

        client = TestClient(server.app)

        content = "[+] Redis:10.0.0.1:6379 unauthorized\n"
        r = client.post("/api/import/scan-results", json={"filename": "fscan.txt", "content": content, "commit": True})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data.get("parser"), "fscan-1.8.4")
        created = data.get("created") or []
        self.assertEqual(len(created), 1)

        vid = created[0]
        g = client.get(f"/api/vulns/{vid}")
        self.assertEqual(g.status_code, 200)
        self.assertIn("Redis", g.json().get("title", ""))

        d = client.delete(f"/api/vulns/{vid}")
        self.assertEqual(d.status_code, 200)

    def test_import_lightx_preview(self):
        from fastapi.testclient import TestClient
        from src.api import server

        client = TestClient(server.app)

        content = "[2025-12-14 21:00:31] [Plugin:MySQL:SUCCESS] MySQL:127.0.0.1:3306 root/root\n"
        r = client.post("/api/import/scan-results", json={"filename": "lightx.txt", "content": content, "commit": False})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data.get("parser"), "lightx")
        self.assertEqual(len(data.get("findings") or []), 1)

    def test_import_commit_findings(self):
        from fastapi.testclient import TestClient
        from src.api import server

        client = TestClient(server.app)

        content = "[+] Redis:10.0.0.2:6379 unauthorized\n[+] MySQL:10.0.0.2:3306 root:root\n"
        preview = client.post("/api/import/scan-results", json={"filename": "fscan.txt", "content": content, "commit": False}).json()
        findings = preview.get("findings") or []
        self.assertTrue(len(findings) >= 2)

        picked = [findings[0]]
        r = client.post("/api/import/commit-findings", json={"findings": picked, "target": "10.0.0.2", "task_id": "10.0.0.2"})
        self.assertEqual(r.status_code, 200)
        created = r.json().get("created") or []
        self.assertEqual(len(created), 1)

        vid = created[0]
        g = client.get(f"/api/vulns/{vid}")
        self.assertEqual(g.status_code, 200)
        client.delete(f"/api/vulns/{vid}")
