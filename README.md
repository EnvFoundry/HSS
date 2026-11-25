# HSS

**Humanities and Social Sciences research environments, composed by task.**

[中文](README.zh-CN.md) · [Catalogue](docs/catalogue.md) · [Install and use](docs/usage.md) · [Host integration](docs/hosts.md) · [Research workflow](docs/research.md)

HSS brings research guidance, methods, software, Skills, literature and data connections into a persistent research space. Browse a field, narrow to a direction, and select reusable modules. Prepare a whole field, a research bundle, or individual modules; shared software is reused.

The catalogue covers philosophy, literature and language, history, arts and culture, sociology and anthropology, politics and public policy, law, Marxist theory, economics, business and finance, education, psychology, communication, population and human geography. Common research capabilities are shared across these fields.

## Research environment

The research workbench connects module selection, research design, executable studies and manuscript assembly. Every catalogue direction expands into a blueprint containing its material inputs, outputs, research guidance, workflows, software choices and operation contracts. A host Agent develops the substantive research argument with the researcher and supplies model calls.

| Implementation | Responsibility |
|---|---|
| TypeScript | Typed host client, field/direction/module picker, research workbench and streaming HTTP transport |
| Rust | Streaming UTF-8 corpus profiles and keyword concordances with character and byte positions |
| C++17 | Exact Unicode text alignment using divide-and-conquer edit distance |
| SQL | Installation, knowledge and bibliography schemas; relational analyses of project CSV datasets |
| Python | Selected preparation, interpreter reuse, research task execution, statistics, materials, CLI and MCP |
| R | Named upstream statistical analyses, fitted models and result exports |

The root `plugin.json` makes this repository directly importable through Origo's repository source interface. Its actual extension loader has installed the package and called the research service successfully. Other hosts use the same stdio MCP or JSON interface.

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

## Workbench and native text tools

From a source checkout, the compiled workbench starts without a frontend build:

```bash
node packages/client/server.mjs --space /research --python python
# Open http://127.0.0.1:8787

hss --space /research prepare corpus-assembly text-collation --backend corpus-assembly=rust --backend text-collation=cpp
hss --space /research run examples/native/study.json --output /research/Projects/native/results
hss blueprint direction:history/sources
```

The native backends use an available Rust and C++ compiler; Windows C++ builds also support CMake with Visual Studio. They are selected explicitly. The ordinary material operations need no native compiler. See [workbench and study composition](docs/workbench.md) for SQL, R, project code and manuscript examples.

## What is included

| Layer | Included capability |
|---|---|
| Navigation | 14 research fields and a common research entry, 60 directions, 91 reusable modules, 8 bundles |
| Research | 19 topic guides, 8 task Skills, 7 workflows, research design and interpretation prompts |
| Method reference | 371 method cards in 40 families; 241 design/task branches |
| Computation | 41 study operations: 24 statistical, 13 material/native, SQL, R analysis, project scripts and prepared commands |
| Software | 43 Python, R, Node, native, command and service components, prepared or connected on selection |
| External R | 11 analysis adapters, usable in a study or exported as R scripts |
| Information | 24 literature/data/service entries; clients for Crossref, OpenAlex, Zotero web libraries and World Bank indicators |
| Agent integration | Python API, CLI/JSON, stdio MCP, portable plugin package, TypeScript client, module picker and research workbench |

Method cards support research design and retrieval. Executable tasks use the operation contracts; broader methods run through their prepared upstream software. R code export and R execution are separate actions. Large datasets, language models and application servers are obtained separately from their configured services.

## Where resources go

| Resource | Default location in the research space |
|---|---|
| Interpreters, software bindings and installation records | `System/env/hss` |
| Skills | `System/skills/hss-*` |
| Research knowledge | `System/knowledge/hss` |
| Workflows and prompts | `System/workflows/hss`, `System/prompts/hss` |
| Origo environment plugin | `System/env/hss-research`, separate from installed software and state |
| Portable exported plugin | Explicit destination, for example `System/plugins/hss` |
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
