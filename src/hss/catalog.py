"""One catalogue supplies navigation, installation and research context."""

import copy
import json
from pathlib import Path

DATA = Path(__file__).parent / "data"


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


class Catalog:
    def __init__(self, extension=None):
        self.extension_root = Path(extension).resolve().parent if extension else None
        self.data = read_json(DATA / "catalog.json")
        if extension:
            extra = read_json(extension)
            for kind in ("fields", "modules", "components", "bundles", "resources"):
                existing = {x["id"] for x in self.data[kind]}
                for item in extra.get(kind, []):
                    if item["id"] in existing:
                        raise ValueError(f"Duplicate {kind} entry: {item['id']}")
                    self.data[kind].append(item)
                    existing.add(item["id"])
        for kind in ("fields", "modules", "components", "bundles", "resources"):
            setattr(self, kind, {x["id"]: x for x in self.data[kind]})
        self._check_references()

    def _check_references(self):
        for field in self.fields.values():
            seen = set()
            for direction in field["directions"]:
                if direction["id"] in seen:
                    raise ValueError(f"Duplicate direction in {field['id']}")
                seen.add(direction["id"])
                for name in direction["modules"]:
                    if name not in self.modules:
                        raise ValueError(f"Unknown module: {name}")
        for module in self.modules.values():
            for name in module.get("requires", []):
                if name not in self.modules:
                    raise ValueError(f"Unknown module dependency: {name}")
            for name in module.get("components", []):
                if name not in self.components:
                    raise ValueError(f"Unknown software component: {name}")
        for bundle in self.bundles.values():
            self.select(bundle["modules"])

    def browse(self, field=None):
        fields = [self.fields[field]] if field else self.fields.values()
        rows = []
        for item in fields:
            entry = copy.deepcopy(item)
            entry["module_count"] = len(
                {m for d in item["directions"] for m in d["modules"]}
            )
            rows.append(entry)
        return {
            "fields": rows,
            "module_count": len(self.modules),
            "bundles": list(self.bundles.values()),
        }

    def select(self, selections):
        """Expand explicit field/direction/bundle selections and module dependencies."""
        chosen, visiting = [], set()

        def add(name):
            if name in chosen:
                return
            if name in visiting:
                raise ValueError(f"Circular module dependency: {name}")
            if name not in self.modules:
                raise ValueError(f"Unknown module: {name}")
            visiting.add(name)
            for dependency in self.modules[name].get("requires", []):
                add(dependency)
            visiting.remove(name)
            chosen.append(name)

        for selection in selections:
            if selection == "all":
                names = list(self.modules)
            elif selection.startswith("field:"):
                field = self.fields[selection[6:]]
                names = [m for d in field["directions"] for m in d["modules"]]
            elif selection.startswith("direction:"):
                field_id, direction_id = selection[10:].split("/", 1)
                direction = next(
                    (
                        d
                        for d in self.fields[field_id]["directions"]
                        if d["id"] == direction_id
                    ),
                    None,
                )
                if direction is None:
                    raise ValueError(f"Unknown direction: {selection}")
                names = direction["modules"]
            elif selection.startswith("bundle:"):
                names = self.bundles[selection[7:]]["modules"]
            else:
                names = [selection]
            for name in names:
                add(name)
        return chosen

    def search(self, query="", field=None, direction=None, kind=None):
        if direction and not field:
            raise ValueError("A direction needs its field")
        selected = (
            set(
                self.select(
                    [
                        f"direction:{field}/{direction}"
                        if direction
                        else f"field:{field}"
                    ]
                )
            )
            if field
            else set(self.modules)
        )
        terms = query.casefold().split()
        results = []
        for item in self.modules.values():
            if item["id"] not in selected or (kind and item["kind"] != kind):
                continue
            haystack = json.dumps(item, ensure_ascii=False).casefold()
            if all(term in haystack for term in terms):
                paths = [
                    {"field": f["id"], "direction": d["id"]}
                    for f in self.fields.values()
                    for d in f["directions"]
                    if item["id"] in d["modules"]
                ]
                results.append({**item, "paths": paths})
        return results

    def methods(self, query="", family=None, executable=None):
        items = read_json(DATA / "methods.json")["methods"]
        terms = query.casefold().split()
        return [
            m
            for m in items
            if (not family or m["family"] == family)
            and (executable is None or bool(m.get("operation")) == executable)
            and all(t in json.dumps(m, ensure_ascii=False).casefold() for t in terms)
        ]

    def context(self, selections):
        modules = [copy.deepcopy(self.modules[m]) for m in self.select(selections)]
        guides = {}
        skills = {}
        for module in modules:
            for path in module.get("knowledge", []):
                guides[path] = self.asset("knowledge", path).read_text(encoding="utf-8")
            skill = module.get("skill")
            if skill:
                skills[skill] = self.asset("skills", skill + "/SKILL.md").read_text(
                    encoding="utf-8"
                )
        operation_ids = {
            op for module in modules for op in module.get("operations", [])
        }
        operations = [
            op
            for op in read_json(DATA / "operations.json")
            if op["id"] in operation_ids
        ]
        return {
            "modules": modules,
            "knowledge": guides,
            "skills": skills,
            "operations": operations,
        }

    def asset(self, kind, name):
        if self.extension_root and (self.extension_root / kind / name).is_file():
            return self.extension_root / kind / name
        return DATA / kind / name
