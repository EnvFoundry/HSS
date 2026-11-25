"""Estimators for explicitly specified research designs."""

import numpy as np
from scipy import optimize
from sklearn.base import clone
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.linear_model import Ridge, LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import StratifiedKFold, KFold, GroupKFold
from .numerics import (
    numeric,
    linear_fit,
    interval,
    score_inference,
    effective_n,
    standardized_difference,
)


def columns(task):
    return task.get("variables", {})


def cluster(task, data):
    key = task.get("inference", {}).get("cluster")
    return None if not key else data[key].to_numpy()


def binary(d):
    if set(np.unique(d)) != {0, 1}:
        raise ValueError("Both binary treatment levels 0 and 1 required")


def no_weights(task):
    if columns(task).get("weight"):
        raise ValueError(
            "This causal adapter does not implement sampling or assignment weights"
        )


def packed_fit(fit, term, estimand):
    effect = next(r for r in fit["coefficients"] if r["term"] == term)
    return dict(
        estimates=[dict(estimand=estimand, **effect)],
        tables={"coefficients": fit["coefficients"]},
        details={
            "n": fit["n"],
            "independent_units": fit["independent_units"],
            "covariance": fit["covariance"],
            "inference_limit": "常规HC3或CR1参考实现；方法级与项目级条件仍须分析。",
        },
        notes=fit["notes"],
        uncertainty={
            "type": "asymptotic_parameter_interval",
            "covariance": fit["covariance"],
        },
    )


def rct(task, data):
    no_weights(task)
    v = columns(task)
    y = numeric(data, [v["outcome"]]).ravel()
    d = numeric(data, [v["treatment"]]).ravel()
    binary(d)
    xcols = v.get("controls", [])
    parts = [np.ones(len(data)), d]
    names = ["intercept", "treatment"]
    if xcols:
        x = numeric(data, xcols)
        center = x - x.mean(axis=0)
        parts.extend(center[:, j] for j in range(center.shape[1]))
        names.extend(xcols)
        parts.extend(d * center[:, j] for j in range(center.shape[1]))
        names.extend("treatment:" + x for x in xcols)
    X = np.column_stack(parts)
    fit = linear_fit(
        y,
        X,
        names,
        groups=cluster(task, data),
        alpha=task.get("inference", {}).get("alpha", 0.05),
    )
    ans = packed_fit(fit, "treatment", task["estimand"]["kind"])
    ans["details"].update(
        n_treated=int(d.sum()),
        n_control=int((1 - d).sum()),
        baseline_balance_smd=standardized_difference(numeric(data, xcols), d)
        if xcols
        else [],
    )
    ans["notes"].append("随机平衡只用于实施分析，不能单独证明或否定随机化。")
    return ans


def iv(task, data):
    no_weights(task)
    v = columns(task)
    y = numeric(data, [v["outcome"]]).ravel()
    d = numeric(data, [v["treatment"]]).ravel()
    zcols = v.get("instruments", [])
    if not zcols:
        raise ValueError("At least one excluded instrument required")
    xcols = v.get("controls", [])
    n = len(data)
    C = np.column_stack([np.ones(n), numeric(data, xcols)])
    Z = np.column_stack([C, numeric(data, zcols)])
    X = np.column_stack([C, d])
    k = X.shape[1]
    q = len(zcols)
    if n <= Z.shape[1] or np.linalg.matrix_rank(Z) < Z.shape[1]:
        raise ValueError("Instrument design is rank deficient or undersized")
    Xhat = Z @ np.linalg.lstsq(Z, X, rcond=None)[0]
    G = Xhat.T @ X
    if np.linalg.matrix_rank(G) < k:
        raise ValueError("Underidentified IV design")
    bread = np.linalg.inv(G)
    beta = bread @ (Xhat.T @ y)
    u = y - X @ beta
    scores = Xhat * u[:, None]
    groups = cluster(task, data)
    notes = []
    if groups is not None:
        from .numerics import cluster_meat

        meat, Gn = cluster_meat(scores, groups)
        cov = bread @ meat @ bread * Gn / (Gn - 1) * (n - 1) / (n - k)
        df = Gn - 1
        if Gn < 30:
            notes.append("少簇IV推断需要额外分析；常规CR1并非弱工具稳健。")
    else:
        cov = bread @ (scores.T @ scores) @ bread * n / (n - k)
        df = n - k
        Gn = n
    effect = interval(
        beta[-1],
        np.sqrt(max(cov[-1, -1], 0)),
        df,
        task.get("inference", {}).get("alpha", 0.05),
    )
    fs = linear_fit(d, Z, ["intercept"] + xcols + zcols, groups=groups, cov_type="HC1")
    bb = fs["beta"][-q:]
    vv = fs["vcov"][-q:, -q:]
    first_wald = float(bb @ np.linalg.pinv(vv) @ bb / q)
    notes.append(
        "排除限制与工具独立性不是第一阶段检验能证明的；该Wald区间不对弱工具稳健。"
    )

    return dict(
        estimates=[dict(estimand=task["estimand"]["kind"], **effect)],
        tables={"first_stage": fs["coefficients"]},
        details={
            "n": n,
            "independent_units": Gn,
            "excluded_instruments": q,
            "first_stage_robust_wald_F": first_wald,
            "weak_robust_inference_computed": False,
        },
        notes=notes,
        uncertainty={"type": "wald_interval_not_weak_iv_robust"},
    )


def crossfits(task, data, d):
    folds = int(task.get("analysis", {}).get("folds", 5))
    seed = int(task.get("analysis", {}).get("seed", 20261020))
    groups = cluster(task, data)
    if folds < 2:
        raise ValueError("Cross-fitting requires at least two folds")
    if groups is not None:
        if len(np.unique(groups)) < folds:
            raise ValueError("Too few clusters for requested cross-fitting")
        return list(GroupKFold(n_splits=folds).split(data, d, groups))
    if set(np.unique(d)) == {0, 1}:
        if min(np.sum(d == 0), np.sum(d == 1)) < folds:
            raise ValueError("Too few treatment observations per fold")
        return list(
            StratifiedKFold(folds, shuffle=True, random_state=seed).split(data, d)
        )
    return list(KFold(folds, shuffle=True, random_state=seed).split(data))


def aipw(task, data, flexible=False):
    no_weights(task)
    v = columns(task)
    features = v.get("controls", v.get("features", []))
    if not features:
        raise ValueError(
            "Specify baseline covariates, even for this demonstration adapter"
        )
    x = numeric(data, features)
    d = numeric(data, [v["treatment"]]).ravel()
    y = numeric(data, [v["outcome"]]).ravel()
    binary(d)
    n = len(data)
    e = np.full(n, np.nan)
    mu0 = e.copy()
    mu1 = e.copy()
    seed = int(task.get("analysis", {}).get("seed", 20261020))
    reg = (
        RandomForestRegressor(
            n_estimators=100,
            min_samples_leaf=12,
            max_depth=6,
            random_state=seed,
            n_jobs=1,
        )
        if flexible
        else make_pipeline(StandardScaler(), Ridge(alpha=1.0))
    )
    clf = (
        RandomForestClassifier(
            n_estimators=100,
            min_samples_leaf=15,
            max_depth=6,
            random_state=seed,
            n_jobs=1,
        )
        if flexible
        else make_pipeline(StandardScaler(), LogisticRegression(C=1e6, max_iter=2000))
    )
    fold_log = []
    for j, (train, test) in enumerate(crossfits(task, data, d)):
        if set(np.unique(d[train])) != {0, 1}:
            raise ValueError("A cross-fit training fold lacks a treatment group")
        fit = clone(clf).fit(x[train], d[train])
        e[test] = fit.predict_proba(x[test])[:, 1]
        for level, target in [(0, mu0), (1, mu1)]:
            tr = train[d[train] == level]
            if len(tr) < 5:
                raise ValueError("Outcome nuisance training group too small")
            target[test] = clone(reg).fit(x[tr], y[tr]).predict(x[test])
        fold_log.append(
            {
                "fold": j,
                "n_train": len(train),
                "n_test": len(test),
                "overlap_count": len(set(train) & set(test)),
            }
        )
    raw = e.copy()
    eps = task.get("analysis", {}).get("clip_epsilon")
    if eps is not None:
        eps = float(eps)
        if not 0 < eps < 0.5:
            raise ValueError("clip_epsilon must be between 0 and .5")
        e = np.clip(e, eps, 1 - eps)
    if ((e <= 0) | (e >= 1)).any():
        raise ValueError(
            "Estimated zero/one propensity: review positivity; clipping cannot be silently introduced"
        )
    score = mu1 - mu0 + d * (y - mu1) / e - (1 - d) * (y - mu0) / (1 - e)
    if task["estimand"]["kind"] != "ATE":
        raise ValueError(
            "This AIPW adapter is explicitly ATE only; ATT needs a different score"
        )
    est = score_inference(
        score, cluster(task, data), task.get("inference", {}).get("alpha", 0.05)
    )
    notes = []
    if (raw != e).any():
        notes.append("使用预设倾向概率截断；由此产生偏差和敏感性需要报告。")
    if raw.min() < 0.02 or raw.max() > 0.98:
        notes.append("估计倾向概率接近边界，需额外重叠与有限样本分析。")
    weights = d / e + (1 - d) / (1 - e)
    return dict(
        estimates=[dict(estimand="ATE", **est)],
        tables={"crossfit": fold_log},
        details={
            "n": n,
            "min_raw_propensity": float(raw.min()),
            "max_raw_propensity": float(raw.max()),
            "clipped_fraction": float(np.mean(raw != e)),
            "weight_effective_n": effective_n(weights),
            "baseline_smd": standardized_difference(x, d),
            "weighted_smd": standardized_difference(x, d, weights),
            "crossfit_predictions": True,
            "unmeasured_confounding_solved": False,
        },
        notes=notes,
        uncertainty={"type": "influence_score_asymptotic_interval"},
    )


def dml_plr(task, data):
    no_weights(task)
    v = columns(task)
    xcols = v.get("controls", v.get("features", []))
    if not xcols:
        raise ValueError("Baseline covariates required")
    x = numeric(data, xcols)
    d = numeric(data, [v["treatment"]]).ravel()
    y = numeric(data, [v["outcome"]]).ravel()
    ell = np.full(len(data), np.nan)
    m = ell.copy()
    seed = int(task.get("analysis", {}).get("seed", 20261020))
    learner = RandomForestRegressor(
        n_estimators=100, min_samples_leaf=12, max_depth=6, random_state=seed, n_jobs=1
    )
    for train, test in crossfits(task, data, d):
        ell[test] = clone(learner).fit(x[train], y[train]).predict(x[test])
        m[test] = clone(learner).fit(x[train], d[train]).predict(x[test])
    rd = d - m
    ry = y - ell
    fit = linear_fit(
        ry,
        rd[:, None],
        ["partial_linear_parameter"],
        groups=cluster(task, data),
        alpha=task.get("inference", {}).get("alpha", 0.05),
    )
    ans = packed_fit(fit, "partial_linear_parameter", "partial_linear_parameter")
    ans["notes"].append("PLR系数不自动等于异质性下ATE；目标结构条件由方案论证。")
    return ans


def did_2x2(task, data):
    no_weights(task)
    v = columns(task)
    t = v["time"]
    dcol = v["treatment"]
    ycol = v["outcome"]
    times = sorted(data[t].unique())
    if len(times) != 2:
        raise ValueError("Two-period adapter rejects staggered or multi-period data")
    d = numeric(data, [dcol]).ravel()
    binary(d)
    post = (data[t] == times[1]).to_numpy(dtype=float)
    if v.get("controls") or v.get("features"):
        raise ValueError(
            "This unadjusted 2x2 adapter does not estimate conditional-parallel-trend DiD"
        )
    if task.get("branch_id") == "CA04.two_period_panel" or (
        not task.get("branch_id")
        and task.get("data_contract", {}).get("structure") == "panel"
    ):
        unit = v["unit"]
        if data.duplicated([unit, t]).any():
            raise ValueError("Duplicate unit by time rows")
        piv = data.pivot(index=unit, columns=t, values=ycol)
        if piv.isna().any().any():
            raise ValueError(
                "Balanced two-period panel required; no silent complete-case selection"
            )
        dg = data.groupby(unit)[dcol]
        if (dg.nunique() != 1).any():
            raise ValueError(
                "Treatment must indicate a fixed treated group, not post-period receipt"
            )
        uu = piv.index
        group = dg.first().reindex(uu).to_numpy(dtype=float)
        dy = (piv[times[1]] - piv[times[0]]).to_numpy(dtype=float)
        X = np.column_stack([np.ones(len(uu)), group])
        ckey = task.get("inference", {}).get("cluster")
        gg = None
        if ckey:
            if (data.groupby(unit)[ckey].nunique() != 1).any():
                raise ValueError("Cluster changes within unit")
            gg = data.groupby(unit)[ckey].first().reindex(uu).to_numpy()
        fit = linear_fit(
            dy,
            X,
            ["intercept", "ATT"],
            groups=gg,
            alpha=task.get("inference", {}).get("alpha", 0.05),
        )
    else:
        if any(((d == g) & (post == p)).sum() < 2 for g in [0, 1] for p in [0, 1]):
            raise ValueError("All four DiD cells need observations")
        y = numeric(data, [ycol]).ravel()
        X = np.column_stack([np.ones(len(data)), d, post, d * post])
        fit = linear_fit(
            y,
            X,
            ["intercept", "treated_group", "post", "ATT"],
            groups=cluster(task, data),
            alpha=task.get("inference", {}).get("alpha", 0.05),
        )
    ans = packed_fit(fit, "ATT", "ATT")
    ans["details"].update(
        periods=[str(x) for x in times],
        pretrend_test="not_identified_with_one_preperiod",
    )
    ans["notes"].append("两期数据不能检验处理前趋势；不声称平行趋势已被验证。")
    return ans


def local_rd(task, data):
    no_weights(task)
    v = columns(task)
    r = numeric(data, [v["running"]]).ravel()
    window = task.get("analysis", {}).get("window")
    cut = float(
        task.get("design", {}).get("cutoff", task.get("analysis", {}).get("cutoff", 0))
    )
    if not window or len(window) != 2 or not float(window[0]) < cut < float(window[1]):
        raise ValueError(
            "Prespecified local-randomization window straddling cutoff required"
        )
    mask = (r >= float(window[0])) & (r <= float(window[1]))
    sub = data.loc[mask].copy()
    if len(sub) < 8:
        raise ValueError(
            "Local window too small for this asymptotic reference implementation"
        )
    assigned = (sub[v["running"]].to_numpy() >= cut).astype(float)
    if not np.array_equal(numeric(sub, [v["treatment"]]).ravel(), assigned):
        raise ValueError("Fuzzy RD needs an IV/RD-specific estimator")
    result = rct(task, sub)
    result["details"].update(window=window, cutoff=cut, n_window=len(sub))
    result["notes"].append(
        "该结果基于窗口内局部随机化，不是局部多项式RD或CCT偏差校正。"
    )
    return result


def synthetic_control(task, data):
    no_weights(task)
    v = columns(task)
    unit = v["unit"]
    time = v["time"]
    ycol = v["outcome"]
    a = task.get("analysis", {})
    treated = a["treated_unit"]
    start = a["treatment_start"]
    donors = a["donor_units"]
    if not donors or treated in donors or len(set(donors)) != len(donors):
        raise ValueError("Nonempty donor list must be unique and exclude treated unit")
    if data.duplicated([unit, time]).any():
        raise ValueError("Duplicate synthetic-control unit by time")
    panel = data.pivot(index=time, columns=unit, values=ycol).sort_index()
    keep = [treated] + donors
    if any(c not in panel for c in keep) or panel[keep].isna().any().any():
        raise ValueError("Balanced complete treated-donor panel required")
    before = panel.index < start
    after = ~before
    if before.sum() < 3 or after.sum() < 1:
        raise ValueError(
            "At least three pretreatment periods and one post period required"
        )
    Y = panel[treated].to_numpy(dtype=float)
    D = panel[donors].to_numpy(dtype=float)
    objective = lambda w: float(np.mean((Y[before] - D[before] @ w) ** 2))
    opt = optimize.minimize(
        objective,
        np.ones(len(donors)) / len(donors),
        method="SLSQP",
        bounds=[(0, 1)] * len(donors),
        constraints=[{"type": "eq", "fun": lambda w: w.sum() - 1}],
        options={"ftol": 1e-12, "maxiter": 3000},
    )
    if not opt.success:
        raise ValueError("Synthetic-control optimizer failed: " + opt.message)
    weights = opt.x
    pred = D @ weights
    gap = Y - pred
    return dict(
        estimates=[
            {
                "estimand": "treated_unit_post_mean_gap",
                "estimate": float(gap[after].mean()),
                "std_error": None,
                "ci_low": None,
                "ci_high": None,
            }
        ],
        tables={
            "donor_weights": [
                {"unit": str(u), "weight": float(w)} for u, w in zip(donors, weights)
            ],
            "trajectory": [
                {
                    "time": str(t),
                    "observed": float(y),
                    "counterfactual": float(c),
                    "gap": float(g),
                }
                for t, y, c, g in zip(panel.index, Y, pred, gap)
            ],
        },
        details={
            "preperiods": int(before.sum()),
            "postperiods": int(after.sum()),
            "pre_rmspe": float(np.sqrt(objective(weights))),
            "optimization_success": True,
            "formal_inference_computed": False,
        },
        notes=[
            "本地只完成经典权重与轨迹计算；供体污染、反事实结构及正式推断仍需项目材料。"
        ],
        uncertainty={"type": "not_computed"},
        follow_up=["synthetic_control_inference"],
    )


FUNCTIONS = {
    "rct": rct,
    "iv": iv,
    "aipw": aipw,
    "dml_irm": lambda t, d: aipw(t, d, True),
    "dml_plr": dml_plr,
    "did_2x2": did_2x2,
    "local_rd": local_rd,
    "synthetic_control": synthetic_control,
}


def execute(adapter, task, data):
    if adapter not in FUNCTIONS:
        raise ValueError("Causal adapter not implemented: " + str(adapter))
    return FUNCTIONS[adapter](task, data)
