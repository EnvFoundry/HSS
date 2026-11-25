---
name: hss-materials
description: Use when assembling corpora, comparing texts, organizing historical sources or interpreting literary and cultural materials.
---

# 文本、史料与数字人文

Preserve document identity, location and context. Separate transcription and transformation from interpretation. Use search, comparison and text models to support close engagement with the materials.

Start with `hss search "TASK"` or `hss browse`. Load only the relevant modules using `hss context historical-sources`. The same functions are available as HSS MCP tools. Read `history.md` from the returned context when its research procedure is needed.

Use `hss plan MODULE...` to inspect the selected resources and software. Prepare the user’s selected modules with `hss prepare MODULE...`; keep data, code and findings inside the research project. Use an existing execution binding when available.

Useful modules: historical-sources, corpus-assembly, text-concordance, text-collation. Add other modules only when the question needs them.

Return a concrete research output appropriate to the task, including the relevant source locations, calculations or developed argument. Record the next unresolved research question when further work is needed.

Before writing an executable study task, call `hss describe OPERATION` (MCP: `hss_describe`) for the exact input fields and a complete task example. Pass `{ "tasks": [TASK] }` to `hss_run` with a project output directory. Material passage offsets are Unicode code points into the unchanged document text.
