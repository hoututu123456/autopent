import os
import unittest


class ReportDownloadTests(unittest.TestCase):
    def test_report_download_md_html_pdf(self):
        from fastapi.testclient import TestClient
        from src.api import server

        report_dir = os.path.join(server.BASE_DIR, "data", "reports")
        os.makedirs(report_dir, exist_ok=True)

        base = "download_test_report"
        md_path = os.path.join(report_dir, f"{base}.md")
        pdf_path = os.path.join(report_dir, f"{base}.pdf")

        try:
            with open(md_path, "w", encoding="utf-8") as f:
                f.write("# 标题\n\n内容\n")
            with open(pdf_path, "wb") as f:
                f.write(b"%PDF-1.4\n%autopentestai\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n")

            client = TestClient(server.app)

            r1 = client.get("/api/reports/download", params={"name": base, "format": "md"})
            self.assertEqual(r1.status_code, 200)
            self.assertIn("attachment", (r1.headers.get("content-disposition") or "").lower())

            r2 = client.get("/api/reports/download", params={"name": base, "format": "html"})
            self.assertEqual(r2.status_code, 200)
            self.assertIn("text/html", (r2.headers.get("content-type") or "").lower())

            r3 = client.get("/api/reports/download", params={"name": base, "format": "pdf"})
            self.assertEqual(r3.status_code, 200)
            self.assertIn("application/pdf", (r3.headers.get("content-type") or "").lower())
        finally:
            for p in (md_path, pdf_path, os.path.join(report_dir, f"{base}.html")):
                try:
                    os.remove(p)
                except Exception:
                    pass

