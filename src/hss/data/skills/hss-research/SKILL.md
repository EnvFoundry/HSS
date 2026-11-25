---
name: hss-research
description: Use when turning an HSS research question, existing materials or an unfinished plan into a concrete study.
---

# 研究探索与任务组织

Write a coherent research brief, compare materially different routes, then express executable tasks separately from interpretive work. Keep the user’s question central and revise the design when materials change what can be learned.

Create a project with `hss project PROJECT --title TITLE` when it needs a workspace. Write `research.json` with the phenomenon, question, goal, scope and available materials. Call `hss explore research.json` (MCP: `hss_explore` with `brief`) to develop candidate routes and the next concrete questions. Compare a small number of materially different designs, record the researcher's choices, then express computational tasks in `study.json`. Keep interpretive work and unresolved conceptual questions in the project as substantive research tasks.

Start with `hss search "TASK"` or `hss browse`. Load only the relevant modules using `hss context research-question`. The same functions are available as HSS MCP tools. Read `research.md` from the returned context when its research procedure is needed.

Use `hss plan MODULE...` to inspect the selected resources and software. Prepare the user’s selected modules with `hss prepare MODULE...`; keep data, code and findings inside the research project. Use an existing execution binding when available.

Useful modules: research-question, literature-search, theory-building. Add other modules only when the question needs them.

Return a concrete research output appropriate to the task, including the relevant source locations, calculations or developed argument. Record the next unresolved research question when further work is needed.

Before writing an executable study task, call `hss describe OPERATION` (MCP: `hss_describe`) for the exact input fields and a complete task example. Pass `{ "tasks": [TASK] }` to `hss_run` with a project output directory. Material passage offsets are Unicode code points into the unchanged document text.
