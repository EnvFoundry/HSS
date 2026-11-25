---
name: hss-theory
description: Use when clarifying concepts, reconstructing arguments, developing theory, analysing norms or building formal social models.
---

# 概念、理论与规范论证

Separate definitions, assumptions, empirical statements and value premises. Reconstruct strong alternative positions. Develop the central reasoning continuously, then discuss its boundaries and implications.

Start with `hss search "TASK"` or `hss browse`. Load only the relevant modules using `hss context concept-analysis`. The same functions are available as HSS MCP tools. Read `theory.md` from the returned context when its research procedure is needed.

Use `hss plan MODULE...` to inspect the selected resources and software. Prepare the user’s selected modules with `hss prepare MODULE...`; keep data, code and findings inside the research project. Use an existing execution binding when available.

Useful modules: concept-analysis, argument-analysis, theory-building, normative-analysis. Add other modules only when the question needs them.

Return a concrete research output appropriate to the task, including the relevant source locations, calculations or developed argument. Record the next unresolved research question when further work is needed.

Before writing an executable study task, call `hss describe OPERATION` (MCP: `hss_describe`) for the exact input fields and a complete task example. Pass `{ "tasks": [TASK] }` to `hss_run` with a project output directory. Material passage offsets are Unicode code points into the unchanged document text.
