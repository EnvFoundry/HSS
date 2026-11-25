"""File and stdio interfaces shared by research operating systems and agents."""

from pathlib import Path
import shutil
import sys
from .catalog import write_json


def export(manager, output, selections=()):
    root = Path(output).resolve()
    if root.exists() and any(root.iterdir()):
        raise FileExistsError("Use an empty plugin output directory")
    root.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        Path(__file__).parent,
        root / "runtime" / "hss",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    packaged_data = root / "runtime" / "hss" / "data"
    write_json(packaged_data / "catalog.json", manager.catalog.data)
    for module in manager.catalog.modules.values():
        for area in ("knowledge", "workflows", "prompts"):
            for filename in module.get(area, []):
                target = packaged_data / area / filename
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(manager.catalog.asset(area, filename), target)
        if module.get("skill"):
            target = packaged_data / "skills" / module["skill"] / "SKILL.md"
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(
                manager.catalog.asset("skills", module["skill"] + "/SKILL.md"), target
            )
    skills = sorted(
        {
            manager.catalog.modules[m].get("skill")
            for m in manager.catalog.select(selections)
        }
        - {None}
    )
    for name in skills:
        shutil.copytree(packaged_data / "skills" / name, root / "skills" / name)
    (root / "server.py").write_text(
        'from pathlib import Path\nimport sys\nsys.path.insert(0, str(Path(__file__).parent / "runtime"))\nfrom hss.mcp import serve\nserve()\n',
        encoding="utf-8",
    )
    configure = '''"""Run after moving this plugin to another machine."""
import json, os, sys
from pathlib import Path
root = Path(__file__).resolve().parent
server = {"command": sys.executable, "args": ["-B", str(root / "server.py")], "env": {"HSS_RESEARCH_SPACE": os.environ.get("HSS_RESEARCH_SPACE", str(Path.home() / ".hss"))}}
(root / "mcp.json").write_text(json.dumps({"mcpServers": {"hss": server}}, ensure_ascii=False, indent=2)+"\\n", encoding="utf-8")
plugin = json.loads((root / "plugin.json").read_text(encoding="utf-8"))
plugin["mcpServers"]["hss"]["env"] = server["env"]
(root / "plugin.json").write_text(json.dumps(plugin, ensure_ascii=False, indent=2)+"\\n", encoding="utf-8")
print(root / "mcp.json")
'''
    (root / "configure.py").write_text(configure, encoding="utf-8")
    server = {
        "command": sys.executable,
        "args": ["-B", str(root / "server.py")],
        "env": {"HSS_RESEARCH_SPACE": str(manager.layout.space)},
    }
    write_json(root / "mcp.json", {"mcpServers": {"hss": server}})
    write_json(
        root / "plugin.json",
        {
            "name": "hss-research",
            "version": "0.1.0",
            "description": "Humanities and social sciences research resources and execution",
            "skills": ["skills/" + s for s in skills],
            "environment": {"resources": []},
            "mcpServers": {
                "hss": {
                    "transport": "stdio",
                    "command": "${RESEARCH_PYTHON}",
                    "args": ["-B", "${PACKAGE_ROOT}/server.py"],
                    "env": {"HSS_RESEARCH_SPACE": str(manager.layout.space)},
                }
            },
        },
    )
    (root / "README.md").write_text(
        "# HSS host package\n\nUse `mcp.json` with a stdio MCP client. After moving the directory, run `python configure.py` with the desired Python interpreter. Set `HSS_RESEARCH_SPACE` to the persistent research space.\n\n`plugin.json` uses the EnvFoundry package fields consumed by Qiushi integrations; the host substitutes `RESEARCH_PYTHON` and `PACKAGE_ROOT`. The host owns execution jobs, accounts and UI.\n",
        encoding="utf-8",
    )
    return {
        "package": str(root),
        "mcp": str(root / "mcp.json"),
        "plugin": str(root / "plugin.json"),
        "skills": skills,
    }
