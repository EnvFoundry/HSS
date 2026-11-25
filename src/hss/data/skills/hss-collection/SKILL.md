---
name: hss-collection
description: Use when designing surveys, measurement instruments, sampling or behavioural experiments.
---

# 调查与行为研究

Connect each item or manipulation to the research question. Specify the sampling or allocation structure, pilot the collection procedure and retain the meaning of the resulting fields. Generate experimental responses only for software examples, clearly identified as simulated.

Start with `hss search "TASK"` or `hss browse`. Load only the relevant modules using `hss context sampling`. The same functions are available as HSS MCP tools. Read `survey.md` from the returned context when its research procedure is needed.

Use `hss plan MODULE...` to inspect the selected resources and software. Prepare the user’s selected modules with `hss prepare MODULE...`; keep data, code and findings inside the research project. Use an existing execution binding when available.

Useful modules: sampling, questionnaire, scale-design, behavioural-experiments. Add other modules only when the question needs them.

Return a concrete research output appropriate to the task, including the relevant source locations, calculations or developed argument. Record the next unresolved research question when further work is needed.

Before writing an executable study task, call `hss describe OPERATION` (MCP: `hss_describe`) for the exact input fields and a complete task example. Pass `{ "tasks": [TASK] }` to `hss_run` with a project output directory. Material passage offsets are Unicode code points into the unchanged document text.
