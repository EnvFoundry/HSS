"""HSS command-line interface. JSON goes to stdout; progress goes to stderr."""

import argparse
import json
from pathlib import Path
import sys
from .api import request


def read(path):
    return (
        json.load(sys.stdin)
        if path == "-"
        else json.loads(Path(path).read_text(encoding="utf-8"))
    )


def main(argv=None):
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        prog="hss",
        description="Compose humanities and social sciences research environments",
    )
    parser.add_argument("--space", help="Persistent research space")
    parser.add_argument("--layout", help="JSON file mapping resource areas to paths")
    parser.add_argument("--extension", help="Additional catalogue entries")
    commands = parser.add_subparsers(dest="action", required=True)
    p = commands.add_parser("describe")
    p.add_argument("operation", nargs="?")
    for name in ("browse", "installed", "resources", "serve"):
        p = commands.add_parser(name)
        if name == "browse":
            p.add_argument("--field")
    for name in ("search", "methods", "lookup"):
        p = commands.add_parser(name)
        p.add_argument("query", nargs="?", default="")
        if name == "search":
            p.add_argument("--field")
            p.add_argument("--direction")
            p.add_argument("--kind")
        elif name == "methods":
            p.add_argument("--family")
            p.add_argument("--executable", action="store_true")
    for name in ("plan", "prepare", "context", "remove", "export", "index"):
        p = commands.add_parser(name)
        p.add_argument("selections", nargs="*")
        if name == "prepare":
            p.add_argument("--resources-only", action="store_true")
            p.add_argument("--offline", action="store_true")
        if name == "remove":
            p.add_argument("--prune", action="store_true")
        if name == "export":
            p.add_argument("--output", required=True)
    for name in ("request", "prepare-request", "explore"):
        p = commands.add_parser(name)
        p.add_argument("file", nargs="?", default="-")
    p = commands.add_parser("run")
    p.add_argument("file")
    p.add_argument("--output", required=True)
    p = commands.add_parser("project")
    p.add_argument("path")
    p.add_argument("--title", required=True)
    p = commands.add_parser("bind")
    p.add_argument("component")
    p.add_argument("command", nargs="+")
    p = commands.add_parser("exec")
    p.add_argument("component")
    p.add_argument("arguments", nargs=argparse.REMAINDER)
    p = commands.add_parser("connect")
    p.add_argument("provider")
    p.add_argument("query", nargs="?", default="")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--options", help="JSON options file")
    p = commands.add_parser("export-r")
    p.add_argument("adapter")
    p.add_argument("file")
    p.add_argument("--data", required=True)
    p.add_argument("--output", required=True)
    args = vars(parser.parse_args(argv))
    try:
        if args["action"] == "serve":
            import os

            if args.get("space"):
                os.environ["HSS_RESEARCH_SPACE"] = args["space"]
            from .mcp import serve

            serve()
            return 0
        if args.get("layout"):
            args["layout"] = read(args["layout"])
        action = args["action"]
        if action in {"request", "prepare-request"}:
            payload = read(args["file"])
            if action == "prepare-request":
                payload["action"] = "prepare"
            for key in ("space", "layout", "extension"):
                if args.get(key):
                    payload[key] = args[key]
        else:
            payload = {k: v for k, v in args.items() if v is not None}
            if action == "prepare":
                payload["software"] = not args["resources_only"]
                payload["options"] = {"offline": args["offline"]}
            elif action == "run":
                payload.update(
                    study=read(args["file"]),
                    base=str(Path(args["file"]).resolve().parent),
                )
            elif action == "explore":
                payload["brief"] = read(args["file"])
            elif action == "export-r":
                payload["task"] = read(args["file"])
            elif action == "connect" and args.get("options"):
                payload["options"] = read(args["options"])

        def progress(message):
            print(json.dumps(message, ensure_ascii=False), file=sys.stderr, flush=True)

        result = request(payload, progress)
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return (
            2
            if isinstance(result, dict)
            and (result.get("failed") or result.get("pending"))
            else 0
        )
    except (ValueError, KeyError, OSError, RuntimeError, ImportError) as exc:
        print(
            json.dumps(
                {"error": str(exc), "type": type(exc).__name__}, ensure_ascii=False
            ),
            file=sys.stderr,
        )
        return 1
