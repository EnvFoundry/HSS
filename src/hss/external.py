"""Run project code and upstream R methods with prepared research interpreters."""

import json
import csv
import os
from pathlib import Path
import subprocess
from .catalog import write_json

R_COMPONENTS = {
    "did": "r-did",
    "contdid": "r-contdid",
    "did_multiplegt": "r-multiplegt",
    "rdrobust": "r-rdrobust",
    "grf": "r-grf",
    "synthdid": "r-synthdid",
    "lavaan": "r-lavaan",
    "cox": "r-survival",
    "survey": "r-survey",
    "mice": "r-missing",
    "qca": "r-qca",
}


def execute(task, out):
    binding = task.get("runtime")
    if not binding:
        raise ValueError(
            "Execute external analyses through hss run after preparing their component"
        )
    if task["operation"] == "r_analysis":
        from .r_export import export_r

        exported = export_r(task["adapter"], task, task["data"], out)
        arguments = ["--vanilla", str(Path(exported["code_file"]).resolve())]
    elif task["operation"] == "command":
        arguments = [
            a["path"] if isinstance(a, dict) else a for a in task.get("arguments", [])
        ]
    else:
        context = out / "input.json"
        write_json(context, {k: v for k, v in task.items() if k != "runtime"})
        arguments = (["--vanilla"] if binding["kind"] == "r" else []) + [
            task["script"],
            str(context.resolve()),
            *task.get("arguments", []),
        ]
    completed = subprocess.run(
        [*binding["command"], *arguments],
        cwd=out,
        env={**os.environ, **binding.get("environment", {}), "PYTHONUTF8": "1"},
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=task.get("timeout", 1800),
    )
    (out / "console.txt").write_text(completed.stdout, encoding="utf-8")
    (out / "messages.txt").write_text(completed.stderr, encoding="utf-8")
    if completed.returncode:
        raise RuntimeError(
            f"{task.get('component', task.get('adapter'))} exited with {completed.returncode}: {completed.stderr[-4000:]}"
        )
    result_file = out / "result.json"
    result = (
        json.loads(result_file.read_text(encoding="utf-8"))
        if result_file.exists()
        else {}
    )
    if not isinstance(result, dict):
        raise ValueError("A project script's result.json must contain an object")
    estimates = out / "estimates.csv"
    if estimates.is_file():

        def value(text):
            try:
                return float(text)
            except (ValueError, TypeError):
                return text

        with estimates.open(encoding="utf-8-sig", newline="") as stream:
            result.setdefault("tables", {})["estimates"] = [
                {k: value(v) for k, v in row.items()} for row in csv.DictReader(stream)
            ]
    result["artifacts"] = sorted(
        str(p.resolve()) for p in out.rglob("*") if p.is_file() and p != result_file
    )
    result["runtime_component"] = task.get(
        "component", R_COMPONENTS.get(task.get("adapter"))
    )
    return result
