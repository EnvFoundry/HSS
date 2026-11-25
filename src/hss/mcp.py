"""MCP stdio server, with no dependency required for catalogue operations."""

import json
import sys
from .api import request
from .catalog import DATA

STRING = {"type": "string"}
SELECTIONS = {"type": "array", "items": STRING}
TOOL_SPECS = {
    "describe": (
        "Get exact operation inputs and a complete example before writing a study task",
        {"operation": STRING},
        [],
    ),
    "browse": ("Browse fields, directions and bundles", {"field": STRING}, []),
    "search": (
        "Find reusable research modules",
        {"query": STRING, "field": STRING, "kind": STRING},
        [],
    ),
    "methods": (
        "Find method cards and their actual execution support",
        {"query": STRING, "family": STRING, "executable": {"type": "boolean"}},
        [],
    ),
    "resources": ("List data and literature services with access descriptions", {}, []),
    "index": (
        "Build a local searchable database of selected research resources",
        {"selections": SELECTIONS},
        ["selections"],
    ),
    "lookup": (
        "Search the selected local research knowledge",
        {"query": STRING, "limit": {"type": "integer"}},
        ["query"],
    ),
    "context": (
        "Read selected research guidance and available software bindings",
        {"selections": SELECTIONS},
        ["selections"],
    ),
    "plan": (
        "Resolve selected modules, shared software and install locations",
        {
            "selections": SELECTIONS,
            "existing": {"type": "array", "items": {"type": "object"}},
        },
        ["selections"],
    ),
    "prepare": (
        "Prepare only explicitly selected modules",
        {
            "selections": SELECTIONS,
            "software": {"type": "boolean"},
            "existing": {"type": "array", "items": {"type": "object"}},
            "options": {"type": "object"},
        },
        ["selections"],
    ),
    "installed": ("Read prepared modules and interpreter bindings", {}, []),
    "explore": (
        "Develop alternative research designs from an initial brief",
        {"brief": {"type": "object"}},
        ["brief"],
    ),
    "project": (
        "Create a research project in an empty directory",
        {"path": STRING, "title": STRING, "brief": {"type": "object"}},
        ["path", "title"],
    ),
    "run": (
        "Execute specified study tasks using the configured interpreter",
        {"study": {"type": "object"}, "output": STRING, "base": STRING},
        ["study", "output"],
    ),
    "connect": (
        "Query a scholarly metadata or indicator service",
        {
            "provider": {"enum": ["crossref", "openalex", "worldbank", "zotero"]},
            "query": STRING,
            "limit": {"type": "integer"},
            "options": {"type": "object"},
        },
        ["provider"],
    ),
    "export-r": (
        "Generate R code for an explicit method configuration",
        {
            "adapter": STRING,
            "task": {"type": "object"},
            "data": STRING,
            "output": STRING,
        },
        ["adapter", "task", "data", "output"],
    ),
}


def resources():
    result = [
        {
            "uri": "hss://catalog",
            "name": "HSS catalogue",
            "mimeType": "application/json",
        },
        {
            "uri": "hss://methods",
            "name": "Research methods",
            "mimeType": "application/json",
        },
    ]
    for folder, suffix, mime in (
        ("knowledge", "md", "text/markdown"),
        ("workflows", "json", "application/json"),
    ):
        result += [
            {"uri": f"hss://{folder}/{p.name}", "name": p.stem, "mimeType": mime}
            for p in sorted((DATA / folder).glob("*." + suffix))
        ]
    return result


def dispatch(method, params):
    if method == "initialize":
        requested = params.get("protocolVersion")
        return {
            "protocolVersion": requested
            if requested in {"2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25"}
            else "2025-11-25",
            "capabilities": {"tools": {}, "resources": {}, "prompts": {}},
            "serverInfo": {"name": "hss", "version": "0.1.0"},
            "instructions": "Browse first; load only relevant context. Prepare explicit selections. Keep project files outside System.",
        }
    if method == "ping":
        return {}
    if method == "tools/list":
        result = []
        for name, (description, properties, required) in TOOL_SPECS.items():
            readonly = name not in {"prepare", "project", "run", "export-r", "index"}
            result.append(
                {
                    "name": "hss_" + name.replace("-", "_"),
                    "description": description,
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            **properties,
                            "space": STRING,
                            "layout": {"type": "object"},
                        },
                        "required": required,
                        "additionalProperties": False,
                    },
                    "annotations": {
                        "readOnlyHint": readonly,
                        "destructiveHint": False,
                        "idempotentHint": readonly or name == "prepare",
                        "openWorldHint": name in {"connect", "prepare"},
                    },
                }
            )
        return {"tools": result}
    if method == "tools/call":
        name = params["name"]
        action = next(
            (key for key in TOOL_SPECS if "hss_" + key.replace("-", "_") == name), None
        )
        if not action:
            raise ValueError("Unknown tool: " + name)
        try:
            value = request({**params.get("arguments", {}), "action": action})
            structured = value if isinstance(value, dict) else {"items": value}
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(value, ensure_ascii=False, allow_nan=False),
                    }
                ],
                "structuredContent": structured,
                "isError": False,
            }
        except Exception as exc:
            return {
                "content": [{"type": "text", "text": f"{type(exc).__name__}: {exc}"}],
                "isError": True,
            }
    if method == "resources/list":
        return {
            "resources": resources()
            + [
                {
                    "uri": "hss://operations",
                    "name": "Operation inputs and examples",
                    "mimeType": "application/json",
                },
                {
                    "uri": "hss://study-schema",
                    "name": "Study input schema",
                    "mimeType": "application/json",
                },
            ]
        }
    if method == "resources/templates/list":
        return {"resourceTemplates": []}
    if method == "resources/read":
        uri = params["uri"]
        resource = next(
            (r for r in dispatch("resources/list", {})["resources"] if r["uri"] == uri),
            None,
        )
        if not resource:
            raise ValueError("Unknown resource: " + uri)
        name = uri.removeprefix("hss://")
        path = DATA / (
            {
                "catalog": "catalog.json",
                "methods": "methods.json",
                "operations": "operations.json",
                "study-schema": "study.schema.json",
            }.get(name, name)
        )
        return {
            "contents": [
                {
                    "uri": uri,
                    "mimeType": resource["mimeType"],
                    "text": path.read_text(encoding="utf-8"),
                }
            ]
        }
    if method == "prompts/list":
        return {
            "prompts": [
                {
                    "name": "hss_design",
                    "description": "Develop a researchable question and compare designs",
                    "arguments": [
                        {
                            "name": "phenomenon",
                            "description": "Initial phenomenon or question",
                            "required": True,
                        }
                    ],
                },
                {
                    "name": "hss_interpret",
                    "description": "Interpret actual research outputs",
                    "arguments": [
                        {
                            "name": "findings",
                            "description": "Computed or interpreted findings",
                            "required": True,
                        }
                    ],
                },
            ]
        }
    if method == "prompts/get":
        mapping = {
            "hss_design": ("design.md", "phenomenon"),
            "hss_interpret": ("interpret.md", "findings"),
        }
        filename, argument = mapping[params["name"]]
        text = (
            (DATA / "prompts" / filename).read_text(encoding="utf-8")
            + "\n\n"
            + params["arguments"][argument]
        )
        return {
            "messages": [{"role": "user", "content": {"type": "text", "text": text}}]
        }
    raise NotImplementedError("Unknown MCP method: " + method)


def serve():
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    for line in sys.stdin:
        message = None
        try:
            message = json.loads(line)
            if "id" not in message:
                continue
            result = dispatch(message["method"], message.get("params", {}))
            response = {"jsonrpc": "2.0", "id": message["id"], "result": result}
        except Exception as exc:
            code = (
                -32700
                if isinstance(exc, json.JSONDecodeError)
                else -32601
                if isinstance(exc, NotImplementedError)
                else -32602
            )
            response = {
                "jsonrpc": "2.0",
                "id": message.get("id") if isinstance(message, dict) else None,
                "error": {"code": code, "message": str(exc)},
            }
        print(json.dumps(response, ensure_ascii=False, allow_nan=False), flush=True)


if __name__ == "__main__":
    serve()
