import os
import shutil
import tempfile
import unittest


class VulnStoreAndApiTests(unittest.TestCase):
    def test_vuln_store_roundtrip(self):
        from src.utils.vuln_store import VulnStore

        tmp = tempfile.mkdtemp(prefix="autopentestai_")
        try:
            store = VulnStore(tmp)
            v = store.upsert(
                {
                    "task_id": "t",
                    "target": "example.com",
                    "title": "SQL Injection",
                    "severity": "高危",
                    "cvss": 8.8,
                    "status": "open",
                    "details": {"affected": "/a", "evidence": "ok"},
                }
            )
            got = store.get(v["vuln_id"])
            self.assertIsNotNone(got)
            self.assertEqual(got["title"], "SQL Injection")
            self.assertEqual(got["severity"], "高危")
            items = store.list(task_id="t")
            self.assertTrue(any(x["vuln_id"] == v["vuln_id"] for x in items))
            self.assertTrue(store.delete(v["vuln_id"]))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_vuln_api_upsert_list_delete(self):
        from fastapi.testclient import TestClient
        from src.api import server

        client = TestClient(server.app)

        payload = {
            "task_id": "t",
            "target": "example.com",
            "title": "Command Injection",
            "severity": "严重",
            "cvss": 9.8,
            "status": "open",
            "details": {"affected": "/ping", "principle": "input to shell", "evidence": "id=0", "impact": "RCE", "remediation": "sanitize"},
        }

        r1 = client.post("/api/vulns", json=payload)
        self.assertEqual(r1.status_code, 200)
        vid = r1.json().get("vuln_id")
        self.assertTrue(vid)

        r2 = client.get("/api/vulns?task_id=t")
        self.assertEqual(r2.status_code, 200)
        self.assertTrue(any(v.get("vuln_id") == vid for v in r2.json().get("vulns", [])))

        r3 = client.get(f"/api/vulns/{vid}")
        self.assertEqual(r3.status_code, 200)

        r4 = client.delete(f"/api/vulns/{vid}")
        self.assertEqual(r4.status_code, 200)

