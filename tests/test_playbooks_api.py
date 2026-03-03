import os
import unittest


class PlaybooksApiTests(unittest.TestCase):
    def test_playbooks_list_and_create(self):
        from fastapi.testclient import TestClient
        from src.api import server

        client = TestClient(server.app)

        name = "demo_playbook.md"
        content = "# Demo Playbook\n\n仅用于验证与排障。\n"

        r = client.post("/api/playbooks", json={"filename": name, "content": content})
        self.assertEqual(r.status_code, 200)

        r2 = client.get("/api/playbooks")
        self.assertEqual(r2.status_code, 200)
        items = r2.json().get("playbooks") or []
        names = [x.get("name") for x in items if isinstance(x, dict)]
        self.assertIn(name, names)

        pb_path = os.path.join(server.BASE_DIR, "data", "playbooks", name)
        try:
            os.remove(pb_path)
        except Exception:
            pass

