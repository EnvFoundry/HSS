"""Compose modules and materialize their assets into the host's resource areas."""

import json
from pathlib import Path
import shutil
import subprocess
import sys

from .catalog import Catalog, write_json
from .layout import Layout
from .state import State
from . import software
from .process import check_cancel, lock


class Manager:
    def __init__(self, space=None, layout=None, catalog=None):
        self.layout = Layout(space, layout)
        self.catalog = catalog or Catalog()
        self.state = State(self.layout["env"] / "registry.sqlite")

    def components(self, selections, backends=None):
        result = []
        backends = backends or {}
        for name in self.catalog.select(selections):
            module = self.catalog.modules[name]
            ids = module.get("components", [])
            if name in backends:
                key = backends[name]
                alternatives = module.get("backends", {})
                if key not in alternatives:
                    raise ValueError(f"Unknown backend {key} for {name}")
                ids = alternatives[key]
            for component in ids:
                if component not in result:
                    result.append(component)
        return result

    def _assets(self, name):
        module = self.catalog.modules[name]
        assets = []
        for filename in module.get("knowledge", []):
            assets.append(
                (
                    self.layout["knowledge"] / filename,
                    self.catalog.asset("knowledge", filename).read_text(
                        encoding="utf-8"
                    ),
                )
            )
        skill = module.get("skill")
        if skill:
            assets.append(
                (
                    self.layout["skills"] / skill / "SKILL.md",
                    self.catalog.asset("skills", skill + "/SKILL.md").read_text(
                        encoding="utf-8"
                    ),
                )
            )
        for filename in module.get("workflows", []):
            assets.append(
                (
                    self.layout["workflows"] / filename,
                    self.catalog.asset("workflows", filename).read_text(
                        encoding="utf-8"
                    ),
                )
            )
        for filename in module.get("prompts", []):
            assets.append(
                (
                    self.layout["prompts"] / filename,
                    self.catalog.asset("prompts", filename).read_text(encoding="utf-8"),
                )
            )
        return assets

    def plan(self, selections=(), existing=(), backends=None):
        modules = self.catalog.select(selections)
        bindings = self.state.bindings()
        actions = []
        for name in self.components(modules, backends):
            component = self.catalog.components[name]
            binding = software.find_existing(component, bindings, existing)
            actions.append(
                {
                    "component": name,
                    "kind": component["kind"],
                    "action": "reuse"
                    if binding
                    else (
                        "install"
                        if component["kind"] in {"python", "r", "node", "native"}
                        else "connect"
                    ),
                    "binding": binding,
                    "requirements": component.get(
                        "requirements", component.get("packages", [])
                    ),
                    "destination": str(self.layout["env"] / "R/library" if component["kind"] == "r" else self.layout.component_root(name)),
                    "download_bytes": None,
                    "disk_bytes": None,
                    "setup": component.get("setup"),
                }
            )
        assets = {}
        for name in modules:
            for path, text in self._assets(name):
                assets[str(path)] = len(text.encode("utf-8"))
        return {
            "modules": modules,
            "actions": actions,
            "assets": list(assets),
            "resources": [{"path": path, "kind": next((area for area in ("skills", "knowledge", "workflows", "prompts")
                           if Path(path).is_relative_to(self.layout[area])), "resource"), "bytes": size}
                          for path, size in assets.items()],
            "resource_bytes": sum(assets.values()),
            "layout": self.layout.describe(),
        }

    def prepare(
        self,
        selections=(),
        existing=(),
        backends=None,
        software_enabled=True,
        options=None,
        progress=None,
        *,
        cancel=None,
    ):
        modules = self.catalog.select(selections)
        if not modules:
            return {"modules": [], "ready": [], "pending": [], "failed": []}
        with lock(self.layout["env"] / "prepare.lock", cancel=cancel):
            return self._prepare(modules, existing, backends, software_enabled, options, progress, cancel)

    def _prepare(self, modules, existing, backends, software_enabled, options, progress, cancel):
        check_cancel(cancel)
        prepared_assets = []
        known = {r["path"]: r["content"] for r in self.state.rows("assets")}
        for name in modules:
            for path, text in self._assets(name):
                if path.exists() and path.read_text(encoding="utf-8") not in {
                    text,
                    known.get(str(path)),
                }:
                    raise FileExistsError(f"This file contains local edits: {path}")
                prepared_assets.append((name, path, text))
        for _, path, text in prepared_assets:
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists() or path.read_text(encoding="utf-8") != text:
                path.write_text(text, encoding="utf-8")
        with self.state.connection() as con:
            for name in modules:
                con.execute("INSERT OR IGNORE INTO modules(id) VALUES (?)", (name,))
                con.execute("DELETE FROM module_components WHERE module=?", (name,))
                for component in self.components([name], backends):
                    con.execute(
                        "INSERT OR IGNORE INTO module_components VALUES (?,?)",
                        (name, component),
                    )
            for name, path, text in prepared_assets:
                con.execute(
                    "INSERT OR REPLACE INTO assets VALUES (?,?,?)",
                    (name, str(path), text),
                )
        ready, pending, failed = [], [], []
        for name in self.components(modules, backends):
            check_cancel(cancel)
            component = self.catalog.components[name]
            binding = software.find_existing(component, self.state.bindings(), existing, cancel=cancel)
            if binding:
                self.state.bind(name, **binding)
                ready.append({"component": name, "status": "ready", **binding})
            elif not software_enabled:
                pending.append({"component": name, "status": "not_prepared"})
            else:
                try:
                    available = [
                        *existing,
                        *(
                            {**binding, "kind": self.catalog.components[key]["kind"]}
                            for key, binding in self.state.bindings().items()
                            if key in self.catalog.components
                        ),
                    ]
                    result = software.install(
                        component, self.layout, available, options, progress, cancel=cancel
                    )
                    if result["status"] == "ready":
                        self.state.bind(
                            name,
                            **{
                                k: result[k]
                                for k in (
                                    "command",
                                    "managed",
                                    "location",
                                    "environment",
                                )
                            },
                        )
                        ready.append(result)
                    else:
                        pending.append(result)
                except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
                    failed.append({"component": name, "error": str(exc)})
        write_json(
            self.layout["env"] / "selection.json",
            {"modules": self.installed()["modules"], "layout": self.layout.describe()},
        )
        return {
            "modules": modules,
            "ready": ready,
            "pending": pending,
            "failed": failed,
            "assets": sorted({str(p) for _, p, _ in prepared_assets}),
            "layout": self.layout.describe(),
        }

    def bind(self, component, command, environment=None):
        definition = self.catalog.components[component]
        if not software.probe(definition, command, environment):
            raise ValueError(f"The command cannot provide {component}")
        self.state.bind(
            component, command, location=command[0], environment=environment
        )
        return self.state.bindings()[component]

    def installed(self):
        bindings = self.state.bindings()
        selected = sorted(r["id"] for r in self.state.rows("modules"))
        components = {r["component"] for r in self.state.rows("module_components")}
        ready, failed = [], []
        for name, binding in bindings.items():
            if binding["command"] and (Path(binding["command"][0]).is_file() or shutil.which(binding["command"][0])):
                ready.append({"component": name, "status": "ready", **binding})
            else:
                failed.append({"component": name, "error": "The registered executable is unavailable"})
        available = {row["component"] for row in ready}
        module_components = {name: set() for name in selected}
        for row in self.state.rows("module_components"):
            module_components.setdefault(row["module"], set()).add(row["component"])
        return {
            "modules": selected,
            "ready_modules": [name for name in selected if module_components[name] <= available],
            "bindings": bindings,
            "ready": ready,
            "pending": [{"component": name, "status": "not_prepared"} for name in sorted(components - bindings.keys())],
            "failed": failed,
        }

    def context(self, selections):
        result = self.catalog.context(selections)
        prepared = {}
        for row in self.state.rows("module_components"):
            prepared.setdefault(row["module"], []).append(row["component"])
        components = set()
        for module in result["modules"]:
            module["prepared_components"] = prepared.get(module["id"], [])
            components.update(prepared.get(module["id"], module.get("components", [])))
        result["bindings"] = {
            k: v for k, v in self.state.bindings().items() if k in components
        }
        result["layout"] = self.layout.describe()
        return result

    def remove(self, selections, prune=False):
        selected = set(self.catalog.select(selections))
        installed = set(self.installed()["modules"])
        remaining = installed - selected
        for module in remaining:
            needed = set(self.catalog.select([module])) - {module}
            if needed & selected:
                raise ValueError(
                    f"{module} still uses {', '.join(sorted(needed & selected))}"
                )
        deleted, retained = [], []
        if not self.state.path.exists():
            return {"removed": [], "retained": []}
        with self.state.connection() as con:
            rows = list(con.execute("SELECT * FROM assets"))
            for name in selected:
                con.execute("DELETE FROM modules WHERE id=?", (name,))
                con.execute("DELETE FROM assets WHERE module=?", (name,))
                con.execute("DELETE FROM module_components WHERE module=?", (name,))
            used = {r[0] for r in con.execute("SELECT path FROM assets")}
            for row in rows:
                path = Path(row["path"])
                if (
                    row["module"] in selected
                    and str(path) not in used
                    and path.is_file()
                ):
                    if path.read_text(encoding="utf-8") == row["content"]:
                        path.unlink()
                        deleted.append(str(path))
                    else:
                        retained.append(str(path))
            if prune:
                needed = {
                    r[0] for r in con.execute("SELECT component FROM module_components")
                }
                retained_locations = {
                    r[0]
                    for r in con.execute(
                        "SELECT location FROM bindings WHERE component IN (SELECT component FROM module_components)"
                    )
                }
                for row in list(con.execute("SELECT * FROM bindings")):
                    location = (
                        Path(row["location"]).resolve() if row["location"] else None
                    )
                    if row["component"] not in needed:
                        if (
                            row["managed"]
                            and location
                            and str(location) not in retained_locations
                            and location.is_relative_to(self.layout["env"] / "software")
                            and location.is_dir()
                        ):
                            shutil.rmtree(location)
                        con.execute(
                            "DELETE FROM bindings WHERE component=?",
                            (row["component"],),
                        )
        return {
            "removed": sorted(selected & installed),
            "files": sorted(set(deleted)),
            "retained": retained,
        }

    def execute(self, component, arguments, cwd=None, timeout=600):
        import os

        binding = self.state.bindings().get(component)
        if binding is None:
            raise ValueError(f"Prepare or bind {component} first")
        run = subprocess.run(
            [*binding["command"], *arguments],
            cwd=cwd,
            env={**os.environ, **binding["environment"]},
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout,
        )
        return {"exit_code": run.returncode, "stdout": run.stdout, "stderr": run.stderr}

    def run_study(self, plan, output, base=None):
        from .study import ordered_tasks
        from .materials import FUNCTIONS
        from .native import COMPONENTS
        from .external import R_COMPONENTS
        import copy
        import os

        plan = copy.deepcopy(plan)
        for task in plan["tasks"]:
            operation = task.get("operation")
            if operation in {"r_analysis", "script", "command"}:
                component_id = (
                    R_COMPONENTS.get(task.get("adapter"))
                    if operation == "r_analysis"
                    else task.get("component")
                )
                if component_id not in self.catalog.components:
                    raise ValueError("Unknown research runtime: " + str(component_id))
                definition = self.catalog.components[component_id]
                if operation != "command" and definition["kind"] not in {
                    "python",
                    "r",
                    "node",
                }:
                    raise ValueError(
                        "Project scripts require a Python, R or Node component"
                    )
                binding = software.find_existing(definition, self.state.bindings())
                if binding is None:
                    raise ValueError(
                        f"Prepare or bind {component_id} before running this study"
                    )
                task["runtime"] = {**binding, "kind": definition["kind"]}
            native_component = COMPONENTS.get(task.get("operation"))
            if native_component:
                binding = self.state.bindings().get(native_component)
                if binding is None:
                    raise ValueError(
                        f"Prepare or bind {native_component} before running this study"
                    )
                task["native_command"] = binding["command"]
        tasks = ordered_tasks(plan)
        needs_analysis = any(
            t["operation"] not in {*FUNCTIONS, "r_analysis", "script", "command", "sql"}
            for t in tasks
        )
        component = "python-empirical" if needs_analysis else None
        if any(
            str(p).lower().endswith(".pdf") for t in tasks for p in t.get("paths", [])
        ):
            if needs_analysis:
                raise ValueError(
                    "Extract PDFs as a material study, then pass the corpus to the analysis study"
                )
            component = "python-documents"
        if component:
            binding = software.find_existing(
                self.catalog.components[component], self.state.bindings()
            )
            if binding is None:
                raise ValueError(
                    f"Prepare or bind {component} before running this study"
                )
        else:
            binding = {"command": [sys.executable], "environment": {}}
        request = {
            "plan": plan,
            "output": str(Path(output).resolve()),
            "base": str(Path(base or ".").resolve()),
        }
        env = {**os.environ, **binding["environment"]}
        env["PYTHONPATH"] = str(Path(__file__).parent.parent) + (
            os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
        )
        result = subprocess.run(
            [*binding["command"], "-m", "hss.worker"],
            input=json.dumps(request, ensure_ascii=False),
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
        )
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip())
        return json.loads(result.stdout)
