"""A local search index of selected research resources."""

import json
import sqlite3
from contextlib import closing
from .catalog import DATA


def build(manager, selections):
    modules = manager.catalog.select(selections)
    if not modules:
        return {"documents": 0, "database": None}
    path = manager.layout["databases"] / "research.sqlite"
    path.parent.mkdir(parents=True, exist_ok=True)
    records = {}
    for name in modules:
        module = manager.catalog.modules[name]
        records["module:" + name] = (
            module["name"],
            json.dumps(module, ensure_ascii=False),
            "module",
            name,
        )
        for filename in module.get("knowledge", []):
            records["guide:" + filename] = (
                filename,
                manager.catalog.asset("knowledge", filename).read_text(
                    encoding="utf-8"
                ),
                "guide",
                "hss://knowledge/" + filename,
            )
    with closing(sqlite3.connect(path)) as con, con:
        con.executescript((DATA / "sql/documents.sql").read_text(encoding="utf-8"))
        for key, record in records.items():
            con.execute(
                "INSERT OR REPLACE INTO documents VALUES (?,?,?,?,?)", (key, *record)
            )
        count = con.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    return {"documents": count, "database": str(path), "selected_modules": modules}


def search(manager, query, limit=20):
    path = manager.layout["databases"] / "research.sqlite"
    if not path.exists():
        return {
            "results": [],
            "next_action": "Build an index of selected modules with hss index MODULE...",
        }
    query = query.strip()
    if not query:
        raise ValueError("Provide search text")
    with closing(sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)) as con:
        con.row_factory = sqlite3.Row
        escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        rows = con.execute(
            "SELECT * FROM documents WHERE body LIKE ? ESCAPE '\\' OR title LIKE ? ESCAPE '\\' LIMIT ?",
            ("%" + escaped + "%", "%" + escaped + "%", max(1, min(int(limit), 100))),
        )
        result = []
        for row in rows:
            pos = row["body"].casefold().find(query.casefold())
            result.append(
                {
                    "id": row["id"],
                    "title": row["title"],
                    "kind": row["kind"],
                    "location": row["location"],
                    "excerpt": row["body"][max(0, pos - 90) : max(0, pos) + 250],
                }
            )
    return {"results": result}
