"""Selected native text engines; compiled once and called through JSON output."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from .catalog import DATA
from .process import run


def build(component, root, options, *, cancel=None):
    source = DATA / "native"
    root.mkdir(parents=True, exist_ok=True)
    target = root / (component["command"] + (".exe" if os.name == "nt" else ""))
    if component["language"] == "rust":
        compiler = (
            options.get("rustc") or os.environ.get("HSS_RUSTC") or shutil.which("rustc")
        )
        if not compiler:
            return {
                "status": "connection_needed",
                "component": component["id"],
                "instructions": component["setup"],
            }
        commands = [
            [
                compiler,
                "--edition=2021",
                "-O",
                str(source / "corpus.rs"),
                "-o",
                str(target),
            ]
        ]
    else:
        compiler = options.get("cxx") or shutil.which("c++") or shutil.which("g++")
        if compiler:
            commands = [
                [
                    compiler,
                    "-std=c++17",
                    "-O3",
                    *(["-municode"] if os.name == "nt" else []),
                    str(source / "alignment.cpp"),
                    "-o",
                    str(target),
                ]
            ]
        elif shutil.which("cmake"):
            directory = root / "build"
            commands = [
                ["cmake", "-S", str(source), "-B", str(directory)],
                ["cmake", "--build", str(directory), "--config", "Release"],
            ]
        else:
            return {
                "status": "connection_needed",
                "component": component["id"],
                "instructions": component["setup"],
            }
    for command in commands:
        run(
            command, check=True, stdout=sys.stderr, timeout=options.get("timeout", 600), cancel=cancel
        )
    if not target.exists():
        produced = next((root / "build").rglob(target.name), None)
        if produced is None:
            raise RuntimeError("Compiler did not produce " + target.name)
        shutil.copyfile(produced, target)
    return {
        "status": "ready",
        "component": component["id"],
        "command": [str(target)],
        "location": str(root),
        "managed": True,
        "environment": {},
    }


COMPONENTS = {
    "native_profile": "native-corpus",
    "native_concordance": "native-corpus",
    "native_collate": "native-alignment",
}


def execute(task, out):
    command = task.get("native_command")
    if not command:
        raise ValueError(
            "Prepare the native backend and execute the study through hss run"
        )
    operation = task["operation"]
    paths = task.get("paths", [])
    required = 2 if operation == "native_collate" else 1
    if len(paths) != required:
        raise ValueError(f"{operation} requires {required} text file(s)")
    if operation == "native_collate":
        arguments = paths
    elif operation == "native_profile":
        arguments = ["profile", *paths]
    else:
        arguments = ["concordance", *paths, task["query"], str(task.get("context", 40))]
    result = subprocess.run(
        [*command, *arguments],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=task.get("timeout", 600),
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip())
    if operation == "native_concordance":
        records = [json.loads(line) for line in result.stdout.splitlines()]
        return {
            "tables": {"matches": [r for r in records if r["kind"] == "match"]},
            "summary": records[-1],
        }
    value = json.loads(result.stdout)
    table = "segments" if operation == "native_collate" else "top_tokens"
    value["tables"] = {table: value.pop(table)}
    return value
