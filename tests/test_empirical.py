import json, unittest
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import stats
from hss.empirical import causal as ca, descriptive as nc
from hss.empirical.numerics import cluster_meat
from hss.study import clean

EX = Path(__file__).resolve().parents[1] / "examples"


def example(name):
    return json.loads((EX / name).read_text())


def rct_task():
    return example("randomized-study.json")["tasks"][1]


def prediction_task():
    return example("prediction-study.json")["tasks"][0]


def df():
    return pd.read_csv(EX / "synthetic_individual.csv")


class CausalNumericalTests(unittest.TestCase):
    def test_rct_equals_difference_in_means(self):
        data = df()
        t = rct_task()
        t["variables"]["controls"] = []
        r = ca.rct(t, data)
        self.assertAlmostEqual(
            r["estimates"][0]["estimate"],
            data.loc[data.d == 1, "y"].mean() - data.loc[data.d == 0, "y"].mean(),
            12,
        )

    def test_lin_known_effect_simulation(self):
        self.assertLess(
            abs(ca.rct(rct_task(), df())["estimates"][0]["estimate"] - 1.8), 0.25
        )

    def test_iv_equals_wald_ratio(self):
        data = df()
        t = example("adjusted-study.json")["tasks"][0]
        t["variables"]["controls"] = []
        r = ca.iv(t, data)
        wald = (
            data.loc[data.z == 1, "iv_y"].mean() - data.loc[data.z == 0, "iv_y"].mean()
        ) / (
            data.loc[data.z == 1, "dose"].mean() - data.loc[data.z == 0, "dose"].mean()
        )
        self.assertAlmostEqual(r["estimates"][0]["estimate"], wald, 10)

    def test_iv_underidentification_rejected(self):
        data = df()
        data["z"] = 1
        t = example("adjusted-study.json")["tasks"][0]
        with self.assertRaises(ValueError):
            ca.iv(t, data)

    def test_aipw_known_effect(self):
        t = example("adjusted-study.json")["tasks"][1]
        r = ca.aipw(t, df())
        self.assertLess(abs(r["estimates"][0]["estimate"] - 1.8), 0.3)
        self.assertTrue(all(x["overlap_count"] == 0 for x in r["tables"]["crossfit"]))

    def test_aipw_does_not_relabel_att(self):
        t = example("adjusted-study.json")["tasks"][1]
        t["estimand"]["kind"] = "ATT"
        with self.assertRaises(ValueError):
            ca.aipw(t, df())

    def test_dml_irm_executes(self):
        t = example("adjusted-study.json")["tasks"][1]
        self.assertLess(
            abs(ca.aipw(t, df(), True)["estimates"][0]["estimate"] - 1.8), 0.4
        )

    def test_crossfit_keeps_clusters_whole(self):
        t = rct_task()
        t["inference"] = {"cluster": "cluster"}
        data = df()
        for tr, te in ca.crossfits(t, data, data.d.to_numpy()):
            self.assertFalse(set(data.cluster.iloc[tr]) & set(data.cluster.iloc[te]))

    def test_plr_parameter(self):
        rng = np.random.default_rng(123)
        n = 900
        x = rng.normal(size=n)
        d = x + rng.normal(size=n)
        data = pd.DataFrame({"x": x, "d": d, "y": 2 * d + x + rng.normal(size=n)})
        t = {
            "variables": {"outcome": "y", "treatment": "d", "controls": ["x"]},
            "estimand": {"kind": "partial_linear_parameter"},
            "analysis": {"folds": 3, "seed": 123},
        }
        r = ca.dml_plr(t, data)
        self.assertLess(abs(r["estimates"][0]["estimate"] - 2), 0.15)

    def test_did_known_effect(self):
        p = example("policy-study.json")
        r = ca.did_2x2(p["tasks"][0], pd.read_csv(EX / "synthetic_panel.csv"))
        self.assertLess(abs(r["estimates"][0]["estimate"] - 2.2), 0.15)
        self.assertEqual(
            r["details"]["pretrend_test"], "not_identified_with_one_preperiod"
        )

    def test_multiperiod_not_2x2(self):
        t = example("policy-study.json")["tasks"][0]
        data = pd.read_csv(EX / "synthetic_panel.csv")
        third = data[data.time == 1].copy()
        third["time"] = 2
        with self.assertRaises(ValueError):
            ca.did_2x2(t, pd.concat([data, third]))

    def test_unbalanced_did_not_silently_dropped(self):
        t = example("policy-study.json")["tasks"][0]
        with self.assertRaises(ValueError):
            ca.did_2x2(t, pd.read_csv(EX / "synthetic_panel.csv").iloc[1:])

    def test_cluster_order_invariance(self):
        t = rct_task()
        t["inference"] = {"cluster": "cluster"}
        data = df()
        r1 = ca.rct(t, data)["estimates"][0]
        r2 = ca.rct(t, data.sample(frac=1, random_state=9))["estimates"][0]
        self.assertAlmostEqual(r1["std_error"], r2["std_error"], 12)

    def test_local_rd_fuzzy_rejected(self):
        t = rct_task()
        t["variables"]["running"] = "x1"
        t["analysis"]["window"] = [-2, 2]
        with self.assertRaises(ValueError):
            ca.local_rd(t, df())

    def test_local_randomization_window_success(self):
        rng = np.random.default_rng(871)
        r = rng.uniform(-2, 2, 400)
        d = (r >= 0).astype(int)
        data = pd.DataFrame(
            {"r": r, "d": d, "y": 1.5 * d + rng.normal(scale=0.1, size=400)}
        )
        t = {
            "variables": {"running": "r", "treatment": "d", "outcome": "y"},
            "estimand": {"kind": "local_RD"},
            "analysis": {"window": [-1, 1]},
            "design": {"cutoff": 0},
        }
        ans = ca.local_rd(t, data)
        self.assertLess(abs(ans["estimates"][0]["estimate"] - 1.5), 0.05)
        self.assertEqual(ans["details"]["n_window"], int((np.abs(r) <= 1).sum()))

    def test_rcs_did_cell_means(self):
        rows = [
            {"g": g, "t": t, "y": 1 + g + 2 * t + 2 * g * t + (j - 9.5) / 100}
            for g in [0, 1]
            for t in [0, 1]
            for j in range(20)
        ]
        task = {
            "branch_id": "CA04.two_period_rcs",
            "variables": {"treatment": "g", "time": "t", "outcome": "y"},
            "estimand": {"kind": "ATT"},
        }
        self.assertAlmostEqual(
            ca.did_2x2(task, pd.DataFrame(rows))["estimates"][0]["estimate"], 2, 12
        )

    def test_synthetic_control_has_no_invented_interval(self):
        data = pd.DataFrame(
            [
                {"unit": u, "time": t, "y": t + (2 if u == "T" and t >= 4 else 0)}
                for u in ["T", "A", "B"]
                for t in range(6)
            ]
        )
        t = {
            "variables": {"unit": "unit", "time": "time", "outcome": "y"},
            "analysis": {
                "treated_unit": "T",
                "donor_units": ["A", "B"],
                "treatment_start": 4,
            },
        }
        r = ca.synthetic_control(t, data)
        self.assertAlmostEqual(r["estimates"][0]["estimate"], 2, 8)
        self.assertIsNone(r["estimates"][0]["ci_low"])
        self.assertIn("synthetic_control_inference", r["follow_up"])

    def test_one_cluster_cannot_support_cr1(self):
        with self.assertRaises(ValueError):
            cluster_meat(np.ones((4, 2)), np.zeros(4))


class NoncausalNumericalTests(unittest.TestCase):
    def test_ols_agrees_with_independent_simple_regression(self):
        data = df()
        t = {"variables": {"outcome": "y", "features": ["x1"]}}
        r = nc.ols(t, data)
        slope = stats.linregress(data.x1, data.y).slope
        self.assertAlmostEqual(r["estimates"][1]["estimate"], slope, 12)

    def test_gini_known_two_person_distribution(self):
        self.assertAlmostEqual(
            nc.distribution(
                {"variables": {"outcome": "y"}}, pd.DataFrame({"y": [0.0, 2.0]})
            )["estimates"][0]["gini"],
            0.5,
        )

    def test_negative_gini_not_manufactured(self):
        self.assertIsNone(
            nc.distribution(
                {"variables": {"outcome": "y"}}, pd.DataFrame({"y": [-1.0, 2.0]})
            )["estimates"][0]["gini"]
        )

    def test_weighted_mean(self):
        self.assertAlmostEqual(
            nc.summary(
                {"variables": {"outcome": "y", "weight": "w"}},
                pd.DataFrame({"y": [1.0, 4.0], "w": [3.0, 1.0]}),
            )["estimates"][0]["mean"],
            1.75,
        )

    def test_wls_exact_line(self):
        data = pd.DataFrame(
            {"x": [0.0, 1, 2, 3], "y": [1.0, 3, 5, 7], "w": [1.0, 3, 2, 4]}
        )
        r = nc.ols(
            {"variables": {"outcome": "y", "features": ["x"], "weight": "w"}}, data
        )
        self.assertAlmostEqual(r["estimates"][0]["estimate"], 1, 12)
        self.assertAlmostEqual(r["estimates"][1]["estimate"], 2, 12)

    def test_theil_known_two_person_distribution(self):
        self.assertAlmostEqual(
            nc.distribution(
                {"variables": {"outcome": "y"}}, pd.DataFrame({"y": [0.0, 2.0]})
            )["estimates"][0]["theil"],
            np.log(2),
        )

    def test_pca_loadings_orthonormal(self):
        r = nc.pca(
            {
                "variables": {"features": ["x1", "x2", "x3"]},
                "analysis": {"components": 2},
            },
            df(),
        )
        a = np.array(
            [[row[k] for k in ["x1", "x2", "x3"]] for row in r["tables"]["loadings"]]
        )
        np.testing.assert_allclose(a @ a.T, np.eye(2), atol=1e-12)

    def test_predict_beats_training_mean(self):
        data = df()
        data["y"] = 3 * data.x1 - 2 * data.x2
        r = nc.predict(prediction_task(), data)
        self.assertLess(
            r["tables"]["performance"][0]["rmse"],
            r["tables"]["performance"][1]["rmse"] / 10,
        )

    def test_categorical_prediction(self):
        t = prediction_task()
        data = df()
        data["cat"] = np.where(data.x1 > 0, "A", "B")
        t["variables"]["features"].append("cat")
        t["analysis"]["categorical"] = ["cat"]
        self.assertEqual(nc.predict(t, data)["details"]["train_test_overlap"], 0)

    def test_prediction_missing_requires_imputation_plan(self):
        t = prediction_task()
        data = df()
        data.loc[0, "x1"] = np.nan
        with self.assertRaises(ValueError):
            nc.predict(t, data)

    def test_forward_split_entire_time_blocks(self):
        t = prediction_task()
        t["prediction"].update(split="time_forward", time_column="time")
        data = df()
        data["time"] = np.repeat(np.arange(60), 10)
        tr, te = nc.split_indices(t, data, data.y.to_numpy())
        self.assertLess(data.time.iloc[tr].max(), data.time.iloc[te].min())

    def test_group_split_disjoint(self):
        t = prediction_task()
        t["prediction"].update(split="group_holdout", group_column="cluster")
        data = df()
        tr, te = nc.split_indices(t, data, data.y.to_numpy())
        self.assertFalse(set(data.cluster.iloc[tr]) & set(data.cluster.iloc[te]))

    def test_classification_calibration_bin_counts(self):
        t = example("prediction-study.json")["tasks"][1]
        r = nc.predict(t, df())
        self.assertEqual(
            sum(x["n"] for x in r["tables"]["calibration"]), r["details"]["n_test"]
        )

    def test_km_ties_and_censoring(self):
        data = pd.DataFrame({"duration": [1, 2, 2, 3], "event": [1, 1, 0, 1]})
        rows = nc.kaplan_meier(
            {"variables": {"duration": "duration", "event": "event"}}, data
        )["tables"]["survival"]
        self.assertAlmostEqual(rows[0]["survival"], 0.75)
        self.assertAlmostEqual(rows[1]["survival"], 0.5)
        self.assertEqual(rows[2]["survival"], 0)

    def test_observed_triangle(self):
        r = nc.network(
            {"variables": {"source": "s", "target": "t"}},
            pd.DataFrame({"s": ["a", "b", "c"], "t": ["b", "c", "a"]}),
        )
        self.assertEqual(r["estimates"][0]["density"], 1)
        self.assertTrue(all(x["local_clustering"] == 1 for x in r["tables"]["nodes"]))

    def test_moran_requires_weights_alignment(self):
        t = {
            "variables": {"outcome": "y", "unit": "id"},
            "analysis": {
                "spatial_weights": [[0, 1], [1, 0]],
                "weights_unit_order": [1, 0],
            },
        }
        with self.assertRaises(ValueError):
            nc.moran(t, pd.DataFrame({"id": [0, 1], "y": [0.0, 1.0]}))

    def test_moran_known_alternating_graph(self):
        W = np.ones((4, 4)) - np.eye(4)
        t = {
            "variables": {"outcome": "y", "unit": "id"},
            "analysis": {
                "spatial_weights": W.tolist(),
                "weights_unit_order": list(range(4)),
                "permutations": 19,
            },
        }
        self.assertAlmostEqual(
            nc.moran(t, pd.DataFrame({"id": range(4), "y": [1, 2, 3, 4]}))["estimates"][
                0
            ]["morans_i"],
            -1 / 3,
        )

    def test_oaxaca_identity(self):
        data = df()
        t = {
            "variables": {"outcome": "y", "features": ["x1", "x2"], "group": "d"},
            "analysis": {"bootstrap_repetitions": 19},
        }
        r = nc.oaxaca(t, data)
        self.assertLess(abs(r["details"]["sum_identity_error"]), 1e-12)

    def test_common_effect_meta_closed_form(self):
        r = nc.meta(
            {"variables": {"effect": "e", "se": "se"}, "method_id": "f35.fixed_meta"},
            pd.DataFrame({"e": [1.0, 3.0], "se": [1.0, 1.0]}),
        )
        self.assertAlmostEqual(r["estimates"][0]["estimate"], 2)
        self.assertAlmostEqual(r["estimates"][0]["std_error"], 1 / np.sqrt(2))

    def test_holm_and_bh_reference_values(self):
        rows = nc.multiple_testing(
            {"variables": {"p_value": "p"}}, pd.DataFrame({"p": [0.01, 0.04, 0.03]})
        )["tables"]["adjusted_p"]
        np.testing.assert_allclose([r["p_holm"] for r in rows], [0.03, 0.06, 0.06])
        np.testing.assert_allclose([r["q_bh"] for r in rows], [0.03, 0.04, 0.04])

    def test_conformal_no_finite_quantile_when_rank_too_large(self):
        t = example("prediction-study.json")["tasks"][2]
        t["analysis"]["alpha"] = 0.0001
        r = nc.conformal(t, df())
        self.assertFalse(r["details"]["finite_interval"])
        self.assertIsNone(r["estimates"][0]["interval_width"])

    def test_ar_rolling_known_linear_trend(self):
        data = pd.DataFrame({"time": range(50), "y": np.arange(50, dtype=float)})
        r = nc.autoreg(
            {"variables": {"time": "time", "outcome": "y"}, "analysis": {"lags": 1}},
            data,
        )
        self.assertLess(r["estimates"][0]["rmse"], 1e-10)

    def test_chinese_topic_requires_tokenization(self):
        with self.assertRaises(ValueError):
            nc.topic(
                {"variables": {"text": "text"}, "analysis": {"language": "zh"}},
                pd.DataFrame({"text": ["研究社会方法"] * 10}),
            )

    def test_supported_prediction_learners_smoke(self):
        for method in [
            "ridge",
            "lasso",
            "elastic_net",
            "random_forest",
            "gradient_boosting",
        ]:
            t = prediction_task()
            t["selected_method_id"] = "f11." + method
            r = nc.predict(t, df())
            self.assertTrue(np.isfinite(r["estimates"][0]["rmse"]))

    def test_supported_classifiers_smoke(self):
        for method in ["logit", "random_forest", "gradient_boosting"]:
            t = example("prediction-study.json")["tasks"][1]
            t["selected_method_id"] = (
                "f05.logit" if method == "logit" else "f11." + method
            )
            r = nc.predict(t, df())
            self.assertTrue(0 <= r["estimates"][0]["accuracy"] <= 1)

    def test_text_classifier_fits_train_only(self):
        data = pd.DataFrame(
            {
                "text": [
                    "政策 改革 成功" if j % 2 else "政策 失败 冲突" for j in range(100)
                ],
                "label": [j % 2 for j in range(100)],
            }
        )
        t = {
            "variables": {"text": "text", "outcome": "label"},
            "outcome_type": "binary",
            "prediction": {"split": "iid_holdout"},
            "analysis": {"analyzer": "char"},
            "selected_method_id": "f14.text_classifier",
        }
        r = nc.predict(t, data, True)
        self.assertEqual(r["details"]["train_test_overlap"], 0)

    def test_topic_reference_smoke(self):
        data = pd.DataFrame(
            {
                "text": [
                    "research science method",
                    "social policy education",
                    "research education science",
                    "policy social method",
                ]
                * 5
            }
        )
        r = nc.topic({"variables": {"text": "text"}, "analysis": {"topics": 2}}, data)
        self.assertEqual(len(r["tables"]["topics"]), 2)

    def test_kmeans_stability_separated_clusters(self):
        rng = np.random.default_rng(333)
        data = pd.DataFrame(
            np.r_[rng.normal(-5, 0.1, (40, 2)), rng.normal(5, 0.1, (40, 2))],
            columns=["x", "z"],
        )
        r = nc.kmeans(
            {"variables": {"features": ["x", "z"]}, "analysis": {"n_clusters": 2}}, data
        )
        self.assertTrue(
            all(x["adjusted_rand"] > 0.99 for x in r["tables"]["stability"])
        )

    def test_dl_random_effect_meta_smoke(self):
        data = pd.DataFrame({"e": [0.0, 2.0, 4.0], "se": [0.1, 0.1, 0.1]})
        r = nc.meta(
            {
                "variables": {"effect": "e", "se": "se"},
                "selected_method_id": "f35.random_meta",
            },
            data,
        )
        self.assertGreater(r["details"]["tau2_DL"], 0)
        self.assertAlmostEqual(r["estimates"][0]["estimate"], 2)

    def test_nonfinite_json_is_valid_json(self):
        self.assertEqual(
            json.loads(json.dumps(clean({"x": np.inf}), allow_nan=False)), {"x": None}
        )
