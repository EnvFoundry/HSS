import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from hss.api import request
from hss.catalog import Catalog, DATA
from hss.manager import Manager
from hss import software


class EnvironmentTests(unittest.TestCase):
    def test_browse_and_empty_selection_do_not_create_space(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "space"
            manager = Manager(root)
            self.assertGreater(manager.catalog.browse()["module_count"], 50)
            self.assertEqual(manager.plan([])["actions"], [])
            self.assertEqual(manager.prepare([])["modules"], [])
            self.assertFalse(root.exists())

    def test_navigation_and_modules_share_one_definition(self):
        c = Catalog()
        for field in c.fields.values():
            expected = set().union(*(set(d["modules"]) for d in field["directions"]))
            actual = c.select(["field:" + field["id"]])
            self.assertEqual(set(actual), expected)
            for d in field["directions"]:
                self.assertEqual(
                    set(c.select([f"direction:{field['id']}/{d['id']}"])),
                    set(d["modules"]),
                )
        self.assertEqual(
            len(c.select(["all", "field:economics", "prediction"])), len(c.modules)
        )

    def test_context_and_assets_exist_for_every_module(self):
        c = Catalog()
        context = c.context(["all"])
        self.assertEqual(len(context["modules"]), len(c.modules))
        for module in c.modules.values():
            for filename in module.get("workflows", []):
                data = json.loads(
                    (DATA / "workflows" / filename).read_text(encoding="utf-8")
                )
                self.assertTrue(data)
        self.assertEqual(
            len(request({"action": "methods"})),
            len(
                json.loads((DATA / "methods.json").read_text(encoding="utf-8"))[
                    "methods"
                ]
            ),
        )

    def test_resource_selection_and_shared_removal(self):
        with tempfile.TemporaryDirectory() as tmp:
            m = Manager(tmp)
            m.prepare(["concept-analysis", "argument-analysis"], software_enabled=False)
            paths = m.layout.describe()
            skill = Path(paths["skills"]) / "hss-theory" / "SKILL.md"
            self.assertTrue(skill.exists())
            self.assertFalse((m.layout["env"] / "software").exists())
            self.assertFalse((m.layout["knowledge"] / "causal.md").exists())
            m.remove(["concept-analysis"])
            self.assertTrue(skill.exists())
            skill.write_text("Local project guidance", encoding="utf-8")
            result = m.remove(["argument-analysis"])
            self.assertIn(str(skill), result["retained"])
            self.assertTrue(skill.exists())

    def test_custom_layout_and_lowercase_system(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "system").mkdir()
            m = Manager(tmp, {"knowledge": "shared/knowledge"})
            m.prepare(["concept-analysis"])
            self.assertTrue((Path(tmp) / "shared/knowledge/theory.md").exists())
            self.assertFalse((Path(tmp) / "System").exists())

    def test_existing_interpreter_reused_and_never_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            m = Manager(tmp)
            with patch(
                "hss.software.install",
                side_effect=AssertionError("unexpected installation"),
            ):
                result = m.prepare(
                    ["descriptive-statistics"],
                    existing=[{"kind": "python", "command": [sys.executable]}],
                )
            self.assertFalse(result["failed"])
            self.assertEqual(result["ready"][0]["command"], [sys.executable])
            m.remove(["descriptive-statistics"], prune=True)
            self.assertTrue(Path(sys.executable).exists())

    def test_python_version_is_not_a_pandoc_binding(self):
        definition = {"id": "pandoc", "kind": "command", "command": "pandoc"}
        with patch("hss.software.shutil.which", return_value=None):
            self.assertIsNone(
                software.find_existing(
                    definition,
                    {"python-empirical": {"command": [sys.executable]}},
                    [{"command": [sys.executable]}],
                )
            )

    def test_context_uses_the_prepared_alternative(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = Manager(tmp)
            result = manager.prepare(
                ["regression-discontinuity"],
                backends={"regression-discontinuity": "local-randomization"},
            )
            self.assertFalse(result["failed"])
            context = manager.context(["regression-discontinuity"])
            self.assertIn("python-empirical", context["bindings"])
            self.assertNotIn("r-rdrobust", context["bindings"])

    def test_missing_r_is_pending_not_installed(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch("hss.software.shutil.which", return_value=None),
        ):
            result = Manager(tmp).prepare(["survey-analysis"])
            self.assertEqual(result["ready"], [])
            self.assertEqual(result["pending"][0]["status"], "connection_needed")

    def test_managed_dependency_retained_while_shared(self):
        with tempfile.TemporaryDirectory() as tmp:
            m = Manager(tmp)
            location = m.layout["env"] / "software/test"
            location.mkdir(parents=True)
            m.state.bind(
                "python-empirical",
                [sys.executable],
                managed=True,
                location=str(location),
            )
            m.prepare(
                ["descriptive-statistics", "linear-association"], software_enabled=False
            )
            m.remove(["descriptive-statistics"], prune=True)
            self.assertTrue(location.exists())
            m.remove(["linear-association"], prune=True)
            self.assertFalse(location.exists())

    def test_resource_only_preparation_lists_unprepared_software(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch("hss.software.find_existing", return_value=None),
            patch(
                "hss.software.install", side_effect=AssertionError("unexpected install")
            ),
        ):
            result = Manager(tmp).prepare(["prediction"], software_enabled=False)
            self.assertEqual(result["pending"][0]["status"], "not_prepared")


if __name__ == "__main__":
    unittest.main()
