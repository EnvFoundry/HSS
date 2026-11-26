import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from hss.layout import Layout
from hss.manager import Manager
from hss.mcp import dispatch
from hss.preparation import Tasks


class PreparationTests(unittest.TestCase):
    def test_task_result_survives_mcp_process_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {**os.environ, "HSS_RESEARCH_SPACE": tmp}
            message = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                       "params": {"name": "hss_prepare", "task": {},
                                  "arguments": {"selections": ["concept-analysis"], "software": False}}}
            result = subprocess.run([sys.executable, "-m", "hss", "serve"],
                                    input=json.dumps(message) + "\n", text=True,
                                    capture_output=True, check=True, env=env)
            task = json.loads(result.stdout)["result"]["task"]["taskId"]
            message.update(id=2, method="tasks/result", params={"taskId": task})
            result = subprocess.run([sys.executable, "-m", "hss", "serve"],
                                    input=json.dumps(message) + "\n", text=True,
                                    capture_output=True, check=True, env=env, timeout=10)
            value = json.loads(result.stdout)["result"]
            self.assertFalse(value["isError"])
            self.assertTrue(Path(tmp, "System/skills/hss-theory/SKILL.md").is_file())
            self.assertEqual(value["_meta"]["io.modelcontextprotocol/related-task"]["taskId"], task)
            with patch.dict(os.environ, {"HSS_RESEARCH_SPACE": tmp}):
                with self.assertRaises(ValueError):
                    dispatch("tasks/cancel", {"taskId": task})

    def test_software_pending_does_not_mark_module_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            m = Manager(tmp)
            with patch("hss.software.find_existing", return_value=None):
                m.prepare(["prediction"], software_enabled=False)
            installed = m.installed()
            self.assertIn("prediction", installed["modules"])
            self.assertNotIn("prediction", installed["ready_modules"])
            self.assertTrue(installed["pending"])

    def test_existing_home_is_preserved_and_new_layout_is_short(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            new = Layout(root)
            self.assertEqual(new.component_root("solver"), root / "System/software/hss/solver")
            legacy = root / "System/env/hss"
            legacy.mkdir(parents=True)
            old = Layout(root)
            self.assertEqual(old["env"], legacy)
            self.assertEqual(old.component_root("solver"), legacy / "software/solver")

    def test_cancel_waiting_preparation_retains_completed_material(self):
        from hss.process import lock
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"HSS_RESEARCH_SPACE": tmp}):
            m = Manager(tmp)
            m.prepare(["concept-analysis"], software_enabled=False)
            tasks = Tasks()
            with lock(m.layout["env"] / "prepare.lock"):
                task = tasks.start({"selections": ["prediction"], "software": False})["task"]["taskId"]
                limit = time.monotonic() + 5
                while not tasks.row(task)["started_at"] and time.monotonic() < limit:
                    time.sleep(.05)
                self.assertEqual(tasks.cancel(task)["status"], "cancelled")
            self.assertIn("concept-analysis", m.installed()["ready_modules"])
            self.assertNotIn("prediction", m.installed()["modules"])

    def test_failed_prepare_retains_its_error_and_partial_result(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"HSS_RESEARCH_SPACE": tmp}):
            tasks = Tasks()
            task = tasks.start({"selections": ["corpus-assembly"],
                                "backends": {"corpus-assembly": "rust"},
                                "options": {"rustc": str(Path(tmp) / "missing-compiler")}})["task"]["taskId"]
            result = tasks.result(task)
            status = tasks.get(task)
            self.assertEqual(status["status"], "failed")
            self.assertIn("missing-compiler", status["statusMessage"])
            self.assertTrue(result["isError"])
            self.assertEqual(result["structuredContent"]["failed"][0]["component"], "native-corpus")


if __name__ == "__main__":
    unittest.main()
