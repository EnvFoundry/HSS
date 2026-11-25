# Executable operations

Use `hss describe OPERATION` to retrieve exact inputs and a complete example task. The same information is available through `hss_describe` and the MCP resource `hss://operations`. `hss://study-schema` supplies the JSON study schema.

## Statistical operations

| Operation | Scope |
|---|---|
| `rct` | Binary assignment; optional centered baseline covariates and their treatment interactions; HC3 or clustered CR1. |
| `iv` | 2SLS with robust or clustered covariance; requires identification beyond a first-stage association. |
| `aipw` | Binary treatment ATE, cross-fitted propensity and outcome models. |
| `dml_irm` | AIPW score with cross-fitted random forests for the binary-treatment ATE. |
| `dml_plr` | Partially linear parameter; distinct from a general heterogeneous-treatment ATE. |
| `did_2x2` | Balanced panel differences or repeated-cross-section cell contrasts; treated-group indicator is constant within unit. |
| `local_rd` | Sharp assignment inside an explicitly chosen window; distinct from local-polynomial RD. |
| `synthetic_control` | One treated unit, balanced panel, nonnegative donor weights summing to one; no invented confidence interval. |
| `summary` | Positive optional weights; unweighted mean t intervals; weighted point estimates. |
| `distribution` | ECDF; Gini and Theil on nonnegative outcomes with positive mean. |
| `ols` | OLS or explicit WLS with HC3 or clustered CR1 covariance. |
| `predict` | Regression or classification; explicit iid, group, spatial or forward-time split; preprocess training rows only. |
| `text_predict` | Training-only TF-IDF; declare empty-text handling and character or word features. |
| `kmeans` | Standardized features; repeated subsample agreement; groups require substantive interpretation. |
| `pca` | Standardized PCA; exports original columns plus PC1, PC2, etc. |
| `topic` | Exploratory count-based topics; Chinese word analysis requires explicit tokenization. |
| `kaplan_meier` | Independent right censoring, binary event, no left truncation; pointwise Greenwood normal approximation. |
| `autoreg` | One regularly spaced series; expanding-window one-step OLS forecasts. |
| `moran` | Explicit weights matching data-unit order; fixed-weight random-label permutation test. |
| `network` | Undirected binary graph; duplicate edges collapsed; degree, clustering and connected components. |
| `oaxaca` | Reference group zero; within-group iid percentile bootstrap; descriptive decomposition. |
| `meta` | Common-effect or DerSimonian–Laird random effects, normal intervals; compatible scales required. |
| `multiple_testing` | Declared hypothesis family; BH uses independence or suitable positive dependence. |
| `conformal` | Exchangeable regression observations, separate train/calibration/test splits, marginal coverage target. |

## Material and collection operations

| Operation | Output |
|---|---|
| `corpus` | Document text, source locations and paragraph offsets in JSONL. Text, TEI/XML and DOCX use the standard library; PDF extraction uses the optional document component. |
| `concordance` | Exact matched passages with Unicode offsets and left/right context. |
| `coding` | Supplied annotations with exact passages, code counts and document-level code co-occurrence. |
| `agreement` | Two-rater nominal agreement and Cohen kappa on shared units. |
| `collate` | Character segments and an HTML line comparison between two supplied witnesses. |
| `argument_map` | Named claims, relations, source descriptions and an argument document. |
| `questionnaire` | Structured instrument and readable preview, with explicit conditions on earlier items. |
| `experiment` | Standalone keyboard-response browser task and downloaded response CSV; characterize timing for the intended study. |
| `table` | CSV column summaries and declared-key uniqueness. |
| `bibliography` | Project SQLite bibliography from supplied source records. |

## External R

Code export covers `did`, `contdid`, `did_multiplegt`, `rdrobust`, `grf`, `synthdid`, `lavaan`, `cox`, `survey`, `mice` and `qca`. The returned result records `executed: false`. Prepare the matching software and execute the script with the configured R interpreter to obtain a fit. For broader methods, use the selected upstream package directly.

## Integration scope

The development checks cover Python numerical calculations against known answers and an independent statistics library, complete study examples, selected preparation and removal, shared dependencies, path mapping, runtime reuse, plugin relocation, the JSON CLI, the official Python MCP client, and the TypeScript-to-Python transport. A fresh core-only installation and a separately prepared numerical component are exercised before delivery.

R numerical execution, remote authenticated data services, desktop applications and a running Qiushi/Origo product have separate deployment requirements. Their catalogue entries and exports do not imply they have been executed in this development environment. Linux is the locally exercised platform; Windows and Python 3.11/3.12 jobs are configured in CI.

## Method reference

The method cards describe a wider research space than the bundled operations. A branch with no operation may still be fully actionable through an upstream implementation, a qualitative workflow or theoretical work. Matching a question to a method depends on the concrete research design and materials.
