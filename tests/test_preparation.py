import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from contextlib import contextmanager

from hss.layout import Layout
from hss.manager import Manager
from hss.mcp import dispatch
from hss.preparation import Tasks, partial_result


@contextmanager
def workspace():
    directory = tempfile.TemporaryDirectory()
    try:
        yield directory.name
    finally:
        deadline = time.monotonic() + 5
        while True:
            try:
                directory.cleanup()
                break
            except PermissionError:
                if os.name != "nt" or time.monotonic() >= deadline:
                    raise
                time.sleep(.02)


class PreparationTests(unittest.TestCase):
    def test_request_lifetime_negotiates_tasks_and_preserves_reconnection(self):
        from hss.mcp import CONNECTION_LIFECYCLE
        initialize = {"protocolVersion": "2025-11-25", "capabilities": {
            "experimental": {CONNECTION_LIFECYCLE: {"scope": "request"}}}}
        for params in ({"protocolVersion": "2025-11-25"},
                       {**initialize, "protocolVersion": "2025-06-18"}):
            self.assertNotIn("experimental", dispatch("initialize", params)["capabilities"])
        with workspace() as tmp:
            env = {**os.environ, "HSS_RESEARCH_SPACE": tmp}
            arguments = {"selections": ["concept-analysis"], "software": False}
            messages = [
                {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": initialize},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                 "params": {"name": "hss_prepare", "arguments": arguments}},
                {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                 "params": {"name": "hss_prepare", "arguments": arguments, "task": {}}},
            ]
            process = subprocess.run([sys.executable, "-m", "hss", "serve"],
                                     input="".join(json.dumps(value) + "\n" for value in messages),
                                     text=True, capture_output=True, check=True, env=env, timeout=10)
            replies = [json.loads(line) for line in process.stdout.splitlines()]
            self.assertEqual(replies[0]["result"]["capabilities"]["experimental"][CONNECTION_LIFECYCLE], {"scope": "request"})
            self.assertEqual(replies[1]["error"]["code"], -32602)
            task_id = replies[2]["result"]["task"]["taskId"]
            resumed = [messages[0], {"jsonrpc": "2.0", "id": 4, "method": "tasks/result", "params": {"taskId": task_id}}]
            process = subprocess.run([sys.executable, "-m", "hss", "serve"],
                                     input="".join(json.dumps(value) + "\n" for value in resumed),
                                     text=True, capture_output=True, check=True, env=env, timeout=10)
            value = next(json.loads(line)["result"] for line in process.stdout.splitlines() if json.loads(line)["id"] == 4)
            self.assertFalse(value["isError"])
            self.assertEqual(value["_meta"]["io.modelcontextprotocol/related-task"]["taskId"], task_id)
            self.assertTrue(Path(tmp, "System/skills/hss-theory/SKILL.md").is_file())

    def test_task_result_survives_mcp_process_exit(self):
        with workspace() as tmp:
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
        with workspace() as tmp:
            m = Manager(tmp)
            with patch("hss.software.find_existing", return_value=None):
                m.prepare(["prediction"], software_enabled=False)
            installed = m.installed()
            self.assertIn("prediction", installed["modules"])
            self.assertNotIn("prediction", installed["ready_modules"])
            self.assertTrue(installed["pending"])

    def test_existing_home_is_preserved_and_new_layout_is_short(self):
        with workspace() as tmp:
            root = Path(tmp).resolve()
            new = Layout(root)
            self.assertEqual(new.component_root("solver"), root / "System/software/hss/solver")
            legacy = root / "System/env/hss"
            legacy.mkdir(parents=True)
            old = Layout(root)
            self.assertEqual(old["env"], legacy)
            self.assertEqual(old.component_root("solver"), legacy / "software/solver")

    def test_cancel_waiting_preparation_retains_completed_material(self):
        from hss.process import lock
        with workspace() as tmp, patch.dict(os.environ, {"HSS_RESEARCH_SPACE": tmp}):
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
        with workspace() as tmp, patch.dict(os.environ, {"HSS_RESEARCH_SPACE": tmp}):
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

    def test_cancelled_result_links_existing_material(self):
        with workspace() as tmp:
            m = Manager(tmp)
            m.prepare(["concept-analysis"], software_enabled=False)
            result = partial_result({"space": tmp, "selections": ["concept-analysis"]}, "Cancelled", True)
            self.assertTrue(result["assets"])
            self.assertTrue(all(Path(path).is_file() for path in result["assets"]))

    @unittest.skipIf(os.name == "nt", "Unix compiler fixture")
    def test_compiler_failure_is_concise_with_real_output_log(self):
        with workspace() as tmp, patch.dict(os.environ, {"HSS_RESEARCH_SPACE": tmp}):
            compiler = Path(tmp) / "compiler"
            compiler.write_text("#!/bin/sh\necho 'invalid source fixture' >&2\nexit 23\n")
            compiler.chmod(0o700)
            tasks = Tasks()
            task = tasks.start({"selections": ["corpus-assembly"], "backends": {"corpus-assembly": "rust"},
                                "options": {"rustc": str(compiler)}})["task"]["taskId"]
            value = tasks.result(task)["structuredContent"]
            self.assertEqual(value["failed"][0]["error"], "compiler exited with status 23")
            self.assertEqual(value["failed"][0]["exit_code"], 23)
            self.assertIn("invalid source fixture", Path(value["log"]).read_text())


if __name__ == "__main__":
    unittest.main()
