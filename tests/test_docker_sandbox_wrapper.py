import os
import shutil
import tempfile
import unittest


class _FakeToolManager:
    def __init__(self, tool_def):
        self._tool_def = tool_def

    def get_tool(self, name):
        if name == self._tool_def.get("name"):
            return self._tool_def
        return None


class DockerSandboxWrapperTests(unittest.TestCase):
    def test_wrap_with_docker_builds_command(self):
        if os.name == "nt":
            self.skipTest("Windows 环境不启用 docker 沙箱封装测试")
        from src.tools.executor import ToolExecutor

        base_dir = tempfile.mkdtemp(prefix="autopentestai_")
        try:
            tool_def = {"name": "t", "command": "echo", "sandbox": "docker", "docker_image": "kali:latest"}
            tm = _FakeToolManager(tool_def)
            ex = ToolExecutor(tm, base_dir=base_dir)

            cmd, cidfile = ex._wrap_with_docker(["echo", "hi"], tool_def=tool_def, cwd=base_dir, task_id="x")  # type: ignore
            self.assertTrue(isinstance(cmd, list))
            self.assertGreater(len(cmd), 5)
            self.assertEqual(cmd[0], "docker")
            self.assertIn("run", cmd)
            self.assertIn("kali:latest", cmd)
            self.assertTrue(cidfile and cidfile.endswith(".cid"))
        finally:
            shutil.rmtree(base_dir, ignore_errors=True)
