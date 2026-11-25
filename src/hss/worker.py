"""The analysis process runs inside the selected interpreter."""

import json
import sys
from .study import run


def main():
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    try:
        request = json.load(sys.stdin)
        result = run(request["plan"], request["output"], request.get("base"))
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
    except Exception as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
