"""Host-configurable resource areas within a persistent research space."""

import os
from pathlib import Path

AREAS = {
    "env": "env/hss",
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
            self.areas[name] = (
                path if path.is_absolute() else self.space / path
            ).resolve()

    def __getitem__(self, area):
        return self.areas[area]

    def describe(self):
        return {name: str(path) for name, path in self.areas.items()}
