---
name: hss-qualitative
description: Use when designing interviews, coding materials, developing themes, comparing cases or integrating qualitative and quantitative work.
---

# 定性与混合研究

Choose an analytic approach appropriate to the question. Keep quotations attached to material locations, develop interpretations through comparison and explain how each theme relates to the question. Use agreement statistics only when the chosen approach calls for them.

Start with `hss search "TASK"` or `hss browse`. Load only the relevant modules using `hss context interview-design`. The same functions are available as HSS MCP tools. Read `qualitative.md` from the returned context when its research procedure is needed.

Use `hss plan MODULE...` to inspect the selected resources and software. Prepare the user’s selected modules with `hss prepare MODULE...`; keep data, code and findings inside the research project. Use an existing execution binding when available.

Useful modules: interview-design, interview-coding, thematic-analysis, mixed-methods. Add other modules only when the question needs them.

Return a concrete research output appropriate to the task, including the relevant source locations, calculations or developed argument. Record the next unresolved research question when further work is needed.

Before writing an executable study task, call `hss describe OPERATION` (MCP: `hss_describe`) for the exact input fields and a complete task example. Pass `{ "tasks": [TASK] }` to `hss_run` with a project output directory. Material passage offsets are Unicode code points into the unchanged document text.
