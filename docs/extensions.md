# Extend HSS

Use `hss --extension /path/to/extension.json browse` to add catalogue entries without changing the built-in catalogue. The file can contain `fields`, `modules`, `components`, `bundles` and `resources` arrays. IDs must be unique. New field directions reference module IDs; a module can appear under more than one direction.

A module declares `id`, `name`, `summary`, `kind`, `components`, `operations`, `r_exports`, `inputs`, `outputs`, `knowledge`, `skill`, `workflows`, `prompts`, `requires` and `execution`. Copy the closest existing module, then replace its content with the actual capability. Required modules are expanded once; cycles produce a clear error. Backends map a named implementation choice to component IDs.

Custom knowledge, Skills, workflows and prompts live beside the extension JSON in their corresponding directories. They use the same relative paths as the built-in data directory. If no custom file is present, an existing HSS asset can be reused. Exported plugin packages include the merged catalogue and referenced assets.

A software component declares a kind:

| Kind | Required information | Preparation |
|---|---|---|
| `python` | Package requirements, import names | Reuse a compatible interpreter or create a venv |
| `r` | R package names and setup text | Connect Rscript, install packages to HSS's R library |
| `node` | npm packages and setup text | Connect Node/npm, install into the selected component |
| `command` | Command name, optional probe arguments, setup text | Connect an existing command |
| `service` | Official service and connection instructions | Use the host's service connection |

Python imports and installed package requirements are both tested before reuse. A package should have an upstream URL. Large models and data should be represented as separate resource choices; avoid placing them in a core software component.

New executable operations need actual code, concrete inputs and an example demonstrating their intended use. Add statistical operations to the empirical layer or material operations to `materials.py`; the study runner handles the output directory and tabular exports. If an upstream method is substantially broader than a short local adapter, expose the upstream implementation and document its required input instead of labeling a small approximation as the whole method.

Method cards reference sources through `sources.json`. The catalogue can include methods awaiting an implementation, but their operation remains null. Additional external APIs belong in `connectors.py` with explicit input/output mappings; service directory entries need not pretend to be executable connectors.

Keep host integration in the JSON and MCP surfaces. New capabilities should be callable by an existing host without importing a product-specific UI or task scheduler into HSS.
