"""Prepare selected software or bind an interpreter already supplied by a host."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import venv


def probe(component, command, environment=None):
    if not command or not all(isinstance(x, str) and x for x in command):
        return False
    kind = component["kind"]
    env = {**os.environ, **(environment or {})}
    if kind == "python":
        script = "import importlib; " + "; ".join(
            f"importlib.import_module({name!r})"
            for name in component.get("imports", [])
        )
        if component.get("requirements"):
            script += "; from importlib.metadata import version; from packaging.requirements import Requirement; "
            script += f"rs=[Requirement(x) for x in {component['requirements']!r}]; assert all(version(r.name) in r.specifier for r in rs)"
        args = [*command, "-c", script]
    elif kind == "r":
        args = [
            *command,
            "--vanilla",
            "-e",
            "stopifnot(all(vapply("
            + r_vector(component.get("packages", []))
            + ", requireNamespace, logical(1), quietly=TRUE)))",
        ]
    elif kind == "command":
        args = [*command, *component.get("probe_args", ["--version"])]
    elif kind == "node":
        script = (
            "for (const name of "
            + json.dumps(component.get("packages", []))
            + ") require.resolve(name);"
        )
        args = [*command, "-e", script]
    else:
        return False
    try:
        result = subprocess.run(args, env=env, capture_output=True, timeout=30)
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def r_string(value):
    return json.dumps(str(value), ensure_ascii=False)


def r_vector(values):
    return (
        "c(" + ",".join(r_string(v) for v in values) + ")" if values else "character()"
    )


def find_existing(component, bindings, existing=()):
    candidates = [
        item
        for item in existing
        if not item.get("components") or component["id"] in item["components"]
    ]
    for name, entry in bindings.items():
        if component["kind"] != "command" or name == component["id"]:
            candidates.append({**entry, "components": [component["id"]]})
    if component["kind"] == "python":
        candidates.append({"command": [sys.executable]})
    elif component["kind"] == "r" and shutil.which("Rscript"):
        candidates.append({"command": [shutil.which("Rscript")]})
    elif component["kind"] == "node" and shutil.which("node"):
        candidates.append({"command": [shutil.which("node")]})
    elif component["kind"] == "command" and shutil.which(component["command"]):
        candidates.append({"command": [shutil.which(component["command"])]})
    seen = set()
    for item in candidates:
        command = item.get("command", [])
        key = json.dumps([command, item.get("environment", {})], sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        declared_kind = item.get("kind")
        if declared_kind and declared_kind != component["kind"]:
            continue
        if component["kind"] == "command" and not item.get("components"):
            if (
                not command
                or Path(command[0]).stem.casefold() != component["command"].casefold()
            ):
                continue
        if probe(component, command, item.get("environment")):
            return {
                "command": command,
                "environment": item.get("environment", {}),
                "location": item.get("location", command[0]),
                "managed": bool(item.get("managed", False)),
            }
    return None


def install(component, layout, existing=(), options=None, progress=None):
    options = options or {}
    progress = progress or (lambda message: None)
    name = component["id"]
    root = layout["env"] / "software" / name
    kind = component["kind"]
    if kind == "python":
        interpreter = root / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        if not interpreter.exists():
            progress({"component": name, "step": "create_environment"})
            base_python = options.get("python")
            if base_python:
                subprocess.run(
                    [base_python, "-m", "venv", str(root)],
                    check=True,
                    stdout=sys.stderr,
                )
            else:
                venv.EnvBuilder(with_pip=True).create(root)
        args = [
            str(interpreter),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--cache-dir",
            str(layout["cache"] / "pip"),
        ]
        if options.get("offline"):
            args += ["--no-index"]
        if options.get("find_links"):
            args += ["--find-links", str(options["find_links"])]
        args += component["requirements"] + ["packaging>=23"]
        progress({"component": name, "step": "install_packages"})
        subprocess.run(
            args, check=True, stdout=sys.stderr, timeout=options.get("timeout", 1800)
        )
        binding = {
            "command": [str(interpreter)],
            "managed": True,
            "location": str(root),
            "environment": {},
        }
    elif kind == "r":
        candidates = [e["command"] for e in existing if e.get("kind") == "r"]
        command = (
            candidates[0]
            if candidates
            else ([shutil.which("Rscript")] if shutil.which("Rscript") else None)
        )
        if command is None:
            return {
                "status": "connection_needed",
                "component": name,
                "instructions": component["setup"],
            }
        library = layout["env"] / "R" / "library"
        library.mkdir(parents=True, exist_ok=True)
        environment = {"R_LIBS_USER": str(library)}
        if not probe(component, command, environment):
            if options.get("offline"):
                return {
                    "status": "connection_needed",
                    "component": name,
                    "instructions": "Bind an R library containing the selected packages, or prepare them online.",
                }
            github = component.get("github_packages", {})
            cran_packages = [p for p in component["packages"] if p not in github]
            if github:
                cran_packages.append("remotes")
            expression = (
                "install.packages("
                + r_vector(cran_packages)
                + ", lib="
                + r_string(library)
                + ", repos="
                + r_string(options.get("cran", "https://cloud.r-project.org"))
                + ")"
            )
            for repository in github.values():
                expression += (
                    "; remotes::install_github("
                    + r_string(repository)
                    + ", lib="
                    + r_string(library)
                    + ", upgrade='never', dependencies=NA)"
                )
            progress({"component": name, "step": "install_packages"})
            subprocess.run(
                [*command, "--vanilla", "-e", expression],
                env={**os.environ, **environment},
                check=True,
                stdout=sys.stderr,
                timeout=options.get("timeout", 1800),
            )
        binding = {
            "command": command,
            "managed": False,
            "location": str(library),
            "environment": environment,
        }
    elif kind == "node":
        node, npm = shutil.which("node"), shutil.which("npm")
        if not node or not npm:
            return {
                "status": "connection_needed",
                "component": name,
                "instructions": component["setup"],
            }
        root.mkdir(parents=True, exist_ok=True)
        args = [
            npm,
            "install",
            "--prefix",
            str(root),
            "--cache",
            str(layout["cache"] / "npm"),
            "--no-audit",
            "--no-fund",
            "--no-package-lock",
        ]
        if options.get("offline"):
            args.append("--offline")
        args += component["packages"]
        progress({"component": name, "step": "install_packages"})
        subprocess.run(
            args, check=True, stdout=sys.stderr, timeout=options.get("timeout", 1800)
        )
        binding = {
            "command": [node],
            "managed": True,
            "location": str(root),
            "environment": {"NODE_PATH": str(root / "node_modules")},
        }
    else:
        return {
            "status": "connection_needed",
            "component": name,
            "instructions": component.get(
                "setup", "Connect this resource in the host."
            ),
        }
    if not probe(component, binding["command"], binding["environment"]):
        raise RuntimeError(f"The prepared interpreter cannot load {name}")
    return {"status": "ready", "component": name, **binding}
