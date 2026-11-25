"""Numerical helpers for the empirical adapters."""

import numpy as np
from scipy import stats


def numeric(data, columns):
    arr = data.loc[:, columns].to_numpy(dtype=float)
    if not np.isfinite(arr).all():
        raise ValueError(
            "Missing or nonfinite values require an explicit preprocessing plan"
        )
    return arr


def interval(estimate, se, df=None, alpha=0.05):
    q = (
        stats.t.ppf(1 - alpha / 2, df)
        if df is not None
        else stats.norm.ppf(1 - alpha / 2)
    )
    stat = (
        estimate / se
        if se > 0
        else (0.0 if estimate == 0 else np.sign(estimate) * np.inf)
    )
    p = 2 * (stats.t.sf(abs(stat), df) if df is not None else stats.norm.sf(abs(stat)))
    return dict(
        estimate=float(estimate),
        std_error=float(se),
        ci_low=float(estimate - q * se),
        ci_high=float(estimate + q * se),
        p_value=float(p),
        alpha=alpha,
    )


def cluster_meat(scores, groups):
    groups = np.asarray(groups)
    levels = np.unique(groups)
    if len(levels) < 2:
        raise ValueError("At least two independent clusters required")
    agg = np.array([scores[groups == g].sum(axis=0) for g in levels])
    return agg.T @ agg, len(levels)


def linear_fit(y, X, names, weights=None, groups=None, cov_type="HC3", alpha=0.05):
    y = np.asarray(y, dtype=float).reshape(-1)
    X = np.asarray(X, dtype=float)
    n, k = X.shape
    if not np.isfinite(y).all() or not np.isfinite(X).all():
        raise ValueError("Nonfinite regression input")
    if n <= k or np.linalg.matrix_rank(X) < k:
        raise ValueError(
            "Insufficient residual degrees of freedom or rank-deficient design"
        )
    w = np.ones(n) if weights is None else np.asarray(weights, dtype=float)
    if len(w) != n or not np.isfinite(w).all() or (w <= 0).any():
        raise ValueError("Positive finite regression weights required")
    a = X * np.sqrt(w[:, None])
    b = y * np.sqrt(w)
    beta = np.linalg.lstsq(a, b, rcond=None)[0]
    bread = np.linalg.inv(a.T @ a)
    u = b - a @ beta
    notes = []
    if groups is not None:
        meat, G = cluster_meat(a * u[:, None], groups)
        vcov = bread @ meat @ bread * (G / (G - 1)) * ((n - 1) / (n - k))
        df = G - 1
        covariance = "CR1"
        independent_units = G
        if G < 30:
            notes.append(
                "少簇下CR1常规区间可能失真；需项目专属推断分析，30并非普遍有效阈值。"
            )
    elif cov_type == "HC3":
        h = np.einsum("ij,jk,ik->i", a, bread, a)
        if np.any(1 - h < 1e-10):
            raise ValueError("Unit leverage prevents HC3 inference")
        score = a * (u / (1 - h))[:, None]
        vcov = bread @ (score.T @ score) @ bread
        df = n - k
        covariance = "HC3"
        independent_units = n
    elif cov_type == "HC1":
        score = a * u[:, None]
        vcov = bread @ (score.T @ score) @ bread * n / (n - k)
        df = n - k
        covariance = "HC1"
        independent_units = n
    else:
        raise ValueError("Only HC3, HC1 or explicitly clustered CR1 supported")
    se = np.sqrt(np.maximum(np.diag(vcov), 0))
    records = [
        dict(term=name, **interval(beta[j], se[j], df, alpha))
        for j, name in enumerate(names)
    ]
    return dict(
        coefficients=records,
        beta=beta,
        vcov=vcov,
        residual=y - X @ beta,
        n=n,
        rank=k,
        df=df,
        covariance=covariance,
        independent_units=independent_units,
        notes=notes,
    )


def score_inference(values, groups=None, alpha=0.05):
    values = np.asarray(values, dtype=float)
    n = len(values)
    if n < 3 or not np.isfinite(values).all():
        raise ValueError("At least three finite scores required")
    theta = values.mean()
    center = values - theta
    if groups is None:
        se = values.std(ddof=1) / np.sqrt(n)
        df = n - 1
        G = n
    else:
        meat, G = cluster_meat(center[:, None], groups)
        se = np.sqrt(float(meat[0, 0]) * G / (G - 1)) / n
        df = G - 1
    return dict(**interval(theta, se, df, alpha), n=n, independent_units=G)


def standardized_difference(x, d, weights=None):
    x = np.asarray(x, dtype=float)
    d = np.asarray(d)
    w = np.ones(len(d)) if weights is None else np.asarray(weights)
    records = []
    for j in range(x.shape[1]):
        a = x[d == 1, j]
        b = x[d == 0, j]
        pooled = np.sqrt((np.var(a, ddof=1) + np.var(b, ddof=1)) / 2)
        diff = np.average(a, weights=w[d == 1]) - np.average(b, weights=w[d == 0])
        records.append(float(diff / pooled) if pooled > 0 else None)
    return records


def effective_n(weights):
    w = np.asarray(weights, dtype=float)
    return float(w.sum() ** 2 / np.square(w).sum())


def finite_json(value):
    """Convert numpy objects; unidentified/infinite quantities become explicit nulls."""
    if isinstance(value, np.ndarray):
        return finite_json(value.tolist())
    if isinstance(value, np.generic):
        return finite_json(value.item())
    if isinstance(value, dict):
        return {str(k): finite_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [finite_json(v) for v in value]
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value
