import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone

from .layout import Layout
from .process import Cancelled, check_cancel, lock
from .state import State


TERMINAL = {"completed", "failed", "cancelled"}


def timestamp():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def tool_result(value, error=False):
    return {"content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False, allow_nan=False)}],
            "structuredContent": value, "isError": error}


def partial_result(arguments, error, cancelled=False):
    from .catalog import Catalog
    from .manager import Manager
    manager = Manager(arguments.get("space"), arguments.get("layout"), Catalog(arguments.get("extension")))
    modules = manager.catalog.select(arguments.get("selections", []))
    components = set(manager.components(modules, arguments.get("backends")))
    installed = manager.installed()
    ready = [item for item in installed["ready"] if item["component"] in components]
    return {"modules": modules, "ready": ready, "pending": [
                {"component": name, "status": "not_prepared"}
                for name in sorted(components - {item["component"] for item in ready})],
            "failed": [] if cancelled else [{"error": str(error)}],
            "assets": sorted({row["path"] for row in manager.state.rows("assets")
                              if row["module"] in modules and Path(row["path"]).is_file()}),
            "error": str(error), "cancelled": cancelled, "layout": manager.layout.describe()}


class Tasks:
    def __init__(self, root=None):
        self.root = Path(root) if root is not None else Layout()["env"]
        self.state = State(self.root / "registry.sqlite")

    def folder(self, task_id):
        if not isinstance(task_id, str) or len(task_id) != 32 or any(c not in "0123456789abcdef" for c in task_id):
            raise ValueError("Unknown preparation task")
        return self.root / "preparations" / task_id

    def row(self, task_id):
        self.folder(task_id)
        if not self.state.path.exists():
            raise ValueError("Unknown preparation task")
        with sqlite3.connect(self.state.path.as_uri() + "?mode=ro", uri=True) as con:
            con.row_factory = sqlite3.Row
            try:
                row = con.execute("SELECT * FROM preparations WHERE id=?", (task_id,)).fetchone()
            except sqlite3.OperationalError as error:
                raise ValueError("Unknown preparation task") from error
        if row is None:
            raise ValueError("Unknown preparation task")
        return dict(row)

    def update(self, task_id, status, result=None, message=None):
        with self.state.connection() as con:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute("SELECT cancel_requested FROM preparations WHERE id=? AND status='working'", (task_id,)).fetchone()
            if row is None:
                return
            if row[0] and status in TERMINAL:
                status = "cancelled"
                message = "Preparation cancelled; completed resources are retained"
                result = {**(result or tool_result({"error": message}, True)), "cancelled": True}
            con.execute("UPDATE preparations SET status=?,result=?,message=?,updated_at=? WHERE id=? AND status='working'",
                        (status, json.dumps(result) if result is not None else None, message, timestamp(), task_id))

    def start(self, arguments):
        from .catalog import Catalog
        Catalog(arguments.get("extension")).select(arguments.get("selections", []))
        task_id = uuid.uuid4().hex
        now = timestamp()
        folder = self.folder(task_id)
        folder.mkdir(parents=True)
        with self.state.connection() as con:
            con.execute("INSERT INTO preparations(id,status,request,created_at,updated_at) VALUES (?,'working',?,?,?)",
                        (task_id, json.dumps(arguments), now, now))
        initial = self.describe(self.row(task_id))
        env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parent.parent)}
        options = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS} if os.name == "nt" else {"start_new_session": True}
        try:
            with (folder / "output.log").open("wb") as output:
                child = subprocess.Popen([sys.executable, "-m", "hss.preparation", str(self.root), task_id],
                                         stdin=subprocess.DEVNULL, stdout=output, stderr=output, env=env, **options)
            threading.Thread(target=child.wait, daemon=True).start()
        except OSError as error:
            self.update(task_id, "failed", tool_result({"error": str(error)}, True), str(error))
            raise
        return {"task": initial}

    @staticmethod
    def describe(row):
        value = {"taskId": row["id"], "status": row["status"], "createdAt": row["created_at"],
                 "lastUpdatedAt": row["updated_at"], "ttl": None, "pollInterval": 1000}
        if row["message"]:
            value["statusMessage"] = row["message"]
        return value

    def get(self, task_id):
        row = self.row(task_id)
        if row["status"] == "working":
            with lock(self.folder(task_id) / "worker.lock", blocking=False) as available:
                age = time.time() - datetime.fromisoformat(row["created_at"].replace("Z", "+00:00")).timestamp()
                if available and (row["started_at"] or age > 30):
                    message = "Preparation worker stopped; completed resources are retained. Prepare the remaining selection again."
                    self.update(task_id, "failed", tool_result({"error": message}, True), message)
            row = self.row(task_id)
        return self.describe(row)

    def result(self, task_id):
        while self.get(task_id)["status"] not in TERMINAL:
            time.sleep(.1)
        row = self.row(task_id)
        result = json.loads(row["result"]) if row["result"] else tool_result({"error": row["message"] or row["status"]}, True)
        return {**result, "_meta": {"io.modelcontextprotocol/related-task": {"taskId": task_id}}}

    def cancel(self, task_id):
        if self.get(task_id)["status"] in TERMINAL:
            raise ValueError("The preparation task is already terminal")
        with self.state.connection() as con:
            changed = con.execute("UPDATE preparations SET cancel_requested=1,updated_at=? WHERE id=? AND status='working'", (timestamp(), task_id))
            if changed.rowcount == 0:
                raise ValueError("The preparation task is already terminal")
        while self.get(task_id)["status"] == "working":
            time.sleep(.1)
        return self.get(task_id)

    def execute(self, task_id):
        from .api import request
        with lock(self.folder(task_id) / "worker.lock"):
            row = self.row(task_id)
            if row["status"] != "working":
                return
            with self.state.connection() as con:
                con.execute("UPDATE preparations SET started_at=?,updated_at=? WHERE id=?", (timestamp(), timestamp(), task_id))
            cancel = lambda: bool(self.row(task_id)["cancel_requested"])

            def progress(value):
                check_cancel(cancel)
                message = json.dumps(value, ensure_ascii=False)
                print(message, flush=True)
                with self.state.connection() as con:
                    con.execute("UPDATE preparations SET message=?,updated_at=? WHERE id=? AND status='working'", (message, timestamp(), task_id))

            try:
                check_cancel(cancel)
                value = request({**json.loads(row["request"]), "action": "prepare"}, progress, cancel=cancel)
                check_cancel(cancel)
                failed = bool(value.get("failed"))
                if failed:
                    value["log"] = str(self.folder(task_id) / "output.log")
                message = "; ".join(item["error"] for item in value.get("failed", []) if item.get("error")) or None
                self.update(task_id, "failed" if failed else "completed", tool_result(value, failed), message)
            except Cancelled as error:
                self.update(task_id, "cancelled", tool_result(partial_result(json.loads(row["request"]), error, True), True), str(error))
            except Exception as error:
                self.update(task_id, "failed", tool_result(partial_result(json.loads(row["request"]), error), True), str(error))


if __name__ == "__main__":
    Tasks(sys.argv[1]).execute(sys.argv[2])
