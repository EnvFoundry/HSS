"""Small local registry; opening a catalogue creates no database."""

import json
import sqlite3
from contextlib import contextmanager
from .catalog import DATA

SCHEMA = (DATA / "sql/registry.sql").read_text(encoding="utf-8")


class State:
    def __init__(self, path):
        self.path = path

    @contextmanager
    def connection(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(self.path, timeout=30)
        con.row_factory = sqlite3.Row
        con.executescript(SCHEMA)
        try:
            with con:
                yield con
        finally:
            con.close()

    def rows(self, table):
        if table not in {
            "modules",
            "bindings",
            "assets",
            "module_components",
            "connections",
        }:
            raise ValueError("Unknown registry table")
        if not self.path.exists():
            return []
        con = sqlite3.connect(f"{self.path.as_uri()}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        try:
            return [dict(row) for row in con.execute(f"SELECT * FROM {table}")]
        finally:
            con.close()

    def bindings(self):
        return {
            r["component"]: {
                **r,
                "command": json.loads(r["command"]),
                "environment": json.loads(r["environment"]),
                "managed": bool(r["managed"]),
            }
            for r in self.rows("bindings")
        }

    def bind(self, component, command, managed=False, location=None, environment=None):
        with self.connection() as con:
            con.execute(
                "INSERT OR REPLACE INTO bindings VALUES (?,?,?,?,?)",
                (
                    component,
                    json.dumps(command),
                    int(managed),
                    location,
                    json.dumps(environment or {}),
                ),
            )
