# HSS

**Humanities and Social Sciences research environments, composed by task.**

[中文](README.zh-CN.md) · [Catalogue](docs/catalogue.md) · [Install and use](docs/usage.md) · [Host integration](docs/hosts.md) · [Research workflow](docs/research.md)

HSS brings research guidance, methods, software, Skills, literature and data connections into a persistent research space. Browse a field, narrow to a direction, and select reusable modules. Prepare a whole field, a research bundle, or individual modules; shared software is reused.

The catalogue covers philosophy, literature and language, history, arts and culture, sociology and anthropology, politics and public policy, law, Marxist theory, economics, business and finance, education, psychology, communication, population and human geography. Common research capabilities are shared across these fields.

## Implementation status

This is a working environment foundation, not a completed implementation of every HSS method. Field and direction entries provide navigation; the 91 modules combine shared research resources, software recipes and explicit operations. The runtime implements 24 statistical and 10 material/collection operations. The wider method catalogue, R exports and upstream software entries have different execution requirements, documented in [execution coverage](docs/execution.md).

Python implements preparation, studies and the CLI/MCP interface. TypeScript in `packages/client/src` implements the host client and selection UI. SQL in `state.py`, `knowledge.py` and `materials.py` manages SQLite records, research indexes and bibliographies. R generators produce scripts for external statistical environments. There is no custom Rust or C/C++ runtime in this repository; hosts and upstream tools keep their own execution implementations.

Host interfaces are implemented. Registration inside a running Qiushi Engine or Origo product, execution of every external software recipe, and end-to-end research examples for every direction remain separate work. Publishing the complete source does not imply that those integrations or all methods have been completed.

## Start

Python 3.11 or later. The catalogue, research guidance, material operations, JSON API and MCP server require only Python's standard library.

```bash
python -m pip install .
hss browse
hss search "interview"
hss plan bundle:interview-study
hss --space /research prepare bundle:interview-study --resources-only
hss context interview-coding
```

Selections use module IDs, `direction:FIELD/DIRECTION`, `field:FIELD`, `bundle:NAME`, or `all`. An empty selection installs nothing. `all` selects every module's default implementation; alternative backends remain explicit choices.

```bash
# Reuse an available Python environment or prepare the selected packages.
hss --space /research prepare descriptive-statistics randomized-experiment
hss --space /research run examples/randomized-study.json --output /research/Projects/example/results/run-01

# Material research requires no numerical stack.
hss run examples/materials-study.json --output /research/Projects/materials/results/run-01

# Host integrations: JSON request/response and MCP over stdio.
hss request request.json
hss serve
hss export bundle:historical-study --output /research/System/plugins/hss
```

Use `python -m hss` wherever the `hss` command is not on PATH. Windows research spaces can use paths such as `D:\Research`; neither an administrator account nor a global package installation is required.

## What is included

| Layer | Included capability |
|---|---|
| Navigation | 14 research fields and a common research entry, 60 directions, 91 reusable modules, 8 bundles |
| Research | 19 topic guides, 8 task Skills, 7 workflows, research design and interpretation prompts |
| Method reference | 371 method cards in 40 families; 241 design/task branches |
| Computation | 24 bounded statistical operations covering 32 branches; 10 material and instrument operations |
| Software | 41 Python, R, Node, command and service components, prepared or connected on selection |
| External R | 11 script generators for 15 registered branches and missing-data imputation |
| Information | 24 literature/data/service entries; clients for Crossref, OpenAlex, Zotero web libraries and World Bank indicators |
| Agent integration | Python API, CLI/JSON, stdio MCP, portable plugin package, TypeScript client and selection component |

A method card is a description, not an implemented estimator. Module records separately list `operations`, `r_exports`, software components and research guidance. R script generation is reported as code export until the script is actually run. Large datasets, language models and application servers are obtained separately from their configured services.

## Where resources go

| Resource | Default location in the research space |
|---|---|
| Interpreters, software bindings and installation records | `System/env/hss` |
| Skills | `System/skills/hss-*` |
| Research knowledge | `System/knowledge/hss` |
| Workflows and prompts | `System/workflows/hss`, `System/prompts/hss` |
| Exported integration package | Explicit destination, normally `System/plugins/hss` |
| MCP client configuration | Exported package's `mcp.json`; the host chooses where to register it |
| Selected local knowledge index | `System/databases/hss` |
| Download cache | `System/cache/hss` |
| Research material, analysis and manuscript | An explicitly chosen project directory, typically `Projects/<name>` |

Paths are configurable. Existing lowercase `system` is respected. The resource catalogue is unified; physical files follow their role in the host system. HSS does not add an account service, execution scheduler or model provider to the host.

## Development

```bash
python -m pip install -e '.[analysis]' statsmodels mcp build
python -m unittest discover -s tests
cd packages/client
npm install
npm run build
npm test
```

[Architecture](docs/architecture.md) describes dependencies and file ownership. [Extensions](docs/extensions.md) explains adding fields, directions, modules, methods and external services. [Execution coverage](docs/execution.md) lists the implemented operations and the scope of the integration checks.

MIT. Numerical adapters and the method catalogue were adapted from the Qiushi social-science toolkit supplied for this project; HSS adds a modular environment and host interface around those research capabilities.
