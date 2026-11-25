---
name: hss-literature
description: Use when searching, organizing, comparing or synthesizing scholarly literature in humanities and social sciences.
---

# 文献与研究综合

Build a question-led reading map. Preserve source locations and distinguish what was read in full from an abstract. Compare objects, theories, designs and findings before writing the synthesis.

Start with `hss search "TASK"` or `hss browse`. Load only the relevant modules using `hss context literature-search`. The same functions are available as HSS MCP tools. Read `literature.md` from the returned context when its research procedure is needed.

Use `hss plan MODULE...` to inspect the selected resources and software. Prepare the user’s selected modules with `hss prepare MODULE...`; keep data, code and findings inside the research project. Use an existing execution binding when available.

Useful modules: literature-search, bibliography, literature-synthesis, systematic-review. Add other modules only when the question needs them.

Return a concrete research output appropriate to the task, including the relevant source locations, calculations or developed argument. Record the next unresolved research question when further work is needed.

Before writing an executable study task, call `hss describe OPERATION` (MCP: `hss_describe`) for the exact input fields and a complete task example. Pass `{ "tasks": [TASK] }` to `hss_run` with a project output directory. Material passage offsets are Unicode code points into the unchanged document text.
