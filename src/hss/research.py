"""Research formulation and project creation for an agent-led conversation."""

from pathlib import Path
from .catalog import DATA, read_json, write_json

ROUTES = {
    "interpretation": [
        "historical-sources",
        "literary-reading",
        "discourse-analysis",
    ],
    "theory": ["concept-analysis", "argument-analysis", "theory-building"],
    "normative": ["normative-analysis", "argument-analysis", "legal-interpretation"],
    "description": ["descriptive-statistics", "sampling", "survey-analysis"],
    "association": ["linear-association", "multilevel-models", "panel-models"],
    "causal": [
        "randomized-experiment",
        "adjusted-effects",
        "did-two-period",
        "did-staggered",
        "regression-discontinuity",
        "instrumental-variables",
    ],
    "prediction": ["prediction", "conformal-prediction", "time-series"],
    "experience": [
        "interview-design",
        "ethnography",
        "thematic-analysis",
        "grounded-theory",
    ],
    "synthesis": ["systematic-review", "literature-synthesis", "meta-analysis"],
}

QUESTIONS = {
    "causal": {
        "units": "处理分配给谁，结果记录在哪一级：个体、机构、地区还是其他单位？",
        "outcome": "要研究的结果是什么，如何测量，目标效应覆盖哪段时间？",
        "treatment_path": "谁在什么日期开始、改变或停止接受处理？是否存在不同实施批次？",
        "comparison": "哪些单位可提供未处理或尚未处理时的比较，比较的依据是什么？",
        "observation_periods": "每个单位有多少期处理前和处理后记录，是否能连接同一单位？",
    },
    "experience": {
        "participants": "哪些人的经验与问题直接相关，如何接近和选择他们？",
        "context": "经验发生在什么社会、制度和生活背景中？",
        "material_form": "现有材料是访谈、田野笔记还是其他记录，能否定位到具体片段？",
        "analytic_orientation": "研究着重解释经验意义、形成概念、比较案例还是理解实践过程？",
    },
    "prediction": {
        "deployment": "预测面对新的个体、地区还是未来时段？",
        "prediction_time": "预测在什么时点发生，当时真正可获得哪些输入？",
        "target": "目标变量、预测时间跨度和实际使用中的误差代价是什么？",
    },
    "interpretation": {
        "corpus_boundary": "材料范围和选择理由是什么，材料形成于什么语境？",
        "textual_witnesses": "采用哪些文本或作品，传承和差异是否影响解释？",
        "interpretive_question": "要解释的意义张力、历史关系或艺术问题具体是什么？",
    },
    "theory": {
        "concepts": "哪些核心概念需要区分、界定或重新表示？",
        "premises": "哪些前提已被接受，哪些是本研究提出的假设？",
        "contribution": "预期形成解释、命题、模型还是概念上的改变？",
    },
    "normative": {
        "values": "要比较哪些价值、义务或正当性原则？",
        "institutional_context": "判断作用于何种制度、行动者与现实条件？",
        "alternatives": "有哪些实质不同的规范立场需要共同讨论？",
    },
    "synthesis": {
        "scope_definition": "纳入哪些问题、对象、时间范围与文献类型？",
        "comparison_unit": "比较的是概念、论证、研究发现还是同一尺度上的效应？",
        "retrieval": "将从哪些数据库、目录和引用关系寻找相关材料？",
    },
}

ROUTE_QUESTIONS = {
    "randomized-experiment": ["实际随机分配机制是什么，随机化单位和分析单位是否一致？"],
    "adjusted-effects": ["哪些处理前变量同时影响处理和结果，是否存在足够的组间重叠？"],
    "did-two-period": ["是否确实只有两组两期，处理组是否在前期未处理而后期接受处理？"],
    "did-staggered": [
        "每个单位的首次实施日期是什么，处理是否持续，哪些批次与时期存在可用比较？"
    ],
    "regression-discontinuity": [
        "哪个阈值决定处理，运行变量能否被操纵，阈值附近还有什么同时变化？"
    ],
    "instrumental-variables": [
        "工具通过什么机制改变处理，为什么它不会经其他路径影响结果？"
    ],
}


def explore(brief, catalog):
    goal = brief.get("goal")
    missing = [
        key
        for key in ("phenomenon", "question", "goal", "scope", "materials")
        if not brief.get(key)
    ]
    candidates = [
        catalog.modules[k] for k in ROUTES.get(goal, []) if k in catalog.modules
    ]
    questions = [
        {"field": key, "question": question}
        for key, question in QUESTIONS.get(goal, {}).items()
        if not brief.get(key)
    ]
    return {
        "brief": brief,
        "next_questions": missing,
        "design_questions": questions,
        "next_turn": questions[:3],
        "candidate_routes": [
            {
                "module": x["id"],
                "purpose": x["summary"],
                "inputs": x["inputs"],
                "outputs": x["outputs"],
                "execution": x["execution"],
                "route_questions": ROUTE_QUESTIONS.get(x["id"], []),
            }
            for x in candidates
        ],
        "workflow": read_json(DATA / "workflows" / "research.json"),
        "next_action": "Develop two or more plausible designs against the available materials; choose with the researcher. A route is a candidate, not a design decision.",
    }


def blueprint(catalog, selections, brief=None):
    """Expand any field, direction or module into a concrete research workspace."""
    context = catalog.context(selections)
    modules = context["modules"]
    workflows = {
        name: read_json(catalog.asset("workflows", name))
        for m in modules
        for name in m.get("workflows", [])
    }
    components = sorted({name for m in modules for name in m.get("components", [])})
    return {
        "brief": brief or {},
        "modules": [
            {
                "id": m["id"],
                "name": m["name"],
                "purpose": m["summary"],
                "inputs": m["inputs"],
                "outputs": m["outputs"],
                "operations": m.get("operations", []),
                "r_adapters": m.get("r_exports", []),
                "backends": m.get("backends", {}),
                "components": m.get("components", []),
                "guides": m.get("knowledge", []),
            }
            for m in modules
        ],
        "operations": context["operations"],
        "software": [catalog.components[c] for c in components],
        "workflows": workflows,
        "knowledge": context["knowledge"],
        "design": explore(brief or {}, catalog),
        "execution": {
            "study": "Declare concrete tasks using operation input schemas; hss run executes their dependency order.",
            "upstream": "Use r_analysis for named R adapters; use script with a prepared component for project-specific Python, R or JavaScript analyses.",
            "interpretation": "Develop the selected interpretation or argument from the supplied materials, guided by the module's knowledge and workflow.",
        },
    }


def create_project(path, title, brief=None, selections=(), study=None, catalog=None):
    root = Path(path).resolve()
    if root.exists() and any(root.iterdir()):
        raise FileExistsError("Use an empty project directory")
    from .catalog import Catalog
    from .study import ordered_tasks

    catalog = catalog or Catalog()
    design = blueprint(catalog, selections, brief)
    study = (
        study
        if study is not None
        else {
            "title": title,
            "question": (brief or {}).get("question", ""),
            "tasks": [],
        }
    )
    ordered_tasks(study)
    for folder in ("materials", "data", "analysis", "results", "writing"):
        (root / folder).mkdir(parents=True, exist_ok=True)
    brief = {"title": title, **(brief or {})}
    write_json(
        root / "research.json",
        {
            **brief,
            "question": brief.get("question", ""),
            "goal": brief.get("goal", ""),
            "scope": brief.get("scope", ""),
            "materials": brief.get("materials", []),
            "alternative_designs": brief.get("alternative_designs", []),
            "selected_design": brief.get("selected_design"),
            "researcher_decisions": brief.get("researcher_decisions", []),
            "modules": [m["id"] for m in design["modules"]],
        },
    )
    write_json(
        root / "study.json",
        study,
    )
    write_json(root / "analysis" / "blueprint.json", design)
    guide = ["# " + title, "", brief.get("question", ""), ""]
    for module in design["modules"]:
        guide += [
            "## " + module["name"],
            "",
            module["purpose"],
            "",
            "Inputs: " + "; ".join(module["inputs"]),
            "Outputs: " + "; ".join(module["outputs"]),
            "",
        ]
    for name, content in design["knowledge"].items():
        guide += [content, ""]
    (root / "analysis" / "research-guide.md").write_text(
        "\n".join(guide), encoding="utf-8"
    )
    (root / "README.md").write_text(
        f"# {title}\n\nDevelop the research question and alternative designs in `research.json`.\nPut source material in `materials`, tabular data in `data`, executable tasks in `study.json`, and analysis code in `analysis`.\nRun `hss run study.json --output results/run-01`. Write the manuscript in `writing/manuscript.md`, using the actual results and cited sources.\n",
        encoding="utf-8",
    )
    (root / "writing" / "manuscript.md").write_text(
        f"# {title}\n\n## Research question\n\n## Scholarly context\n\n## Approach and materials\n\n## Findings or argument\n\n## Interpretation\n\n## References\n",
        encoding="utf-8",
    )
    return {
        "project": str(root),
        "brief": str(root / "research.json"),
        "study": str(root / "study.json"),
    }
