"""Text, qualitative material, arguments and collection instruments."""

from collections import Counter
import csv
import difflib
import html
import json
from pathlib import Path
import re
import sqlite3
import statistics
import xml.etree.ElementTree as ET
import zipfile

from .catalog import write_json


def extract(path):
    path = Path(path)
    if path.suffix.lower() == ".pdf":
        from pypdf import PdfReader

        return "\n\n".join(page.extract_text() or "" for page in PdfReader(path).pages)
    if path.suffix.lower() == ".docx":
        with zipfile.ZipFile(path) as archive:
            root = ET.fromstring(archive.read("word/document.xml"))
        ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        return "\n".join("".join(p.itertext()) for p in root.findall(".//w:p", ns))
    text = path.read_text(encoding="utf-8-sig")
    if path.suffix.lower() in {".xml", ".tei"}:
        root = ET.fromstring(text)
        bodies = root.findall(".//{http://www.tei-c.org/ns/1.0}body")
        return "".join((bodies[0] if bodies else root).itertext())
    return text


def documents(task):
    docs = [dict(d) for d in task.get("documents", [])]
    for name in task.get("paths", []):
        path = Path(name)
        if path.suffix == ".jsonl":
            docs.extend(
                json.loads(line)
                for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            )
        else:
            docs.append(
                {"id": str(path), "source": str(path.resolve()), "text": extract(path)}
            )
    ids = [d["id"] for d in docs]
    if len(set(ids)) != len(ids):
        raise ValueError("Document IDs must be unique")
    for doc in docs:
        if not isinstance(doc.get("text"), str):
            raise ValueError("Each document needs its original text")
    return docs


def corpus(task, out):
    docs = documents(task)
    if not docs:
        raise ValueError("Provide documents or file paths")
    for doc in docs:
        doc["characters"] = len(doc["text"])
        doc["paragraphs"] = [
            {"start": m.start(), "end": m.end()}
            for m in re.finditer(r"[^\r\n]+", doc["text"])
        ]
    path = out / "corpus.jsonl"
    path.write_text(
        "".join(json.dumps(d, ensure_ascii=False) + "\n" for d in docs),
        encoding="utf-8",
    )
    return {
        "documents": len(docs),
        "characters": sum(d["characters"] for d in docs),
        "corpus": str(path),
        "offset_unit": "Unicode code points",
    }


def concordance(task, out):
    query = task["query"]
    if not query:
        raise ValueError("A nonempty query is required")
    pattern = re.compile(
        query if task.get("regex") else re.escape(query),
        0 if task.get("case_sensitive", True) else re.I,
    )
    width = int(task.get("context", 40))
    if width < 0:
        raise ValueError("Context width must be nonnegative")
    rows = []
    for doc in documents(task):
        text = doc["text"]
        for m in pattern.finditer(text):
            rows.append(
                {
                    "document": doc["id"],
                    "start": m.start(),
                    "end": m.end(),
                    "left": text[max(0, m.start() - width) : m.start()],
                    "match": m.group(),
                    "right": text[m.end() : m.end() + width],
                }
            )
    return {
        "tables": {"concordance": rows},
        "matches": len(rows),
        "offset_unit": "Unicode code points",
    }


def collate(task, out):
    docs = documents(task)
    if len(docs) != 2:
        raise ValueError("Collation takes two documents")
    a, b = docs
    segments = []
    for kind, i, j, k, l in difflib.SequenceMatcher(
        None, a["text"], b["text"], autojunk=False
    ).get_opcodes():
        segments.append(
            {
                "kind": kind,
                "left_start": i,
                "left_end": j,
                "right_start": k,
                "right_end": l,
                "left": a["text"][i:j],
                "right": b["text"][k:l],
            }
        )
    page = difflib.HtmlDiff().make_file(
        a["text"].splitlines(),
        b["text"].splitlines(),
        fromdesc=html.escape(a["id"]),
        todesc=html.escape(b["id"]),
        charset="utf-8",
    )
    path = out / "collation.html"
    path.write_text(page, encoding="utf-8")
    return {
        "tables": {"segments": segments},
        "display": str(path),
        "comparison": "character and line alignment; semantic equivalence is interpreted by the researcher",
    }


def coding(task, out):
    docs = {d["id"]: d for d in documents(task)}
    codebook = task["codebook"]
    if not isinstance(codebook, dict) or not all(
        isinstance(v, str) and v.strip() for v in codebook.values()
    ):
        raise ValueError("Provide a code-to-definition mapping")
    rows = []
    for item in task["annotations"]:
        doc = docs[item["document"]]
        start, end = item["start"], item["end"]
        if (
            not isinstance(start, int)
            or not isinstance(end, int)
            or not 0 <= start < end <= len(doc["text"])
        ):
            raise ValueError("Annotation offsets must select an existing passage")
        if item["code"] not in codebook:
            raise ValueError("Unknown code: " + item["code"])
        quote = doc["text"][start:end]
        if "quote" in item and item["quote"] != quote:
            raise ValueError("Quoted passage does not match its offsets")
        rows.append({**item, "quote": quote, "definition": codebook[item["code"]]})
    counts = Counter(r["code"] for r in rows)
    from itertools import combinations

    pairs = Counter()
    for document in docs:
        codes = sorted({row["code"] for row in rows if row["document"] == document})
        pairs.update(combinations(codes, 2))
    cooccurrence = [
        {"code_a": a, "code_b": b, "documents": count}
        for (a, b), count in pairs.items()
    ]
    return {
        "tables": {
            "annotations": rows,
            "code_counts": [{"code": k, "passages": v} for k, v in counts.items()],
            "cooccurrence": cooccurrence,
        },
        "cooccurrence_unit": "document, pooled over supplied coders",
        "codebook": codebook,
        "interpretation": "Counts describe supplied coding; themes and explanations remain interpretive work.",
    }


def agreement(task, out):
    rows = task["ratings"]
    if not rows or len({r["unit"] for r in rows}) != len(rows):
        raise ValueError("Provide one paired rating per distinct unit")
    if any(r.get("a") is None or r.get("b") is None for r in rows):
        raise ValueError("Both raters must label every supplied unit")
    a, b = Counter(r["a"] for r in rows), Counter(r["b"] for r in rows)
    n = len(rows)
    observed = sum(r["a"] == r["b"] for r in rows) / n
    expected = sum(a[k] * b[k] for k in a.keys() | b.keys()) / n**2
    return {
        "units": n,
        "observed_agreement": observed,
        "expected_agreement": expected,
        "cohens_kappa": (observed - expected) / (1 - expected)
        if expected < 1
        else None,
        "scope": "Two complete nominal ratings of the same units",
    }


def argument_map(task, out):
    claims, links = task["claims"], task.get("relations", [])
    lookup = {c["id"]: c for c in claims}
    if len(lookup) != len(claims):
        raise ValueError("Claim IDs must be unique")
    for link in links:
        if link["from"] not in lookup or link["to"] not in lookup:
            raise ValueError("Every relation must connect named claims")
        if link["kind"] not in {"supports", "opposes", "depends", "qualifies"}:
            raise ValueError("Unknown relation kind")
    lines = ["# Argument", ""]
    for claim in claims:
        lines += [
            f"## {claim['id']}",
            "",
            claim["text"],
            "",
            "Role: " + claim.get("role", "claim"),
            "",
            "Source: " + claim.get("source", "researcher formulation"),
            "",
        ]
    for link in links:
        lines.append(
            f"- {link['from']} {link['kind']} {link['to']}: {link.get('reason', '')}"
        )
    path = out / "argument.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "claims": claims,
        "relations": links,
        "document": str(path),
        "scope": "Explicit argument structure; logical truth and source interpretation are not inferred from graph structure.",
    }


def questionnaire(task, out):
    items = task["items"]
    seen, survey = set(), []
    allowed = {"text", "number", "single", "multiple", "scale"}
    for item in items:
        if item["id"] in seen or item["type"] not in allowed:
            raise ValueError("Each item needs a unique ID and supported type")
        if "show_if" in item and item["show_if"]["item"] not in seen:
            raise ValueError("Branch conditions refer to an earlier item")
        if (
            item["type"] in {"single", "multiple", "scale"}
            and len(item.get("options", [])) < 2
        ):
            raise ValueError("Choice items require explicit response options")
        seen.add(item["id"])
        survey.append(dict(item))
    write_json(
        out / "questionnaire.json",
        {"title": task.get("title", "Questionnaire"), "items": survey},
    )
    lines = ["# " + task.get("title", "Questionnaire"), ""]
    for item in survey:
        lines += [
            f"**{item['id']}** {item['prompt']}",
            "",
            " / ".join(map(str, item.get("options", []))),
            "",
        ]
        if item.get("show_if"):
            lines += [
                "Show when: " + json.dumps(item["show_if"], ensure_ascii=False),
                "",
            ]
    (out / "questionnaire.md").write_text("\n".join(lines), encoding="utf-8")
    return {
        "items": len(items),
        "instrument": str(out / "questionnaire.json"),
        "preview": str(out / "questionnaire.md"),
        "collection": "Import the instrument through the survey service adapter chosen by the host.",
    }


def experiment(task, out):
    """Generate a dependency-free reaction-time task with a local CSV download."""
    trials = task["trials"]
    if not trials or any(not t.get("stimulus") for t in trials):
        raise ValueError("Provide actual trial stimuli")
    encoded = json.dumps(trials, ensure_ascii=False).replace("<", "\\u003c")
    template = (Path(__file__).parent / "data" / "experiment.html").read_text(
        encoding="utf-8"
    )
    path = out / "experiment.html"
    path.write_text(template.replace("__TRIALS__", encoded), encoding="utf-8")
    return {
        "experiment": str(path),
        "trials": len(trials),
        "output": "Browser downloads responses.csv after the final trial",
        "timing": "performance.now; characterize browser and display timing for the intended experiment",
        "jspsych": "Use the optional jspsych component for richer stimuli, randomization and plugins.",
    }


def table(task, out):
    with Path(task["data"]).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        names = reader.fieldnames or []
        if len(names) != len(set(names)):
            raise ValueError("Duplicate CSV column names")
        rows = list(reader)
    summaries = []
    for key in names:
        present = [r[key] for r in rows if r[key] not in {None, ""}]
        entry = {
            "column": key,
            "rows": len(rows),
            "missing": len(rows) - len(present),
            "distinct": len(set(present)),
        }
        try:
            numbers = [float(v) for v in present]
            if numbers:
                import math

                if not all(math.isfinite(v) for v in numbers):
                    raise ValueError("Nonfinite values")
                entry.update(
                    type="numeric",
                    mean=statistics.mean(numbers),
                    minimum=min(numbers),
                    maximum=max(numbers),
                )
        except ValueError:
            entry["type"] = "text"
        summaries.append(entry)
    keys = task.get("keys", [])
    if keys:
        if not set(keys) <= set(names):
            raise ValueError("Key columns are absent")
        if len({tuple(r[k] for k in keys) for r in rows}) != len(rows):
            raise ValueError("Declared key is not unique")
    return {"tables": {"columns": summaries}, "rows": len(rows), "keys": keys}


def bibliography(task, out):
    path = out / "bibliography.sqlite"
    with sqlite3.connect(path) as con:
        con.execute(
            "CREATE TABLE IF NOT EXISTS works(id TEXT PRIMARY KEY, title TEXT NOT NULL, authors TEXT, year INTEGER, doi TEXT, url TEXT, metadata TEXT NOT NULL)"
        )
        for item in task["works"]:
            con.execute(
                "INSERT OR REPLACE INTO works VALUES (?,?,?,?,?,?,?)",
                (
                    item["id"],
                    item["title"],
                    json.dumps(item.get("authors", []), ensure_ascii=False),
                    item.get("year"),
                    item.get("doi"),
                    item.get("url"),
                    json.dumps(item, ensure_ascii=False),
                ),
            )
        count = con.execute("SELECT COUNT(*) FROM works").fetchone()[0]
    return {"database": str(path), "works": count}


FUNCTIONS = {
    name: globals()[name]
    for name in (
        "corpus",
        "concordance",
        "collate",
        "coding",
        "agreement",
        "argument_map",
        "questionnaire",
        "experiment",
        "table",
        "bibliography",
    )
}
