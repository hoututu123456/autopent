import os
import shutil
import tempfile
import unittest


class TaskStoreAndReportTests(unittest.TestCase):
    def test_task_store_persists_events(self):
        from src.utils.task_store import TaskStore

        tmp = tempfile.mkdtemp(prefix="autopentestai_")
        try:
            store = TaskStore(tmp)
            store.upsert_task("t1", goal="g", status="running")
            store.append_event("t1", {"type": "log", "content": "a"})
            store.append_event("t1", {"type": "log", "content": "b"})
            store.mark_finished("t1", status="finished")

            t = store.get_task("t1")
            self.assertIsNotNone(t)
            self.assertEqual(t["status"], "finished")

            events = store.load_events("t1")
            self.assertEqual(len(events), 2)
            self.assertEqual(events[0]["content"], "a")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_report_renderer_generates_html(self):
        from src.utils.report_renderer import render_report_html

        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        html = render_report_html(
            base_dir=base_dir,
            markdown_text="# 标题\n\n## 小节\n\n内容\n\nT1059\n\nCVE-2021-44228\n\n```bash\necho hi\n```",
            filename="demo.md",
            target="example.com",
        )
        self.assertIn("<html", html.lower())
        self.assertIn("example.com", html)
        self.assertIn("echo hi", html)
        self.assertIn("T1059", html)
        self.assertIn("CVE-2021-44228", html)
