# Research workbench

Start the compiled interface from the repository:

```bash
node packages/client/server.mjs --space /research --python python
```

Open `http://127.0.0.1:8787`. On Windows, use `--space D:\Research` and the Python executable that provides HSS. The source checkout supplies its own Python module path; a packaged client can use an installed HSS distribution. The server listens on the local machine. Product hosts can embed `<hss-workbench>` and supply their existing `HSSClient` transport instead.

The four views share one research process:

1. Select fields, directions or individual modules. Alternative backends appear on the relevant module cards. Inspect destinations, then prepare the selected resources and software.
2. Describe the phenomenon, question, research aim, scope and available material. Explore returns specific questions and candidate designs. Blueprint combines the selected modules' input contracts, research guides, workflows and software. Create a project when the design is concrete enough to retain.
3. Add actual tasks using their operation examples. Set the directory containing the data and scripts, choose a result directory and run the study. Tasks may depend on preceding tasks. Set `source_task` and `source_table` to pass a named upstream result table to the next task as its data.
4. Supply the authored manuscript sections and bibliographic records. Reference computed tables by their `result.json` path and table name. The manuscript operation assembles the actual text and tables as Markdown.

For the standalone server, relative project, material and output paths are resolved inside `--space`. CLI paths retain the caller's working directory. The host Agent supplies model inference and the substantive reasoning; HSS supplies research context, execution and output assembly.

## SQL

`examples/sql/study.json` joins two CSV files and computes group summaries. CSV types are explicit; empty values become SQL NULL. Query parameters can be supplied separately. Each named query becomes a CSV result table, and `analysis.sqlite` retains the loaded data in the task's output directory.

```bash
hss run examples/sql/study.json --output /research/Projects/sql/results
```

## R analysis

Prepare the corresponding R component, using an existing Rscript installation. Then include `r_analysis` in the same study as material or numerical tasks:

```json
{
  "tasks": [{
    "id": "duration-model",
    "operation": "r_analysis",
    "adapter": "cox",
    "data": "data.csv",
    "variables": {"duration": "duration", "event": "event", "features": ["age"]}
  }]
}
```

The task records `analysis.R`, `fit.rds`, textual output and messages. The Cox, lavaan and survey adapters also return estimate tables. All eleven adapters can execute this way; `export-r` remains useful when another system will execute the R code.

## Project code

Use `script` when the research requires a fuller upstream API or a custom model:

```json
{
  "tasks": [{
    "id": "analysis",
    "operation": "script",
    "component": "python-spatial",
    "script": "analysis/spatial.py",
    "data": "data/regions.csv",
    "parameters": {"neighbors": 5}
  }]
}
```

The selected component must be prepared or bound. Python, R and Node scripts receive the absolute path of `input.json` as their first argument. They run in their own task output directory and can write `result.json` containing `tables`, `estimates`, `notes` or other JSON research results. Other created files are returned as artifacts. `data`, `paths` and `script` are resolved from the study's base directory. The runtime preserves the registered interpreter's environment.

This interface supports the full installed package API; it does not reduce a research package to the bundled convenience operations. A project may contain R, Python, JavaScript and SQL tasks in one dependency graph.

## Native text tools

Select `corpus-assembly=rust` or `text-concordance=rust` for the Rust engine. Select `text-collation=cpp` or `translation-analysis=cpp` for the C++ engine. Preparation compiles into `System/env/hss/software/native-corpus` or `native-alignment`, and records reusable executable commands. `HSS_RUSTC` can name a nondefault Rust compiler; preparation options can supply `rustc` or `cxx`.

Rust profiles count UTF-8 bytes, Unicode scalar values, lines and whitespace-separated tokens. Exact concordances operate within a line and report both byte and character offsets. These are text operations; Chinese linguistic segmentation belongs to the selected language-processing package. C++ alignment computes exact character edit distance and aligned segments, including non-ASCII text and filenames.

## Manuscript assembly

```json
{
  "title": "A study of participation",
  "sections": [{
    "heading": "Results",
    "text": "The accompanying table reports the observed group means.",
    "tables": [{"result": "results/summary/result.json", "name": "summary", "caption": "Group summaries"}]
  }],
  "references": [{"citation": "Bibliographic entry supplied by the researcher", "url": "https://example.org/source"}]
}
```

```bash
hss manuscript manuscript.json --output writing/draft
```

Each section needs authored text. References come from supplied records. The host Agent can create these inputs from the research materials, model outputs and discussion with the researcher. Use the `research-publishing` component to typeset the resulting Markdown with Quarto or Pandoc.

## Prepared command-line software

Use `command` with a registered component such as Tesseract or Quarto. Arguments are strings; use `{"path":"materials/page.png"}` for inputs resolved from the study base. Output names remain relative to the task directory. For example, `hss describe command` returns an OCR task. Standard output, messages and created files are retained with the study.
