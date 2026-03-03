import os
import tempfile
import unittest


class BinaryTriageScriptTests(unittest.TestCase):
    def test_binary_triage_produces_sha256(self):
        import subprocess

        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        script = os.path.join(base_dir, "scripts", "binary_triage.py")

        fd, path = tempfile.mkstemp(prefix="autopentestai_bin_", suffix=".bin")
        os.close(fd)
        try:
            with open(path, "wb") as f:
                f.write(b"\x7fELF" + b"\x00" * 64)

            out = subprocess.check_output(["python", script, "--file", path], text=True, errors="replace")
            self.assertIn("SHA256:", out)
        finally:
            try:
                os.remove(path)
            except Exception:
                pass

