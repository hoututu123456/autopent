import os
import tempfile
import unittest


class CodeAuditScriptTests(unittest.TestCase):
    def test_code_audit_finds_obvious_issues(self):
        import subprocess

        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        script = os.path.join(base_dir, "scripts", "code_audit.py")

        tmp = tempfile.mkdtemp(prefix="autopentestai_code_audit_")
        try:
            p = os.path.join(tmp, "a.py")
            with open(p, "w", encoding="utf-8") as f:
                f.write('import subprocess\nsubprocess.run("id", shell=True)\n')

            out = subprocess.check_output(
                ["python", script, "--path", tmp, "--min-severity", "high", "--format", "json"],
                text=True,
                errors="replace",
            )
            self.assertIn("PY.SUBPROCESS_SHELL_TRUE", out)
        finally:
            try:
                for fn in os.listdir(tmp):
                    os.remove(os.path.join(tmp, fn))
                os.rmdir(tmp)
            except Exception:
                pass

