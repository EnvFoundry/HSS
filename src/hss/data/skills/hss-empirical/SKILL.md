---
name: hss-empirical
description: Use when preparing data, choosing statistical implementations or running empirical HSS research.
---

# 实证研究与计算

Define the target quantity, observational units, variables, timing and study design before selecting an implementation. Use the full upstream software API when a task exceeds the bundled operation. Interpret estimates in the terms of the actual design.

Start with `hss search "TASK"` or `hss browse`. Load the modules that match the actual design: for example `hss context did-staggered` for a staggered policy, `hss context survey-analysis` for a complex sample, or `hss context descriptive-statistics` for sample description. Read the returned method guidance: causal studies use `causal.md`, prediction uses `prediction.md`, and other quantitative tasks use their own guide. The same functions are available as HSS MCP tools.

Use `hss plan MODULE...` to inspect the selected resources and software. Prepare the user’s selected modules with `hss prepare MODULE...`; keep data, code and findings inside the research project. Use an existing execution binding when available.

Useful modules: descriptive-statistics, linear-association, did-staggered, prediction. Add other modules only when the question needs them.

Return a concrete research output appropriate to the task, including the relevant source locations, calculations or developed argument. Record the next unresolved research question when further work is needed.

Before writing an executable study task, call `hss describe OPERATION` (MCP: `hss_describe`) for the exact input fields and a complete task example. Pass `{ "tasks": [TASK] }` to `hss_run` with a project output directory. Material passage offsets are Unicode code points into the unchanged document text.
