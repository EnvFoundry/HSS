import csv
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

from hss.api import request
from hss.catalog import Catalog
from hss.manager import Manager
from hss.research import blueprint


class WorkflowTests(unittest.TestCase):
    def test_command_uses_prepared_program_and_resolves_input_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.txt"
            source.write_text("研究材料", encoding="utf-8")
            manager = Manager(root / "space")
            manager.catalog.components["copy-program"] = {
                "id": "copy-program",
                "kind": "command",
                "command": sys.executable,
            }
            manager.bind("copy-program", [sys.executable])
            code = "from pathlib import Path; import sys; Path('copy.txt').write_text(Path(sys.argv[1]).read_text(encoding='utf-8'),encoding='utf-8')"
            manager.run_study(
                {
                    "tasks": [
                        {
                            "id": "copy",
                            "operation": "command",
                            "component": "copy-program",
                            "arguments": ["-c", code, {"path": "source.txt"}],
                        }
                    ]
                },
                root / "results",
                root,
            )
            self.assertEqual(
                (root / "results/copy/copy.txt").read_text(encoding="utf-8"), "研究材料"
            )

    def test_every_direction_has_an_executable_or_authored_research_path(self):
        catalog = Catalog()
        for field in catalog.fields.values():
            for direction in field["directions"]:
                with self.subTest(field=field["id"], direction=direction["id"]):
                    plan = blueprint(
                        catalog, [f"direction:{field['id']}/{direction['id']}"]
                    )
                    self.assertTrue(plan["modules"])
                    self.assertTrue(plan["knowledge"])
                    self.assertTrue(plan["workflows"])
                    for module in plan["modules"]:
                        self.assertTrue(module["inputs"])
                        self.assertTrue(module["outputs"])
                        self.assertTrue(module["guides"])

    def test_sql_to_project_script_to_manuscript(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "observations.csv").write_text(
                "group_name,value\nA,2\nA,4\nB,9\n", encoding="utf-8"
            )
            (root / "analysis.py").write_text(
                'import json,sys\nfrom pathlib import Path\nrequest=json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))\nPath("result.json").write_text(json.dumps({"tables":{"statement":[{"answer":request["parameters"]["value"]*2}]}}),encoding="utf-8")\n',
                encoding="utf-8",
            )
            manager = Manager(root / "space")
            manager.state.bind("python-empirical", [sys.executable])
            # An isolated extension makes this script's stdlib requirement explicit.
            catalog = manager.catalog
            catalog.components["python-example"] = {
                "id": "python-example",
                "kind": "python",
                "imports": [],
            }
            manager.bind("python-example", [sys.executable])
            plan = {
                "tasks": [
                    {
                        "id": "join",
                        "operation": "sql",
                        "datasets": [
                            {
                                "name": "observations",
                                "path": "observations.csv",
                                "types": {"value": "REAL"},
                            }
                        ],
                        "queries": [
                            {
                                "name": "means",
                                "sql": "SELECT group_name, AVG(value) AS mean_value FROM observations GROUP BY group_name",
                            }
                        ],
                    },
                    {
                        "id": "calculation",
                        "operation": "script",
                        "component": "python-example",
                        "script": "analysis.py",
                        "parameters": {"value": 7},
                        "depends_on": ["join"],
                        "source_task": "join",
                        "source_table": "means",
                    },
                ]
            }
            result = manager.run_study(plan, root / "results", root)
            results = json.loads(Path(result["results"]).read_text(encoding="utf-8"))
            self.assertEqual(
                results["join"]["tables"]["means"],
                [
                    {"group_name": "A", "mean_value": 3.0},
                    {"group_name": "B", "mean_value": 9.0},
                ],
            )
            self.assertEqual(
                results["calculation"]["tables"]["statement"][0]["answer"], 14
            )
            forwarded = json.loads(
                (root / "results/calculation/input.json").read_text(encoding="utf-8")
            )
            self.assertEqual(Path(forwarded["data"]), root / "results/join/means.csv")
            output = request(
                {
                    "action": "manuscript",
                    "output": str(root / "writing"),
                    "base": str(root),
                    "document": {
                        "title": "Worked comparison",
                        "sections": [
                            {
                                "heading": "Results",
                                "text": "The synthetic observations have group means of 3 and 9.",
                                "tables": [
                                    {
                                        "result": "results/join/result.json",
                                        "name": "means",
                                    }
                                ],
                            }
                        ],
                    },
                }
            )
            self.assertIn(
                "| A | 3.0 |", Path(output["manuscript"]).read_text(encoding="utf-8")
            )

    def test_project_keeps_supplied_design_and_tasks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            request(
                {
                    "action": "project",
                    "path": str(root),
                    "title": "Interview comparison",
                    "selections": ["interview-coding"],
                    "brief": {
                        "question": "How do participants describe the transition?",
                        "selected_design": "Comparative thematic interviews",
                    },
                    "study": {"tasks": []},
                }
            )
            brief = json.loads((root / "research.json").read_text(encoding="utf-8"))
            self.assertEqual(
                brief["selected_design"], "Comparative thematic interviews"
            )
            self.assertIn("interview-coding", brief["modules"])
            self.assertTrue((root / "analysis/research-guide.md").is_file())

    def test_source_plugin_can_start_without_package_install(self):
        root = Path(__file__).resolve().parents[1]
        manifest = json.loads((root / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["name"], "hss-research")
        self.assertNotEqual(manifest["name"], "hss")
        completed = subprocess.run(
            [sys.executable, "-B", str(root / "connect/server.py")],
            input=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
            + "\n",
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        tools = json.loads(completed.stdout)["result"]["tools"]
        self.assertTrue(
            {"hss_blueprint", "hss_manuscript", "hss_run"}.issubset(
                {t["name"] for t in tools}
            )
        )


@unittest.skipUnless(
    os.environ.get("HSS_RSCRIPT"), "Set HSS_RSCRIPT to run upstream R integration"
)
class RIntegrationTests(unittest.TestCase):
    def test_three_r_methods_execute_and_export_actual_estimates(self):
        rng = random.Random(19)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with (root / "data.csv").open("w", encoding="utf-8", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(
                    [
                        "duration",
                        "event",
                        "age",
                        "x1",
                        "x2",
                        "x3",
                        "psu",
                        "stratum",
                        "weight",
                    ]
                )
                for i in range(300):
                    latent = rng.gauss(0, 1)
                    writer.writerow(
                        [
                            rng.expovariate(0.02),
                            int(rng.random() < 0.8),
                            20 + rng.random() * 50,
                            *[latent + rng.gauss(0, 0.5) for _ in range(3)],
                            i // 5,
                            i // 100,
                            1 + (i % 3),
                        ]
                    )
            manager = Manager(root / "space")
            for component in ("r-survival", "r-lavaan", "r-survey"):
                manager.bind(component, [os.environ["HSS_RSCRIPT"]])
            tasks = [
                {
                    "id": "cox",
                    "operation": "r_analysis",
                    "adapter": "cox",
                    "data": "data.csv",
                    "variables": {
                        "duration": "duration",
                        "event": "event",
                        "features": ["age"],
                    },
                },
                {
                    "id": "factor",
                    "operation": "r_analysis",
                    "adapter": "lavaan",
                    "data": "data.csv",
                    "branch_id": "NC02.factor",
                    "variables": {},
                    "analysis": {"model_syntax": "factor =~ x1 + x2 + x3"},
                },
                {
                    "id": "survey",
                    "operation": "r_analysis",
                    "adapter": "survey",
                    "data": "data.csv",
                    "variables": {"outcome": "age", "weight": "weight"},
                    "data_contract": {
                        "survey_design": {"psu": "psu", "strata": "stratum"}
                    },
                },
            ]
            result = manager.run_study({"tasks": tasks}, root / "results", root)
            results = json.loads(Path(result["results"]).read_text(encoding="utf-8"))
            for name in ("cox", "factor", "survey"):
                self.assertTrue(results[name]["tables"]["estimates"])
                self.assertTrue((root / "results" / name / "fit.rds").is_file())


if __name__ == "__main__":
    unittest.main()
