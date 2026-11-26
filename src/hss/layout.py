"""Host-configurable resource areas within a persistent research space."""

import os
from pathlib import Path

AREAS = {
    "env": "software/hss",
    "skills": "skills",
    "knowledge": "knowledge/hss",
    "workflows": "workflows/hss",
    "prompts": "prompts/hss",
    "plugins": "plugins/hss",
    "mcp": "mcp/hss",
    "databases": "databases/hss",
    "cache": "cache/hss",
}


class Layout:
    def __init__(self, space=None, areas=None):
        self.space = (
            Path(space or os.environ.get("HSS_RESEARCH_SPACE", "~/.hss"))
            .expanduser()
            .resolve()
        )
        system = self.space / "System"
        if not system.exists() and (self.space / "system").is_dir():
            system = self.space / "system"
        self.system = system
        unknown = set(areas or {}) - set(AREAS)
        if unknown:
            raise ValueError("Unknown resource areas: " + ", ".join(sorted(unknown)))
        self.areas = {}
        for name, suffix in AREAS.items():
            value = (areas or {}).get(name)
            path = Path(value).expanduser() if value else system / suffix
            if name == "env" and not value and not path.exists() and (system / "env/hss").is_dir():
                path = system / "env/hss"
            self.areas[name] = (
                path if path.is_absolute() else self.space / path
            ).resolve()

    def __getitem__(self, area):
        return self.areas[area]

    def describe(self):
        return {name: str(path) for name, path in self.areas.items()}

    def component_root(self, component):
        root = self["env"]
        return (root if root == self.system / "software/hss" else root / "software") / component
