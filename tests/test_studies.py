import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
import statsmodels.api as sm
from hss.empirical.numerics import linear_fit
from hss.study import run, ordered_tasks, normalize
from hss.manager import Manager
from hss.materials import coding, concordance, agreement
from hss.r_export import export_r

ROOT = Path(__file__).resolve().parents[1]
EX = ROOT / "examples"


class StudyTests(unittest.TestCase):
    def test_example_studies_run_end_to_end(self):
        for path in EX.glob("*-study.json"):
            with self.subTest(path=path.name), tempfile.TemporaryDirectory() as tmp:
                result = Manager(Path(tmp) / "space").run_study(
                    json.loads(path.read_text(encoding="utf-8")),
                    Path(tmp) / "result",
                    EX,
                )
                self.assertTrue(Path(result["report"]).is_file())
                records = json.loads(
                    Path(result["results"]).read_text(encoding="utf-8")
                )
                self.assertTrue(
                    all(r["status"] == "completed" for r in records.values())
                )

    def test_hc3_agrees_with_independent_library(self):
        rng = np.random.default_rng(129)
        x = np.c_[np.ones(100), rng.normal(size=(100, 2))]
        y = x @ np.array([1.0, 2.0, 3.0]) + rng.normal(size=100) * (1 + abs(x[:, 1]))
        a = linear_fit(y, x, ["intercept", "x", "z"])
        b = sm.OLS(y, x).fit(cov_type="HC3", use_t=True)
        np.testing.assert_allclose(a["beta"], b.params, atol=1e-12)
        np.testing.assert_allclose(a["vcov"], b.cov_params(), atol=1e-12)

    def test_study_graph_and_unimplemented_method(self):
        with self.assertRaises(ValueError):
            ordered_tasks(
                {
                    "tasks": [
                        {"id": "a", "operation": "table", "source_task": "b"},
                        {"id": "b", "operation": "table", "source_task": "a"},
                    ]
                }
            )
        with self.assertRaises(ValueError):
            normalize({"id": "a", "branch_id": "CA04.group_time"})
        with self.assertRaises(ValueError):
            normalize({"id": "a", "branch_id": "NC03.linear", "operation": "rct"})

    def test_future_features_are_not_used_in_prediction(self):
        study = json.loads((EX / "prediction-study.json").read_text(encoding="utf-8"))
        study["tasks"] = study["tasks"][:1]
        study["tasks"][0]["variable_metadata"]["x1"]["available_at"] = 1
        with (
            tempfile.TemporaryDirectory() as tmp,
            self.assertRaisesRegex(ValueError, "unavailable"),
        ):
            run(study, tmp, EX)

    def test_pca_cannot_preprocess_prediction_test_rows(self):
        study = json.loads((EX / "measurement-study.json").read_text(encoding="utf-8"))
        task = study["tasks"][1]
        task.update(branch_id="NC04.regression", prediction={"split": "iid_holdout"})
        with (
            tempfile.TemporaryDirectory() as tmp,
            self.assertRaisesRegex(ValueError, "training folds"),
        ):
            run(study, tmp, EX)

    def test_unicode_passages_keep_exact_offsets(self):
        text = "我在城里工作。城里有图书馆。"
        docs = [{"id": "a", "text": text}]
        with tempfile.TemporaryDirectory() as tmp:
            rows = concordance({"documents": docs, "query": "城里"}, Path(tmp))[
                "tables"
            ]["concordance"]
            self.assertEqual(
                [text[r["start"] : r["end"]] for r in rows], ["城里", "城里"]
            )
            r = rows[0]
            coded = coding(
                {
                    "documents": docs,
                    "codebook": {"place": "Place reference"},
                    "annotations": [
                        {
                            "document": "a",
                            "start": r["start"],
                            "end": r["end"],
                            "code": "place",
                            "quote": "城里",
                        }
                    ],
                },
                Path(tmp),
            )
            self.assertEqual(coded["tables"]["annotations"][0]["quote"], "城里")

    def test_agreement_known_table(self):
        rows = [
            {"unit": i, "a": a, "b": b}
            for i, (a, b) in enumerate([("A", "A"), ("A", "B"), ("B", "B"), ("B", "B")])
        ]
        result = agreement({"ratings": rows}, None)
        self.assertAlmostEqual(result["cohens_kappa"], 0.5)

    def test_r_export_preserves_explicit_design(self):
        task = {
            "data_contract": {"structure": "panel"},
            "variables": {
                "outcome": "y",
                "unit": "id",
                "time": "year",
                "cohort": "cohort",
            },
            "analysis": {
                "control_group": "notyettreated",
                "aggregation": "dynamic",
                "anticipation": 1,
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = export_r("did", task, EX / "synthetic_panel.csv", tmp)
            text = Path(result["code_file"]).read_text(encoding="utf-8")
            self.assertIn('control_group="notyettreated"', text)
            self.assertIn("anticipation=1", text)
            self.assertFalse(result["executed"])


if __name__ == "__main__":
    unittest.main()
