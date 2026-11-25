"""Descriptive, predictive and exploratory calculations."""

import numpy as np
import pandas as pd
from scipy import stats
from scipy.sparse.csgraph import connected_components
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA, LatentDirichletAllocation
from sklearn.ensemble import (
    RandomForestRegressor,
    RandomForestClassifier,
    GradientBoostingRegressor,
    GradientBoostingClassifier,
)
from sklearn.feature_extraction.text import TfidfVectorizer, CountVectorizer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge, Lasso, ElasticNet, LogisticRegression
from sklearn.metrics import (
    mean_squared_error,
    mean_absolute_error,
    r2_score,
    accuracy_score,
    balanced_accuracy_score,
    log_loss,
    roc_auc_score,
    average_precision_score,
    adjusted_rand_score,
)
from sklearn.model_selection import train_test_split, GroupShuffleSplit
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer
from .numerics import numeric, linear_fit, interval, effective_n


def vmap(task):
    return task.get("variables", {})


def settings(task):
    return task.get("analysis", {})


def random_state(task):
    return int(settings(task).get("seed", 20261020))


def summary(task, data):
    v = vmap(task)
    cols = v.get("outcomes") or [v["outcome"]]
    wc = v.get("weight")
    w = np.ones(len(data)) if not wc else numeric(data, [wc]).ravel()
    if (w <= 0).any():
        raise ValueError(
            "Positive summary weights required; zero weight rows need explicit sample handling"
        )
    records = []
    for col in cols:
        y = numeric(data, [col]).ravel()
        m = float(np.average(y, weights=w))
        row = {
            "variable": col,
            "n": len(y),
            "mean": m,
            "min": float(y.min()),
            "max": float(y.max()),
            "effective_n": effective_n(w),
        }
        order = np.argsort(y)
        cw = np.cumsum(w[order]) / w.sum()
        for p in [0.1, 0.25, 0.5, 0.75, 0.9]:
            row["q" + str(int(100 * p))] = float(
                y[order[min(np.searchsorted(cw, p), len(y) - 1)]]
            )
        if not wc and len(y) > 1:
            row.update(interval(m, y.std(ddof=1) / np.sqrt(len(y)), len(y) - 1))
        records.append(row)
    return dict(
        estimates=records,
        tables={"summary": records},
        details={
            "raw_rows": len(data),
            "weighted": bool(wc),
            "design_based_variance": False,
        },
        notes=["有权重点统计不自动具有复杂抽样总体区间；需按抽样设计接入survey适配器。"]
        if wc
        else [],
        uncertainty={"type": "weighted_point_only" if wc else "iid_mean_t_interval"},
    )


def distribution(task, data):
    v = vmap(task)
    y = numeric(data, [v["outcome"]]).ravel()
    w = np.ones(len(y)) if not v.get("weight") else numeric(data, [v["weight"]]).ravel()
    if (w <= 0).any():
        raise ValueError("Positive weights required")
    order = np.argsort(y)
    ys = y[order]
    ws = w[order]
    W = ws.sum()
    cum = ws.cumsum()
    mean = np.average(ys, weights=ws)
    gini = theil = None
    if ys.min() >= 0 and mean > 0:
        gini = float(np.sum(ws * (2 * cum - W - ws) * ys) / (W * np.sum(ws * ys)))
        ratio = ys / mean
        terms = np.zeros(len(ys))
        good = ratio > 0
        terms[good] = ratio[good] * np.log(ratio[good])
        theil = float(np.average(terms, weights=ws))
    result = {"mean": float(mean), "gini": gini, "theil": theil}
    return dict(
        estimates=[result],
        tables={
            "ecdf": [
                {"value": float(a), "cumulative_share": float(b / W)}
                for a, b in zip(ys, cum)
            ]
        },
        details={"n": len(y), "nonnegative_inequality_support": bool(ys.min() >= 0)},
        notes=["Gini与Theil只在非负且正均值支持下计算；未提供总体不平等区间。"],
        uncertainty={"type": "descriptive_point_only"},
    )


def ols(task, data):
    v = vmap(task)
    features = v.get("features", v.get("controls", []))
    y = numeric(data, [v["outcome"]]).ravel()
    X = np.column_stack([np.ones(len(data)), numeric(data, features)])
    w = None if not v.get("weight") else numeric(data, [v["weight"]]).ravel()
    group = task.get("inference", {}).get("cluster")
    groups = None if not group else data[group].to_numpy()
    fit = linear_fit(
        y,
        X,
        ["intercept"] + features,
        weights=w,
        groups=groups,
        alpha=task.get("inference", {}).get("alpha", 0.05),
    )
    return dict(
        estimates=fit["coefficients"],
        tables={"coefficients": fit["coefficients"]},
        details={
            "n": fit["n"],
            "rank": fit["rank"],
            "covariance": fit["covariance"],
            "independent_units": fit["independent_units"],
        },
        notes=fit["notes"]
        + ["回归系数按条件关联解释；控制和固定效应不自动赋予因果含义。"],
        uncertainty={
            "type": "conditional_association_interval",
            "covariance": fit["covariance"],
        },
    )


def split_indices(task, data, y, classification=False):
    pred = task.get("prediction", {})
    mode = pred.get("split")
    test_size = float(pred.get("test_fraction", 0.25))
    idx = np.arange(len(data))
    seed = random_state(task)
    if not 0.05 <= test_size <= 0.5:
        raise ValueError("test_fraction outside reference adapter range [.05,.5]")
    if mode in ["iid_holdout", "iid_three_way"]:
        stratify = y if classification else None
        tr, te = train_test_split(
            idx, test_size=test_size, random_state=seed, stratify=stratify
        )
    elif mode in ["group_holdout", "spatial_block"]:
        key = (
            pred.get("group_column")
            if mode == "group_holdout"
            else pred.get("spatial_block_column")
        )
        if not key:
            raise ValueError("Group or spatial block column required")
        tr, te = next(
            GroupShuffleSplit(n_splits=1, test_size=test_size, random_state=seed).split(
                data, y, data[key]
            )
        )
    elif mode in ["time_forward", "group_time"]:
        key = pred.get("time_column")
        if not key:
            raise ValueError("Prediction time column required")
        times = np.sort(data[key].dropna().unique())
        if len(times) < 3:
            raise ValueError(
                "At least three observed time blocks required for forward prediction"
            )
        cutoff = times[max(1, min(len(times) - 1, int(len(times) * (1 - test_size))))]
        train_mask = (data[key] < cutoff).to_numpy()
        test_mask = (data[key] >= cutoff).to_numpy()
        if mode == "group_time":
            gkey = pred.get("group_column")
            if not gkey:
                raise ValueError("Group column required for future new-unit prediction")
            groups = np.asarray(data[gkey].unique())
            gt, ge = train_test_split(groups, test_size=test_size, random_state=seed)
            train_mask &= data[gkey].isin(gt).to_numpy()
            test_mask &= data[gkey].isin(ge).to_numpy()
        tr = np.flatnonzero(train_mask)
        te = np.flatnonzero(test_mask)
    else:
        raise ValueError("Explicit supported prediction split required")
    if len(tr) < 8 or len(te) < 3:
        raise ValueError("Too few training or testing observations")
    if set(tr) & set(te):
        raise ValueError("Train-test overlap")
    if classification and (
        len(np.unique(y[tr])) < 2 or not set(np.unique(y[te])) <= set(np.unique(y[tr]))
    ):
        raise ValueError(
            "Test labels not represented in training, or training has one class"
        )
    return tr, te


def metric_records(y, pred, prob=None, classes=None):
    if prob is None:
        return {
            "rmse": float(np.sqrt(mean_squared_error(y, pred))),
            "mae": float(mean_absolute_error(y, pred)),
            "r2": float(r2_score(y, pred)),
        }
    ans = {
        "accuracy": float(accuracy_score(y, pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y, pred)),
        "log_loss": float(log_loss(y, prob, labels=classes)),
    }
    if len(classes) == 2 and len(np.unique(y)) == 2:
        binary_y = (y == classes[1]).astype(int)
        pp = prob[:, 1]
        ans.update(
            roc_auc=float(roc_auc_score(binary_y, pp)),
            average_precision=float(average_precision_score(binary_y, pp)),
            brier=float(np.mean((binary_y - pp) ** 2)),
        )
    return ans


def predict(task, data, text=False):
    v = vmap(task)
    target = data[v["outcome"]]
    if target.isna().any():
        raise ValueError("Missing prediction labels cannot be silently dropped")
    classification = task.get("outcome_type") in ["binary", "nominal", "ordinal"]
    y = target.to_numpy() if classification else target.to_numpy(dtype=float)
    if not classification and not np.isfinite(y).all():
        raise ValueError("Nonfinite prediction labels")
    tr, te = split_indices(task, data, y, classification)
    a = settings(task)
    mid = task.get(
        "selected_method_id",
        task.get("method_id", a.get("learner", "logit" if classification else "ridge")),
    ).split(".")[-1]
    if mid == "logistic":
        mid = "logit"
    seed = random_state(task)
    if classification:
        if mid not in {
            "logit",
            "text_classifier",
            "random_forest",
            "gradient_boosting",
        }:
            raise ValueError("Unsupported classification learner: " + mid)
        model = (
            RandomForestClassifier(
                n_estimators=120,
                min_samples_leaf=5,
                max_depth=8,
                random_state=seed,
                n_jobs=1,
            )
            if mid == "random_forest"
            else (
                GradientBoostingClassifier(
                    n_estimators=100, max_depth=2, random_state=seed
                )
                if mid == "gradient_boosting"
                else LogisticRegression(C=float(a.get("C", 1.0)), max_iter=3000)
            )
        )
    else:
        model = {
            "ridge": Ridge(alpha=float(a.get("alpha", 1.0))),
            "lasso": Lasso(alpha=float(a.get("alpha", 0.05)), max_iter=5000),
            "elastic_net": ElasticNet(alpha=float(a.get("alpha", 0.05)), max_iter=5000),
            "random_forest": RandomForestRegressor(
                n_estimators=120,
                min_samples_leaf=5,
                max_depth=8,
                random_state=seed,
                n_jobs=1,
            ),
            "gradient_boosting": GradientBoostingRegressor(
                n_estimators=100, max_depth=2, random_state=seed
            ),
        }.get(mid)
        if model is None:
            raise ValueError("Unsupported regression learner: " + mid)
    if text:
        key = v["text"]
        if data[key].isna().any() and not a.get("allow_empty_text"):
            raise ValueError(
                "Missing text requires an explicit empty-text handling rule"
            )
        x = data[key].fillna("").astype(str)
        pipeline = make_pipeline(
            TfidfVectorizer(
                analyzer=a.get("analyzer", "char"),
                ngram_range=tuple(a.get("ngram_range", [2, 4])),
                max_features=5000,
            ),
            model,
        )
    else:
        features = v.get("features", [])
        if not features:
            raise ValueError("Prediction features required")
        x = data[features]
        cats = a.get("categorical", [])
        nums = [c for c in features if c not in cats]
        if x.isna().any().any() and not a.get("allow_training_fold_imputation", False):
            raise ValueError(
                "Explicit training-fold imputation plan required for missing features"
            )
        transforms = []
        if nums:
            transforms.append(
                (
                    "numeric",
                    make_pipeline(
                        SimpleImputer(strategy="median", keep_empty_features=True),
                        StandardScaler(),
                    ),
                    nums,
                )
            )
        if cats:
            transforms.append(
                (
                    "categorical",
                    make_pipeline(
                        SimpleImputer(strategy="most_frequent"),
                        OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                    ),
                    cats,
                )
            )
        pipeline = make_pipeline(ColumnTransformer(transforms), model)
    pipeline.fit(x.iloc[tr], y[tr])
    yp = pipeline.predict(x.iloc[te])
    prob = pipeline.predict_proba(x.iloc[te]) if classification else None
    classes = pipeline.classes_ if classification else None
    metrics = metric_records(y[te], yp, prob, classes)
    if classification:
        base = np.array([np.mean(y[tr] == c) for c in classes])
        bprob = np.tile(base, (len(te), 1))
        bpred = np.repeat(classes[np.argmax(base)], len(te))
        baseline = metric_records(y[te], bpred, bprob, classes)
    else:
        baseline = metric_records(y[te], np.repeat(y[tr].mean(), len(te)))
    calibration = []
    if classification and len(classes) == 2:
        for lo in np.linspace(0, 0.9, 10):
            mask = (prob[:, 1] >= lo) & (
                prob[:, 1] < (lo + 0.1) if lo < 0.9 else prob[:, 1] <= 1.0
            )
            if mask.any():
                calibration.append(
                    {
                        "lower": float(lo),
                        "n": int(mask.sum()),
                        "mean_prediction": float(prob[mask, 1].mean()),
                        "observed_rate": float((y[te][mask] == classes[1]).mean()),
                    }
                )
    details = {
        "n_train": len(tr),
        "n_test": len(te),
        "n_unused": len(data) - len(tr) - len(te),
        "split": task.get("prediction", {}),
        "train_rows": tr.tolist(),
        "test_rows": te.tolist(),
        "train_test_overlap": 0,
        "preprocessor_fit_on_training_only": True,
        "test_set_used_for_tuning": False,
        "parameters": {
            k: str(v)
            for k, v in pipeline.get_params(deep=True).items()
            if "__" not in k
        },
    }
    return dict(
        estimates=[{"model": mid, **metrics}],
        tables={
            "performance": [
                {"model": mid, **metrics},
                {"model": "training_only_baseline", **baseline},
            ],
            "calibration": calibration,
        },
        details=details,
        notes=[
            "固定超参数参考运行，未进行模型搜索；测试集使用已记录，不能反复据其结果调参。",
            "预测特征贡献不构成因果效应或机制材料。",
        ],
        uncertainty={"type": "heldout_performance_without_sampling_interval"},
    )


def kmeans(task, data):
    v = vmap(task)
    x = numeric(data, v["features"])
    z = StandardScaler().fit_transform(x)
    k = int(settings(task).get("n_clusters", 3))
    seed = random_state(task)
    if not 1 < k < min(len(data), 20):
        raise ValueError("Cluster count outside local reference scope")
    fit = KMeans(n_clusters=k, n_init=10, random_state=seed).fit(z)
    stability = []
    rng = np.random.default_rng(seed)
    for j in range(int(settings(task).get("stability_repeats", 5))):
        ix = rng.choice(len(z), size=max(k + 1, int(0.8 * len(z))), replace=False)
        new = KMeans(n_clusters=k, n_init=10, random_state=seed + j + 1).fit(z[ix])
        stability.append(
            {
                "replicate": j,
                "adjusted_rand": float(
                    adjusted_rand_score(fit.labels_[ix], new.labels_)
                ),
            }
        )
    return dict(
        estimates=[{"k": k, "inertia": float(fit.inertia_)}],
        tables={
            "cluster_sizes": [
                {"cluster": int(g), "n": int((fit.labels_ == g).sum())}
                for g in range(k)
            ],
            "stability": stability,
        },
        details={
            "n": len(z),
            "scaling": "zscore",
            "stability_is_not_external_validation": True,
        },
        notes=["聚类结果属于探索，仍需外部含义与独立验证。"],
        uncertainty={"type": "exploratory_stability_not_parameter_ci"},
        follow_up=["cluster_external_validity"],
    )


def pca(task, data):
    v = vmap(task)
    x = numeric(data, v["features"])
    z = StandardScaler().fit_transform(x)
    k = int(settings(task).get("components", 2))
    if not 1 <= k <= min(z.shape):
        raise ValueError("Invalid PCA dimension")
    fit = PCA(n_components=k, random_state=random_state(task)).fit(z)
    scores = fit.transform(z)
    derived = data.copy()
    for j in range(k):
        derived["PC" + str(j + 1)] = scores[:, j]
    return dict(
        estimates=[
            {"component": j + 1, "explained_variance_share": float(x)}
            for j, x in enumerate(fit.explained_variance_ratio_)
        ],
        tables={
            "loadings": [
                dict(
                    component=j + 1,
                    **{name: float(val) for name, val in zip(v["features"], row)},
                )
                for j, row in enumerate(fit.components_)
            ]
        },
        details={
            "n": len(data),
            "scaled": True,
            "construct_validity_established": False,
        },
        notes=["PCA只构建线性表示；概念测量仍需外部效度。"],
        uncertainty={"type": "exploratory_representation"},
        derived_frame=derived,
        follow_up=["construct_validity"],
    )


def topic(task, data):
    v = vmap(task)
    a = settings(task)
    texts = data[v["text"]].fillna("").astype(str)
    if data[v["text"]].isna().any() and not a.get("allow_empty_text"):
        raise ValueError("Missing documents require an explicit empty-text rule")
    if (
        a.get("language") == "zh"
        and not a.get("pretokenized")
        and a.get("analyzer", "word") == "word"
    ):
        raise ValueError(
            "Chinese word topics require declared tokenization or an explicit character analyzer"
        )
    vec = CountVectorizer(
        max_features=3000, min_df=2, analyzer=a.get("analyzer", "word")
    )
    matrix = vec.fit_transform(texts)
    k = int(a.get("topics", 3))
    if matrix.shape[1] < k:
        raise ValueError("Vocabulary too small for requested topic count")
    fit = LatentDirichletAllocation(
        n_components=k,
        max_iter=20,
        random_state=random_state(task),
        learning_method="batch",
    ).fit(matrix)
    vocab = vec.get_feature_names_out()
    rows = []
    for j, weights in enumerate(fit.components_):
        rows.append(
            {"topic": j, "top_terms": ", ".join(vocab[np.argsort(weights)[-10:][::-1]])}
        )
    return dict(
        estimates=[
            {"topics": k, "perplexity_in_sample": float(fit.perplexity(matrix))}
        ],
        tables={"topics": rows},
        details={
            "documents": len(data),
            "vocabulary": len(vocab),
            "confirmatory": False,
        },
        notes=["样本内困惑度不是主题效度；需要人工与独立语料验证。"],
        uncertainty={"type": "exploratory_topic_model"},
        follow_up=["topic_external_validity"],
    )


def kaplan_meier(task, data):
    v = vmap(task)
    duration = numeric(data, [v.get("duration", v.get("outcome"))]).ravel()
    event = numeric(data, [v["event"]]).ravel()
    if (duration < 0).any() or not set(np.unique(event)) <= {0, 1}:
        raise ValueError("Nonnegative duration and binary event required")
    survival = 1.0
    greenwood = 0.0
    rows = []
    z = stats.norm.ppf(1 - task.get("inference", {}).get("alpha", 0.05) / 2)
    for time in np.sort(np.unique(duration[event == 1])):
        risk = int((duration >= time).sum())
        deaths = int(((duration == time) & (event == 1)).sum())
        survival *= 1 - deaths / risk
        if risk > deaths:
            greenwood += deaths / (risk * (risk - deaths))
        se = survival * np.sqrt(greenwood) if survival > 0 else 0.0
        rows.append(
            {
                "time": float(time),
                "n_risk": risk,
                "events": deaths,
                "survival": float(survival),
                "greenwood_se": float(se),
                "approx_ci_low": max(0.0, float(survival - z * se)),
                "approx_ci_high": min(1.0, float(survival + z * se)),
            }
        )
    return dict(
        estimates=[
            {
                "n": len(data),
                "events": int(event.sum()),
                "right_censored": int((1 - event).sum()),
            }
        ],
        tables={"survival": rows},
        details={
            "independent_right_censoring_assumed": True,
            "left_truncation_supported": False,
        },
        notes=[
            "区间为Greenwood正态近似，尾部可失真；本地不支持左截断、依赖样本和竞争风险。"
        ],
        uncertainty={"type": "pointwise_greenwood_normal_approximation"},
    )


def autoreg(task, data):
    v = vmap(task)
    time = v["time"]
    ycol = v["outcome"]
    a = settings(task)
    p = int(a.get("lags", 1))
    if data[time].duplicated().any():
        raise ValueError("Local autoregression supports one series with unique times")
    ordered = data.sort_values(time)
    y = numeric(ordered, [ycol]).ravel()
    n = len(y)
    start = int(n * float(a.get("train_fraction", 0.65)))
    try:
        coordinates = pd.to_numeric(ordered[time], errors="raise").to_numpy(dtype=float)
    except (ValueError, TypeError):
        coordinates = (
            pd.to_datetime(ordered[time], errors="raise")
            .astype("int64")
            .to_numpy(dtype=float)
        )
    gaps = np.diff(coordinates)
    if (
        not np.isfinite(coordinates).all()
        or not np.all(gaps > 0)
        or not np.allclose(gaps, gaps[0])
    ):
        raise ValueError(
            "Regular observed time spacing required; define missing time points before autoregression"
        )
    if p < 1 or start <= p + 3 or n - start < 3:
        raise ValueError("Insufficient time-series history or test horizon")
    rows = []
    for t in range(start, n):
        X = np.array([[1.0] + [y[j - l] for l in range(1, p + 1)] for j in range(p, t)])
        beta = np.linalg.lstsq(X, y[p:t], rcond=None)[0]
        pred = float(np.r_[1.0, [y[t - l] for l in range(1, p + 1)]] @ beta)
        rows.append(
            {
                "time": str(ordered[time].iloc[t]),
                "observed": float(y[t]),
                "predicted": pred,
                "last_value_baseline": float(y[t - 1]),
            }
        )
    truth = np.array([r["observed"] for r in rows])
    pred = np.array([r["predicted"] for r in rows])
    base = np.array([r["last_value_baseline"] for r in rows])
    return dict(
        estimates=[{"model": "AR" + str(p), **metric_records(truth, pred)}],
        tables={
            "rolling_forecast": rows,
            "performance": [
                {"model": "AR" + str(p), **metric_records(truth, pred)},
                {"model": "last_value", **metric_records(truth, base)},
            ],
        },
        details={
            "one_step_rolling": True,
            "fixed_model_order": p,
            "future_labels_used": False,
        },
        notes=[
            "这是固定阶数滚动OLS参考预测，不是完整ARIMA；预测区间及结构变化需另行评估。"
        ],
        uncertainty={"type": "heldout_errors_no_forecast_interval"},
    )


def moran(task, data):
    v = vmap(task)
    a = settings(task)
    y = numeric(data, [v["outcome"]]).ravel()
    W = np.asarray(a["spatial_weights"], dtype=float)
    n = len(y)
    if (
        W.shape != (n, n)
        or not np.isfinite(W).all()
        or (W < 0).any()
        or np.diag(W).any()
        or W.sum() <= 0
    ):
        raise ValueError("Finite nonnegative zero-diagonal spatial weights required")
    if a.get("weights_unit_order") is None or list(
        map(str, a["weights_unit_order"])
    ) != list(map(str, data[v["unit"]])):
        raise ValueError("Explicit weights unit order must match data order")
    z = y - y.mean()
    den = z @ z
    if den <= 0:
        raise ValueError("Moran statistic undefined for constant outcome")
    statistic = lambda x: float(n / W.sum() * (x @ W @ x) / (x @ x))
    observed = statistic(z)
    B = int(a.get("permutations", 199))
    if B < 19:
        raise ValueError("At least 19 permutations required")
    rng = np.random.default_rng(random_state(task))
    null = np.array([statistic(rng.permutation(z)) for _ in range(B)])
    expected = -1 / (n - 1)
    pv = float(
        (1 + np.sum(np.abs(null - expected) >= abs(observed - expected))) / (B + 1)
    )
    return dict(
        estimates=[
            {"morans_i": observed, "permutation_p": pv, "null_expectation": expected}
        ],
        tables={},
        details={
            "n": n,
            "permutations": B,
            "null": "exchangeable_random_labels_given_fixed_weights",
        },
        notes=["置换结果依赖随机标签零假设；空间自相关不构成因果效应。"],
        uncertainty={"type": "random_label_permutation_test"},
    )


def network(task, data):
    v = vmap(task)
    s = v["source"]
    t = v["target"]
    nodes = sorted(set(data[s]) | set(data[t]), key=str)
    index = {x: j for j, x in enumerate(nodes)}
    A = np.zeros((len(nodes), len(nodes)))
    if data[[s, t]].isna().any().any():
        raise ValueError(
            "Missing node labels require an explicit missing-edge treatment"
        )
    for x, y in zip(data[s], data[t]):
        if x == y:
            raise ValueError("Self loops outside simple-graph adapter scope")
        A[index[x], index[y]] = A[index[y], index[x]] = 1.0
    n = len(nodes)
    degree = A.sum(axis=1)
    triangles = np.diag(A @ A @ A) / 2
    den = degree * (degree - 1) / 2
    clustering = np.divide(triangles, den, out=np.zeros(n), where=den > 0)
    comps, labels = connected_components(A, directed=False)
    return dict(
        estimates=[
            {
                "nodes": n,
                "edges": int(A.sum() / 2),
                "density": float(A.sum() / (n * (n - 1))) if n > 1 else 0.0,
                "components": int(comps),
            }
        ],
        tables={
            "nodes": [
                {
                    "node": str(node),
                    "degree": float(degree[j]),
                    "local_clustering": float(clustering[j]),
                    "component": int(labels[j]),
                }
                for j, node in enumerate(nodes)
            ]
        },
        details={
            "graph": "undirected_binary_simple",
            "duplicate_edges_collapsed": len(data) - int(A.sum() / 2),
        },
        notes=["指标描述所观察到的图；缺边机制与同伴因果效应尚未识别。"],
        uncertainty={"type": "observed_graph_descriptors"},
    )


def oaxaca(task, data):
    v = vmap(task)
    group = numeric(data, [v["group"]]).ravel()
    y = numeric(data, [v["outcome"]]).ravel()
    x = np.column_stack([np.ones(len(data)), numeric(data, v["features"])])
    if set(np.unique(group)) != {0, 1}:
        raise ValueError("Oaxaca adapter needs two groups coded 0/1")

    def decompose(xx, yy, gg):
        mats = [xx[gg == j] for j in [0, 1]]
        ys = [yy[gg == j] for j in [0, 1]]
        if any(
            np.linalg.matrix_rank(m) < m.shape[1] or len(m) <= m.shape[1] for m in mats
        ):
            raise ValueError("Rank or sample size failure in decomposition group")
        b0, b1 = [np.linalg.lstsq(m, z, rcond=None)[0] for m, z in zip(mats, ys)]
        m0, m1 = [m.mean(axis=0) for m in mats]
        explained = float((m1 - m0) @ b0)
        unexplained = float(m1 @ (b1 - b0))
        return np.array([explained, unexplained, float(ys[1].mean() - ys[0].mean())])

    point = decompose(x, y, group)
    B = int(settings(task).get("bootstrap_repetitions", 199))
    rng = np.random.default_rng(random_state(task))
    rep = []
    if B < 19:
        raise ValueError("At least 19 bootstrap repetitions required")
    for _ in range(B):
        ix = np.r_[
            rng.choice(
                np.flatnonzero(group == 0), int((group == 0).sum()), replace=True
            ),
            rng.choice(
                np.flatnonzero(group == 1), int((group == 1).sum()), replace=True
            ),
        ]
        rep.append(decompose(x[ix], y[ix], group[ix]))
    alpha = task.get("inference", {}).get("alpha", 0.05)
    low, high = np.quantile(np.array(rep), [alpha / 2, 1 - alpha / 2], axis=0)
    rows = [
        {
            "component": label,
            "estimate": float(val),
            "bootstrap_ci_low": float(low[j]),
            "bootstrap_ci_high": float(high[j]),
        }
        for j, (label, val) in enumerate(
            zip(
                ["composition_reference_group_0", "coefficient_remainder", "total_gap"],
                point,
            )
        )
    ]
    return dict(
        estimates=rows,
        tables={"decomposition": rows},
        details={
            "reference_group": 0,
            "sum_identity_error": float(point[0] + point[1] - point[2]),
            "bootstrap": B,
        },
        notes=["分解遵循参考组0规则，不能把解释部分或剩余部分直接称为因果贡献或歧视。"],
        uncertainty={"type": "within_group_iid_percentile_bootstrap"},
    )


def meta(task, data):
    v = vmap(task)
    y = numeric(data, [v["effect"]]).ravel()
    se = numeric(data, [v["se"]]).ravel()
    k = len(y)
    if k < 2 or (se <= 0).any():
        raise ValueError(
            "At least two effect estimates with positive standard errors required"
        )
    if v.get("effect_scale") and data[v["effect_scale"]].nunique() != 1:
        raise ValueError("Cannot pool incompatible effect scales")
    w = 1 / se**2
    mu = np.average(y, weights=w)
    Q = float(np.sum(w * (y - mu) ** 2))
    den = w.sum() - (w @ w) / w.sum()
    tau2 = max(0.0, (Q - (k - 1)) / den)
    is_random = task.get("selected_method_id", task.get("method_id", "")).endswith(
        "random_meta"
    )
    weights = 1 / (se**2 + tau2) if is_random else w
    theta = float(np.average(y, weights=weights))
    s = float(np.sqrt(1 / weights.sum()))
    est = interval(theta, s, None, task.get("inference", {}).get("alpha", 0.05))
    return dict(
        estimates=[{"model": "DL_random" if is_random else "common_effect", **est}],
        tables={},
        details={
            "studies": k,
            "Q": Q,
            "tau2_DL": tau2,
            "I2": max(0.0, (Q - (k - 1)) / Q) if Q > 0 else 0.0,
        },
        notes=[
            "独立研究且目标量和尺度一致为前提；DL与常规正态区间不替代小样本或研究内依赖专属推断。"
        ],
        uncertainty={"type": "normal_meta_interval"},
    )


def multiple_testing(task, data):
    v = vmap(task)
    ps = numeric(data, [v["p_value"]]).ravel()
    m = len(ps)
    if ((ps < 0) | (ps > 1)).any():
        raise ValueError("P-values outside [0,1]")
    ix = np.argsort(ps)
    p = ps[ix]
    holm = np.maximum.accumulate((m - np.arange(m)) * p)
    bh = np.minimum.accumulate((m * p / np.arange(1, m + 1))[::-1])[::-1]
    out = np.empty((m, 2))
    out[ix, 0] = np.minimum(holm, 1)
    out[ix, 1] = np.minimum(bh, 1)
    rows = [
        {
            "index": j,
            "p_raw": float(pv),
            "p_holm": float(out[j, 0]),
            "q_bh": float(out[j, 1]),
        }
        for j, pv in enumerate(ps)
    ]
    return dict(
        estimates=[],
        tables={"adjusted_p": rows},
        details={
            "hypotheses": m,
            "BH_requires_independence_or_suitable_positive_dependence": True,
        },
        notes=["须预先明确检验族；BH的适用依赖条件与Holm不同。"],
        uncertainty={"type": "multiplicity_adjustment"},
    )


def conformal(task, data):
    v = vmap(task)
    x = numeric(data, v["features"])
    y = numeric(data, [v["outcome"]]).ravel()
    n = len(y)
    a = settings(task)
    alpha = float(a.get("alpha", 0.1))
    seed = random_state(task)
    if task.get("prediction", {}).get("split") != "iid_three_way" or not 0 < alpha < 1:
        raise ValueError(
            "Local conformal supports declared exchangeable iid three-way regression split"
        )
    tr, rest = train_test_split(np.arange(n), test_size=0.4, random_state=seed)
    cal, te = train_test_split(rest, test_size=0.5, random_state=seed + 1)
    if min(len(tr), len(cal), len(te)) < 5:
        raise ValueError("Conformal split too small")
    model = make_pipeline(StandardScaler(), Ridge(alpha=1.0)).fit(x[tr], y[tr])
    res = np.abs(y[cal] - model.predict(x[cal]))
    rank = int(np.ceil((len(cal) + 1) * (1 - alpha)))
    q = float(np.sort(res)[rank - 1]) if rank <= len(cal) else np.inf
    pred = model.predict(x[te])
    coverage = float(np.mean((y[te] >= pred - q) & (y[te] <= pred + q)))
    return dict(
        estimates=[
            {
                "nominal_coverage": 1 - alpha,
                "test_coverage": coverage,
                "interval_width": 2 * q if np.isfinite(q) else None,
            }
        ],
        tables={},
        details={
            "n_train": len(tr),
            "n_calibration": len(cal),
            "n_test": len(te),
            "quantile_rank": rank,
            "finite_interval": bool(np.isfinite(q)),
            "train_calibration_test_disjoint": True,
        },
        notes=[
            "保证为所声明交换条件下的边际覆盖，不是逐个体条件覆盖；漂移不能直接沿用。"
        ],
        uncertainty={"type": "split_conformal_prediction_interval"},
    )


FUNCTIONS = {
    "summary": summary,
    "distribution": distribution,
    "ols": ols,
    "predict": predict,
    "text_predict": lambda t, d: predict(t, d, True),
    "kmeans": kmeans,
    "pca": pca,
    "topic": topic,
    "kaplan_meier": kaplan_meier,
    "autoreg": autoreg,
    "moran": moran,
    "network": network,
    "oaxaca": oaxaca,
    "meta": meta,
    "multiple_testing": multiple_testing,
    "conformal": conformal,
}


def execute(adapter, task, data):
    if adapter not in FUNCTIONS:
        raise ValueError("Noncausal adapter not implemented: " + str(adapter))
    return FUNCTIONS[adapter](task, data)
