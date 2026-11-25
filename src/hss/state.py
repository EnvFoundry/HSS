"""Small local registry; opening a catalogue creates no database."""

import json
import sqlite3
from contextlib import contextmanager

SCHEMA = """
CREATE TABLE IF NOT EXISTS modules (id TEXT PRIMARY KEY, installed_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS bindings (component TEXT PRIMARY KEY, command TEXT NOT NULL, managed INTEGER NOT NULL DEFAULT 0, location TEXT, environment TEXT NOT NULL DEFAULT '{}');
CREATE TABLE IF NOT EXISTS assets (module TEXT NOT NULL, path TEXT NOT NULL, content TEXT NOT NULL, PRIMARY KEY(module,path));
CREATE TABLE IF NOT EXISTS module_components (module TEXT NOT NULL, component TEXT NOT NULL, PRIMARY KEY(module,component));
CREATE TABLE IF NOT EXISTS connections (id TEXT PRIMARY KEY, config TEXT NOT NULL);
"""


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
