"""A single JSON request surface for CLI, TypeScript and MCP clients."""

from .catalog import Catalog, DATA, read_json
from .manager import Manager


def request(payload, progress=None, *, cancel=None):
    action = payload["action"]
    catalog = Catalog(payload.get("extension"))
    manager = Manager(payload.get("space"), payload.get("layout"), catalog)
    selections = payload.get("selections", [])
    if action == "browse":
        return catalog.browse(payload.get("field"))
    if action == "describe":
        operations = read_json(DATA / "operations.json")
        if payload.get("operation"):
            operation = next(
                (item for item in operations if item["id"] == payload["operation"]),
                None,
            )
            if operation is None:
                raise ValueError("Unknown operation: " + payload["operation"])
            return operation
        return {
            "operations": [
                {
                    "id": x["id"],
                    "name": x["name"],
                    "kind": x["kind"],
                    "scope": x["scope"],
                }
                for x in operations
            ]
        }
    if action == "search":
        return catalog.search(
            payload.get("query", ""),
            payload.get("field"),
            payload.get("direction"),
            payload.get("kind"),
        )
    if action == "methods":
        return catalog.methods(
            payload.get("query", ""),
            payload.get("family"),
            True if payload.get("executable") else None,
        )
    if action == "resources":
        return {
            "resources": list(catalog.resources.values()),
            "sources": read_json(DATA / "sources.json"),
        }
    if action in {"index", "lookup"}:
        from . import knowledge

        return (
            knowledge.build(manager, selections)
            if action == "index"
            else knowledge.search(manager, payload["query"], payload.get("limit", 20))
        )
    if action == "context":
        return manager.context(selections)
    if action == "plan":
        return manager.plan(
            selections, payload.get("existing", []), payload.get("backends")
        )
    if action in {"prepare", "prepare-request"}:
        return manager.prepare(
            selections,
            payload.get("existing", []),
            payload.get("backends"),
            payload.get("software", True),
            payload.get("options"),
            progress,
            cancel=cancel,
        )
    if action == "installed":
        return manager.installed()
    if action == "bind":
        return manager.bind(
            payload["component"], payload["command"], payload.get("environment")
        )
    if action == "remove":
        return manager.remove(selections, payload.get("prune", False))
    if action == "exec":
        return manager.execute(
            payload["component"],
            payload.get("arguments", []),
            payload.get("cwd"),
            payload.get("timeout", 600),
        )
    if action == "run":
        return manager.run_study(
            payload["study"], payload["output"], payload.get("base")
        )
    if action == "explore":
        from .research import explore

        return explore(payload["brief"], catalog)
    if action == "project":
        from .research import create_project

        return create_project(
            payload["path"],
            payload["title"],
            payload.get("brief"),
            selections,
            payload.get("study"),
            catalog,
        )
    if action == "blueprint":
        from .research import blueprint

        return blueprint(catalog, selections, payload.get("brief"))
    if action == "manuscript":
        from .manuscript import render

        return render(payload["document"], payload["output"], payload.get("base"))
    if action == "connect":
        from .connectors import search

        return search(
            payload["provider"],
            payload.get("query", ""),
            payload.get("limit", 10),
            payload.get("options"),
        )
    if action == "export-r":
        from .r_export import export_r

        return export_r(
            payload["adapter"], payload["task"], payload["data"], payload["output"]
        )
    if action == "export":
        from .hosts import export

        return export(manager, payload["output"], selections)
    raise ValueError("Unknown HSS action: " + action)
