"""Execute explicitly specified tasks and connect their research outputs."""

import csv
import math
from pathlib import Path
import re

from .catalog import DATA, read_json, write_json
from . import materials


def normalize(task):
    task = dict(task)
    if task.get("operation") == "r_analysis":
        from .external import R_COMPONENTS

        if task.get("adapter") not in R_COMPONENTS:
            raise ValueError("Unknown R analysis adapter: " + str(task.get("adapter")))
        return task
    catalog = read_json(DATA / "methods.json")
    if task.get("branch_id"):
        branch = next(
            (x for x in catalog["branches"] if x["id"] == task["branch_id"]), None
        )
        if not branch:
            raise ValueError("Unknown branch: " + task["branch_id"])
        if not branch.get("operation"):
            raise ValueError(
                "This branch uses research guidance or an external implementation: "
                + branch["id"]
            )
        if task.get("operation") and task["operation"] != branch["operation"]:
            raise ValueError("The operation does not implement the selected branch")
        task["operation"] = branch["operation"]
        task.setdefault("selected_method_id", branch["method"])
    method_id = task.get("selected_method_id", task.get("method_id"))
    if method_id:
        method = next((x for x in catalog["methods"] if x["id"] == method_id), None)
        if not method:
            raise ValueError("Unknown method: " + method_id)
        if not method.get("operation"):
            raise ValueError(
                "The selected method has no bundled computation; use its upstream implementation"
            )
        if task.get("operation") and method["operation"] != task["operation"]:
            raise ValueError("Selected method and operation disagree")
        task["operation"] = method["operation"]
    if not task.get("operation"):
        raise ValueError("Specify an operation or an implemented method branch")
    if task.get("selected_method_id") == "f19.difference_in_means" and task.get(
        "variables", {}
    ).get("controls"):
        raise ValueError(
            "An unadjusted difference in means has no controls; select the adjusted randomized-experiment method"
        )
    prediction = task.get("prediction", {})
    targets = {
        "iid": {"iid_holdout", "iid_three_way"},
        "future_new_units": {"group_time"},
        "future_existing_units": {"time_forward"},
        "new_groups": {"group_holdout"},
        "new_regions": {"spatial_block"},
    }
    if (
        prediction.get("target_domain") in targets
        and prediction.get("split") not in targets[prediction["target_domain"]]
    ):
        raise ValueError(
            "Prediction split does not match the declared deployment target"
        )
    return task


def ordered_tasks(plan):
    tasks = {t["id"]: normalize(t) for t in plan["tasks"]}
    if len(tasks) != len(plan["tasks"]):
        raise ValueError("Task IDs must be unique")
    if any(not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", x) for x in tasks):
        raise ValueError(
            "Use letters, numbers, dots, underscores or hyphens for task IDs"
        )
    done, active, result = set(), set(), []

    def visit(key):
        if key in done:
            return
        if key not in tasks:
            raise ValueError("Unknown upstream task: " + key)
        if key in active:
            raise ValueError("Task dependencies contain a cycle")
        active.add(key)
        task = tasks[key]
        for upstream in task.get("depends_on", []) + (
            [task["source_task"]] if task.get("source_task") else []
        ):
            visit(upstream)
        active.remove(key)
        done.add(key)
        result.append(task)

    for key in tasks:
        visit(key)
    return result


def clean(value):
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if hasattr(value, "tolist"):
        return clean(value.tolist())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def write_tables(result, out):
    files = {}
    for name, records in result.get("tables", {}).items():
        if not re.fullmatch(r"[A-Za-z0-9_-]+", name):
            raise ValueError("Invalid table name")
        if not records:
            continue
        path = out / (name + ".csv")
        keys = list(dict.fromkeys(k for r in records for k in r))
        with path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=keys)
            writer.writeheader()
            writer.writerows(records)
        files[name] = str(path)
    result["table_files"] = files


def execute_task(task, out, base):
    task = dict(task)
    for name in ("data", "script"):
        if task.get(name):
            task[name] = str((base / Path(task[name])).resolve())
    task["paths"] = [str((base / Path(p)).resolve()) for p in task.get("paths", [])]
    if task.get("datasets"):
        task["datasets"] = [
            {**source, "path": str((base / source["path"]).resolve())}
            for source in task["datasets"]
        ]
    if task["operation"] == "command":
        task["arguments"] = [
            {"path": str((base / a["path"]).resolve())} if isinstance(a, dict) else a
            for a in task.get("arguments", [])
        ]
    out.mkdir(parents=True, exist_ok=False)
    if task["operation"] in {"r_analysis", "script", "command"}:
        from .external import execute

        result = execute(task, out)
    elif task["operation"] == "sql":
        from .tabular_sql import execute

        result = execute(task, out)
    elif task["operation"] in materials.FUNCTIONS:
        result = materials.FUNCTIONS[task["operation"]](task, out)
    else:
        from .empirical import causal, descriptive
        import pandas as pd

        op = task["operation"]
        functions = {**causal.FUNCTIONS, **descriptive.FUNCTIONS}
        if op not in functions:
            raise ValueError("Unknown operation: " + op)
        data = pd.read_csv(task["data"])
        if data.empty:
            raise ValueError("Analysis data is empty")
        variables = task.get("variables", {})
        if variables.get("weight") and op not in {"summary", "distribution", "ols"}:
            raise ValueError(
                "This operation does not implement the declared weights; use the matching upstream method"
            )
        if task.get("inference", {}).get("cluster") and op not in {
            "rct",
            "iv",
            "aipw",
            "dml_irm",
            "dml_plr",
            "did_2x2",
            "local_rd",
            "ols",
        }:
            raise ValueError("This operation does not implement clustered inference")
        contract = task.get("data_contract", {})
        keys = contract.get("primary_key", [])
        if keys and (data[keys].isna().any().any() or data.duplicated(keys).any()):
            raise ValueError("The declared observation key must be complete and unique")
        metadata = task.get("variable_metadata", {})
        prediction_time = task.get("prediction", {}).get("prediction_time")
        treatment_time = task.get("design", {}).get("treatment_time")
        if op in {"predict", "text_predict", "conformal"}:
            features = variables.get("features", []) + (
                [variables["text"]] if variables.get("text") else []
            )
            for feature in features:
                available = metadata.get(feature, {}).get("available_at")
                if (
                    available is not None
                    and prediction_time is not None
                    and available > prediction_time
                ):
                    raise ValueError(
                        "Feature is unavailable at prediction time: " + feature
                    )
        if op in causal.FUNCTIONS:
            for feature in variables.get("controls", []):
                measured = metadata.get(feature, {}).get("measured_at")
                if (
                    measured is not None
                    and treatment_time is not None
                    and measured >= treatment_time
                ):
                    raise ValueError(
                        "This design requires baseline controls: " + feature
                    )
        if (
            task.get("inference", {}).get("cluster")
            and data[task["inference"]["cluster"]].isna().any()
        ):
            raise ValueError("Cluster labels contain missing values")
        alpha = task.get("inference", {}).get("alpha", 0.05)
        if not 0 < alpha < 1:
            raise ValueError("Inference alpha must lie between zero and one")
        if op in {"rct", "iv", "aipw", "dml_irm", "local_rd"} and not task.get(
            "estimand", {}
        ).get("kind"):
            raise ValueError("Specify the estimand kind for this design")
        if task.get("source_task") and op in {"predict", "text_predict", "conformal"}:
            raise ValueError(
                "Fit preprocessing within prediction training folds; do not feed a whole-sample representation into prediction"
            )
        result = functions[op](task, data)
        if "derived_frame" in result:
            path = out / "derived_data.csv"
            result.pop("derived_frame").to_csv(path, index=False)
            result["derived_data"] = str(path)
    result = clean(result)
    result.update(task=task["id"], operation=task["operation"], status="completed")
    write_tables(result, out)
    write_json(out / "result.json", result)
    return result


def run(plan, output, base=None):
    tasks = ordered_tasks(plan)
    if not tasks:
        raise ValueError("Add at least one research task before execution")
    output = Path(output).resolve()
    if output.exists() and any(output.iterdir()):
        raise FileExistsError("Choose an empty output directory: " + str(output))
    base = Path(base or ".").resolve()
    output.mkdir(parents=True, exist_ok=True)
    results = {}
    write_json(output / "study.json", plan)
    for task in tasks:
        task = dict(task)
        if task.get("source_task"):
            upstream = results[task["source_task"]]
            source = (
                upstream.get("table_files", {}).get(task["source_table"])
                if task.get("source_table")
                else upstream.get("derived_data")
            )
            if not source:
                raise ValueError("The upstream task produced no derived data table")
            task["data"] = source
        results[task["id"]] = execute_task(task, output / task["id"], base)
        write_json(output / "results.json", results)
    lines = [
        "# " + plan.get("title", "Research results"),
        "",
        plan.get("question", ""),
        "",
    ]
    for key, result in results.items():
        lines += ["## " + key, "", "Operation: `" + result["operation"] + "`", ""]
        for estimate in result.get("estimates", []):
            lines += ["- " + "; ".join(f"{k}: {v}" for k, v in estimate.items())]
        lines += ["", *result.get("notes", []), ""]
        for name, path in result.get("table_files", {}).items():
            lines.append(f"[{name}]({Path(path).relative_to(output).as_posix()})")
        lines += ["", f"[Full result]({key}/result.json)", ""]
    (output / "results.md").write_text("\n".join(lines), encoding="utf-8")
    return {
        "output": str(output),
        "tasks": list(results),
        "results": str(output / "results.json"),
        "report": str(output / "results.md"),
    }
