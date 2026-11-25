---
name: hss-writing
description: Use when forming an HSS article, report or book chapter from actual materials, analyses and arguments.
---

# 人文社科成果写作

Lead with the research question and contribution to understanding. Make each paragraph develop an argument with the relevant material or result. Use concise, connected prose; retain the author’s disciplinary voice.

Start with `hss search "TASK"` or `hss browse`. Load only the relevant modules using `hss context research-writing`. The same functions are available as HSS MCP tools. Read `writing.md` from the returned context when its research procedure is needed.

Use `hss plan MODULE...` to inspect the selected resources and software. Prepare the user’s selected modules with `hss prepare MODULE...`; keep data, code and findings inside the research project. Use an existing execution binding when available.

Useful modules: research-writing, research-publishing. Add other modules only when the question needs them.

Return a concrete research output appropriate to the task, including the relevant source locations, calculations or developed argument. Record the next unresolved research question when further work is needed.

Before writing an executable study task, call `hss describe OPERATION` (MCP: `hss_describe`) for the exact input fields and a complete task example. Pass `{ "tasks": [TASK] }` to `hss_run` with a project output directory. Material passage offsets are Unicode code points into the unchanged document text.
