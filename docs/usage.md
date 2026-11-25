# Install and use

## Select resources

```bash
python -m pip install .
hss browse
hss browse --field economics
hss search "差分"
hss methods "因果"
hss methods --executable
hss plan field:history
hss prepare bundle:historical-study --resources-only
```

The CLI emits JSON. Lists returned by `browse` contain the exact field, direction and module IDs. An empty selection does nothing. Resource-only preparation still reports any compatible existing software; missing software is listed as `not_prepared`.

For ordinary installation, remove `--resources-only`. HSS prepares Python or Node packages and R packages when Rscript is available. It does not install an operating system, R distribution, desktop application or database server. `pending` describes connections that still need the host's runtime or service. CLI exit codes are 0 for complete results, 2 for a preparation containing pending or failed components, and 1 for a request error.

`--space` is a global argument and precedes the command. Without it, `HSS_RESEARCH_SPACE` or `~/.hss` supplies the persistent research space. A `--layout paths.json` file can override any area with an absolute path or a path relative to the research space:

```json
{"env":"System/env/hss","knowledge":"System/knowledge/hss","skills":"System/skills","cache":"D:/ResearchCache/hss"}
```

## Reuse interpreters and choose backends

```json
{
  "action": "prepare",
  "space": "/research",
  "selections": ["descriptive-statistics", "did-staggered"],
  "backends": {"did-staggered":"group-time"},
  "existing": [{"kind":"python","command":["/research/System/env/seedenv/statistics/bin/python"]}],
  "options": {"timeout":1800}
}
```

Save this as `request.json` and run `hss request request.json`. The path is an example; supply the actual interpreter command registered by the host. The same payload without `action` works with `hss prepare-request request.json`. Python components check their required imports and package constraints before reuse.

`did-staggered` offers `group-time`, `continuous-dose` and `treatment-switching`; `regression-discontinuity` offers `local-polynomial` and `local-randomization`; `synthetic-control` offers `reference`, `synth` and `synthetic-did`. Alternative backends prepare different software for the researcher's chosen method. They do not change the mathematical meaning of a study task.

```bash
hss bind python-empirical /path/to/python
hss bind r-survey /path/to/Rscript
hss exec r-survey --vanilla /path/to/analysis.R
hss installed
hss remove prediction
hss remove prediction --prune
```

Use the JSON `bind` action to provide interpreter environment variables such as `R_LIBS_USER`. A command component can use a configured launcher command; `existing` entries for such a launcher should name its `components` explicitly.

Offline Python preparation accepts `options.offline=true` and `options.find_links=/path/to/wheels`. Node uses its local npm cache in offline mode. R offline use binds an existing library. Models, corpora, restricted datasets and remote service accounts are selected and connected separately.

## Run research

```bash
hss project ./my-study --title "Community participation"
hss explore brief.json
hss context interview-design interview-coding thematic-analysis
hss run examples/materials-study.json --output ./my-study/results/materials-01
hss prepare principal-components linear-association
hss run examples/measurement-study.json --output ./my-study/results/models-01
```

Every run uses an empty output directory. Paths in a study file are relative to that file. In the JSON API, `base` specifies this directory explicitly. A task's `source_task` points to an earlier task producing a derived table. Full-sample exploratory representations cannot be used as preprocessing of a held-out prediction set.

`results.json` contains actual task results. Each task directory contains `result.json`, exported CSV tables and any material-specific outputs. `results.md` links these outputs. The questionnaire and experiment examples generate instruments; the invented interviews and synthetic numerical data are teaching examples, not collected research observations.

## Query information

```bash
hss connect crossref "community participation" --limit 10
hss connect openalex "social mobility" --limit 10
hss connect worldbank SP.POP.TOTL --options worldbank-options.json
hss resources
hss index argument-analysis concept-analysis
hss lookup "论证"
```

World Bank options can be `{"country":"CHN","date":"2020:2024"}`. Zotero options specify `{"scope":"users","library":"YOUR_NUMERIC_ID"}`. API keys are read from the host environment (`OPENALEX_API_KEY`, `ZOTERO_API_KEY`) or a named `key_env`; HSS does not place keys in its catalogue.

The local knowledge index contains explicitly selected modules and their guides. Bibliography tasks create a project-owned SQLite database from actual records. Other resource entries describe their official service and access route; an entry alone does not create API access or download a database.
