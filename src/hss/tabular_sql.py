"""Relational analysis of explicitly named CSV datasets using SQLite."""

import csv
from contextlib import closing
from pathlib import Path
import sqlite3


def identifier(value):
    return '"' + str(value).replace('"', '""') + '"'


def execute(task, out):
    tables = {}
    with closing(sqlite3.connect(out / "analysis.sqlite")) as db, db:
        for source in task["datasets"]:
            with Path(source["path"]).open(encoding="utf-8-sig", newline="") as stream:
                reader = csv.DictReader(stream)
                columns = reader.fieldnames
                if not columns or len(set(columns)) != len(columns):
                    raise ValueError("CSV columns must be nonempty and unique")
                types = source.get("types", {})
                if set(types) - set(columns) or any(
                    t not in {"TEXT", "INTEGER", "REAL"} for t in types.values()
                ):
                    raise ValueError(
                        "Declare TEXT, INTEGER or REAL types for existing columns"
                    )
                definition = ",".join(
                    identifier(c) + " " + types.get(c, "TEXT") for c in columns
                )
                db.execute(
                    "CREATE TABLE "
                    + identifier(source["name"])
                    + " ("
                    + definition
                    + ")"
                )

                def rows():
                    for row in reader:
                        values = []
                        for column in columns:
                            value = row[column]
                            if value in {None, ""}:
                                values.append(None)
                            elif types.get(column) == "INTEGER":
                                values.append(int(value))
                            elif types.get(column) == "REAL":
                                values.append(float(value))
                            else:
                                values.append(value)
                        yield values

                db.executemany(
                    "INSERT INTO "
                    + identifier(source["name"])
                    + " VALUES ("
                    + ",".join("?" for _ in columns)
                    + ")",
                    rows(),
                )
        for query in task["queries"]:
            cursor = db.execute(query["sql"], query.get("parameters", []))
            if cursor.description is None:
                raise ValueError("Research queries must return a table")
            names = [c[0] for c in cursor.description]
            if len(names) != len(set(names)):
                raise ValueError("Use distinct column aliases in research queries")
            tables[query["name"]] = [dict(zip(names, row)) for row in cursor]
    return {"tables": tables, "database": str((out / "analysis.sqlite").resolve())}
