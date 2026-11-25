"""Generate R analyses from an explicit research design."""

import json, re
from pathlib import Path


def rq(value):
    return json.dumps(str(value), ensure_ascii=False)


def ident(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.]*", value):
        raise ValueError(
            "R export needs simple ASCII column identifiers; rename explicitly in the data contract"
        )
    return value


def vector(values):
    return "c(" + ",".join(rq(v) for v in values) + ")"


def require(mapping, key):
    if key not in mapping:
        raise ValueError("External adapter configuration required: " + key)
    return mapping[key]


def formula(v):
    return "~" + ("+".join(ident(c) for c in v.get("controls", [])) or "1")


def export_r(adapter, task, data_path, outdir):
    v = task.get("variables", {})
    a = task.get("analysis", {})
    d = task.get("design", {})
    inf = task.get("inference", {})
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    code = []
    packages = []
    y = ident(v["outcome"]) if v.get("outcome") else None
    if v.get("weight") and adapter not in ["survey", "did", "contdid"]:
        raise ValueError(
            "This exporter does not implement the declared weighting contract"
        )
    if inf.get("cluster") and adapter not in [
        "did",
        "contdid",
        "did_multiplegt",
        "rdrobust",
        "grf",
        "survey",
    ]:
        raise ValueError(
            "This exporter does not implement the declared clustering contract"
        )
    if adapter == "did":
        packages = ["did"]
        g = ident(require(v, "cohort"))
        time = ident(require(v, "time"))
        unit = ident(require(v, "unit"))
        control = require(a, "control_group")
        ag = require(a, "aggregation")
        if control not in ["nevertreated", "notyettreated"] or ag not in [
            "simple",
            "dynamic",
            "group",
            "calendar",
        ]:
            raise ValueError(
                "Explicit supported did comparison and aggregation required"
            )
        anticipation = int(require(a, "anticipation"))
        panel = task["data_contract"]["structure"] == "panel"
        extra = ", weightsname=" + rq(ident(v["weight"])) if v.get("weight") else ""
        code = [
            f"fit <- did::att_gt(yname={rq(y)}, tname={rq(time)}, idname={rq(unit)}, gname={rq(g)}, xformla={formula(v)}, data=dat, panel={str(panel).upper()}, control_group={rq(control)}, anticipation={anticipation}, bstrap=TRUE, cband=TRUE, biters=999, clustervars={rq(inf.get('cluster', unit))}{extra})",
            f"aggregate <- did::aggte(fit, type={rq(ag)})",
            "print(summary(fit))",
            "print(summary(aggregate))",
        ]
    elif adapter == "contdid":
        packages = ["contdid"]
        g = ident(require(v, "cohort"))
        time = ident(require(v, "time"))
        unit = ident(require(v, "unit"))
        dose = ident(require(v, "dose"))
        if v.get("controls"):
            raise ValueError(
                "This contdid export does not implement covariate adjustment"
            )
        target = require(a, "target_parameter")
        aggregation = require(a, "aggregation")
        control = require(a, "control_group")
        if (
            target not in ["level", "slope"]
            or aggregation not in ["dose", "eventstudy"]
            or control not in ["nevertreated", "notyettreated"]
        ):
            raise ValueError("Unsupported continuous DiD target or aggregation")
        degree = int(require(a, "spline_degree"))
        knots = int(require(a, "spline_knots"))
        if not 1 <= degree <= 3 or knots < 0:
            raise ValueError(
                "Specify a spline degree from 1 to 3 and nonnegative knot count"
            )
        extra = ", weightsname=" + rq(ident(v["weight"])) if v.get("weight") else ""
        code = [
            f"stopifnot(all(tapply(dat[[{rq(dose)}]],dat[[{rq(unit)}]],function(x) length(unique(x)))==1))",
            f'fit <- contdid::cont_did(yname={rq(y)}, dname={rq(dose)}, gname={rq(g)}, tname={rq(time)}, idname={rq(unit)}, data=dat, target_parameter={rq(target)}, aggregation={rq(aggregation)}, treatment_type="continuous", control_group={rq(control)}, anticipation={int(require(a, "anticipation"))}, degree={degree}, num_knots={knots}, bstrap=TRUE, cband=TRUE, biters=999, clustervars={rq(inf.get("cluster", unit))}{extra})',
            "print(summary(fit))",
        ]
    elif adapter == "did_multiplegt":
        packages = ["DIDmultiplegtDYN"]
        unit = ident(require(v, "unit"))
        time = ident(require(v, "time"))
        tr = ident(require(v, "treatment"))
        effects = int(require(a, "effects"))
        placebo = int(require(a, "placebo"))
        if effects < 1 or placebo < 0:
            raise ValueError("effects>=1 and placebo>=0 required")
        extra = (
            ", controls=" + vector([ident(c) for c in v["controls"]])
            if v.get("controls")
            else ""
        )
        code = [
            f"fit <- DIDmultiplegtDYN::did_multiplegt_dyn(df=dat, outcome={rq(y)}, group={rq(unit)}, time={rq(time)}, treatment={rq(tr)}, effects={effects}, placebo={placebo}, cluster={rq(inf.get('cluster', unit))}, graph_off=TRUE{extra})",
            "print(fit)",
        ]
    elif adapter == "rdrobust":
        packages = ["rdrobust"]
        running = ident(require(v, "running"))
        cutoff = float(require(d, "cutoff"))
        extra = (
            f", fuzzy=dat[[{rq(ident(require(v, 'treatment')))}]]"
            if task.get("branch_id") == "CA05.fuzzy"
            else ""
        )
        if v.get("controls"):
            extra += (
                ", covs=as.matrix(dat[, "
                + vector([ident(c) for c in v["controls"]])
                + ", drop=FALSE])"
            )
        if inf.get("cluster"):
            extra += ", cluster=dat[[" + rq(ident(inf["cluster"])) + "]]"
        code = [
            f'fit <- rdrobust::rdrobust(y=dat[[{rq(y)}]], x=dat[[{rq(running)}]], c={cutoff}, p=1, q=2, bwselect="mserd", masspoints="adjust"{extra})',
            "print(summary(fit))",
            f"rdrobust::rdplot(y=dat[[{rq(y)}]], x=dat[[{rq(running)}]], c={cutoff})",
        ]
    elif adapter == "grf":
        packages = ["grf"]
        features = [ident(c) for c in require(v, "controls")]
        tr = ident(require(v, "treatment"))
        extra = (
            ", clusters=dat[[" + rq(ident(inf["cluster"])) + "]]"
            if inf.get("cluster")
            else ""
        )
        code = [
            f"X <- as.matrix(dat[, {vector(features)}, drop=FALSE])",
            f"fit <- grf::causal_forest(X=X, Y=dat[[{rq(y)}]], W=dat[[{rq(tr)}]], honesty=TRUE, seed={int(a.get('seed', 20261019))}{extra})",
            'print(grf::average_treatment_effect(fit, target.sample="all"))',
            "print(grf::test_calibration(fit))",
            "# Individual CATE intervals and policy value require a prespecified independent validation design.",
        ]
    elif adapter == "synthdid":
        if v.get("controls"):
            raise ValueError(
                "This synthdid exporter does not implement covariate adjustment"
            )
        packages = ["synthdid"]
        unit = ident(require(v, "unit"))
        time = ident(require(v, "time"))
        tr = ident(require(v, "treatment"))
        code = [
            f"setup <- synthdid::panel.matrices(dat, unit={rq(unit)}, time={rq(time)}, outcome={rq(y)}, treatment={rq(tr)})",
            "fit <- synthdid::synthdid_estimate(setup$Y, setup$N0, setup$T0)",
            "print(fit)",
            'print(sqrt(vcov(fit, method="placebo")))',
            "# Review placebo exchangeability and the number of treated and control units.",
        ]
    elif adapter == "lavaan":
        packages = ["lavaan"]
        syntax = require(a, "model_syntax")
        if not isinstance(syntax, str) or len(syntax) > 20000:
            raise ValueError("A bounded declared measurement model is required")
        fun = "cfa" if task.get("branch_id") == "NC02.factor" else "sem"
        code = [
            f"model <- {rq(syntax)}",
            f'fit <- lavaan::{fun}(model=model, data=dat, estimator="MLR", missing="listwise")',
            "print(summary(fit, fit.measures=TRUE, standardized=TRUE))",
            "# No structural coefficient is automatically a causal effect.",
        ]
    elif adapter == "cox":
        packages = ["survival"]
        duration = ident(require(v, "duration"))
        event = ident(require(v, "event"))
        features = [ident(c) for c in require(v, "features")]
        if not features:
            raise ValueError("Cox covariates required")
        code = [
            f"fit <- survival::coxph(survival::Surv({duration}, {event}) ~ "
            + "+".join(features)
            + ", data=dat, x=TRUE)",
            "print(summary(fit))",
            "print(survival::cox.zph(fit))",
            "# Survival prediction additionally needs independent calibration and discrimination evaluation.",
        ]
    elif adapter == "survey":
        packages = ["survey"]
        survey = task.get("data_contract", {}).get("survey_design", {})
        psu = ident(require(survey, "psu"))
        strata = ident(require(survey, "strata"))
        weight = ident(require(v, "weight"))
        code = [
            f"des <- survey::svydesign(ids=~{psu}, strata=~{strata}, weights=~{weight}, data=dat, nest=TRUE)",
            f"fit <- survey::svymean(~{y}, design=des, na.rm=FALSE)",
            "print(fit)",
            "# Specify finite population correction and lonely-PSU policy if required by the sample design.",
        ]
    elif adapter == "mice":
        packages = ["mice"]
        methods = require(a, "imputation_methods")
        if not isinstance(methods, dict):
            raise ValueError("Named per-column imputation methods required")
        code = ["methods <- mice::make.method(dat)"] + [
            f"methods[{rq(ident(k))}] <- {rq(val)}" for k, val in methods.items()
        ]
        code += [
            f"fit <- mice::mice(dat, m={int(require(a, 'imputations'))}, method=methods, seed={int(a.get('seed', 20261019))}, printFlag=FALSE)",
            "print(fit)",
            "# Declare the downstream estimand and pool complete-data estimates with an appropriate combining rule.",
        ]
    elif adapter == "qca":
        packages = ["QCA"]
        conditions = [ident(c) for c in require(v, "conditions")]
        outcome = ident(require(v, "outcome"))
        consistency = float(require(a, "consistency_cutoff"))
        frequency = int(require(a, "frequency_cutoff"))
        if not 0.5 < consistency <= 1 or frequency < 1:
            raise ValueError(
                "Provide a consistency cutoff in (0.5, 1] and a positive frequency cutoff"
            )
        code = [
            f"stopifnot(all(as.matrix(dat[, {vector(conditions + [outcome])}, drop=FALSE]) >= 0), all(as.matrix(dat[, {vector(conditions + [outcome])}, drop=FALSE]) <= 1))",
            f"tt <- QCA::truthTable(dat, outcome={rq(outcome)}, conditions={vector(conditions)}, incl.cut={consistency}, n.cut={frequency}, show.cases=TRUE)",
            "fit <- QCA::minimize(tt, details=TRUE)",
            "print(fit)",
            "# Calibration must be independently justified; set membership relations do not alone identify intervention effects.",
        ]
    else:
        raise ValueError("Unknown external code exporter: " + str(adapter))
    # Require all mapped analysis columns, without implicit complete-case deletion.
    cols = []
    for value in v.values():
        if isinstance(value, str):
            cols.append(ident(value))
        elif isinstance(value, list):
            cols.extend(ident(x) for x in value)
    cols += (
        list(task.get("data_contract", {}).get("survey_design", {}).values())
        if adapter == "survey"
        else []
    )
    cols = sorted(set(x for x in cols if isinstance(x, str)))
    missing_allowed = adapter == "mice"
    header = [
        "# Generated R analysis.",
        "# Run from this directory with Rscript --vanilla analysis.R.",
        f"set.seed({int(a.get('seed', 20261019))})",
    ]
    header += [
        f'if (!requireNamespace({rq(pkg)}, quietly=TRUE)) stop("Missing package: {pkg}; prepare the matching HSS module")'
        for pkg in packages
    ]
    header += [
        f"dat <- read.csv({rq(Path(data_path).resolve())}, check.names=FALSE)",
        f"stopifnot(all({vector(cols)} %in% names(dat)))",
    ]
    if not missing_allowed:
        header += [
            f'if (anyNA(dat[, {vector(cols)}, drop=FALSE])) stop("Missing analysis values: specify preprocessing; no automatic dropping")'
        ]
    footer = ['saveRDS(fit, "fit.rds")']
    path = outdir / "analysis.R"
    path.write_text("\n".join(header + code + footer) + "\n", encoding="utf-8")
    return dict(
        code_file=str(path),
        packages=packages,
        status="code_exported",
        executed=False,
        next_action="Prepare the listed packages and run analysis.R with the configured R interpreter",
    )
