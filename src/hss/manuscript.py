"""Assemble authored research text and actual result tables into a manuscript."""

from pathlib import Path
from .catalog import read_json, write_json


def cell(value):
    return str(value).replace("|", "\\|").replace("\n", " ")


def render(document, output, base=None):
    base = Path(base or ".").resolve()
    sections = document["sections"]
    if (
        not document.get("title")
        or not sections
        or any(not s.get("heading") or not s.get("text", "").strip() for s in sections)
    ):
        raise ValueError("Supply a title and authored text for every requested section")
    root = Path(output).resolve()
    if root.exists() and any(root.iterdir()):
        raise FileExistsError("Use an empty manuscript directory")
    lines = ["# " + document["title"], ""]
    if document.get("authors"):
        lines += [", ".join(document["authors"]), ""]
    if document.get("abstract"):
        lines += ["## Abstract", "", document["abstract"], ""]
    for section in sections:
        lines += ["## " + section["heading"], "", section["text"], ""]
        for table in section.get("tables", []):
            result = read_json(base / table["result"])
            rows = result["tables"][table["name"]]
            if not rows:
                continue
            columns = table.get("columns") or list(rows[0])
            lines += [
                table.get("caption", table["name"]),
                "",
                "| " + " | ".join(map(cell, columns)) + " |",
                "| " + " | ".join("---" for _ in columns) + " |",
            ]
            lines += [
                "| " + " | ".join(cell(row.get(c, "")) for c in columns) + " |"
                for row in rows
            ]
            lines += [""]
    references = document.get("references", [])
    if references:
        lines += ["## References", ""]
        for index, reference in enumerate(references, 1):
            entry = reference.get("citation") or ". ".join(
                str(reference[k])
                for k in ("author", "year", "title", "container")
                if reference.get(k)
            )
            if not entry:
                raise ValueError("References need bibliographic information")
            if reference.get("url"):
                entry += " " + reference["url"]
            lines += [f"{index}. {entry}", ""]
    root.mkdir(parents=True, exist_ok=True)
    path = root / "manuscript.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    write_json(root / "document.json", document)
    return {
        "manuscript": str(path),
        "sections": len(sections),
        "references": len(references),
    }
