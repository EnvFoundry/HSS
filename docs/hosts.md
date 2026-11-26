# Host integration

HSS exposes the same operations through Python, CLI/JSON and MCP. Qiushi Engine, Origo and other hosts supply a persistent research space, process execution and the user-facing research conversation.

## JSON bridge

Spawn `python -m hss request -`, write one JSON request to stdin, and read the JSON response from stdout. Progress records go to stderr. Preparation can receive existing interpreter commands, selected module IDs, backend choices and resource-area mappings. No network server is required.

```python
from hss.api import request
result = request({
    "action": "plan",
    "space": "/research",
    "selections": ["bundle:survey-study"],
    "existing": [{"kind":"python", "command":["/path/to/python"]}]
})
```

Actions: `browse`, `search`, `methods`, `resources`, `context`, `plan`, `prepare`, `installed`, `bind`, `remove`, `uninstall`, `exec`, `explore`, `blueprint`, `project`, `run`, `manuscript`, `connect`, `index`, `lookup`, `export-r`, `export`. The implementation is in `src/hss/api.py`; examples show concrete payloads.

The host owns its task ID, process group, cancellation and account state. It records the returned interpreter command and resources with the rest of its environment registrations. HSS reuses SeedEnv interpreters when their packages meet the selected component requirements. This integration shape does not require either environment to import the other.

## MCP and plugins

```bash
hss export bundle:policy-study --output ./hss-plugin
```

The resulting package includes its stdio server, runtime, selected Skills, `mcp.json`, `plugin.json` and `configure.py`. Generic MCP clients use `mcp.json`. The plugin manifest follows EnvFoundry's `skills`, `environment.resources`, `mcpServers`, `${RESEARCH_PYTHON}` and `${PACKAGE_ROOT}` conventions. The host supplies the actual persistent space.

After moving the package, run `python configure.py` inside it. This writes the current interpreter and package paths into the MCP configuration. Set `HSS_RESEARCH_SPACE` before configuring if the host uses a nondefault space. Register this configuration through the host's existing MCP mechanism.

The server supports the MCP 2025-11-25 lifecycle with stdio tools, resources and prompts. It can negotiate the earlier supported protocol dates listed in its implementation. The interface has been exercised with the official Python MCP client. Newer protocol generations and each product's packaging rules must be integrated through that product's supported interface.

Tools cover catalogue browsing, context, research formulation, preparation, studies, data queries and R code export. Resources expose knowledge guides and workflow descriptions; prompts help develop a design and interpret findings. Tool errors return `isError` with the underlying cause.

### Connection lifetime

A host using MCP 2025-11-25 can include
`capabilities.experimental["io.envfoundry/connection-lifecycle"] = {"scope":"request"}`
in `initialize`. HSS echoes that value only for this negotiated protocol.
On such a connection `hss_prepare` requires `task: {}`. Other operations finish
their owned work before replying. The host retains the process/container while
calls or unresolved Tasks remain; once they finish, it may close the connection.
Reopening the same research space preserves prepared resources, task IDs and
results. This does not authorize terminating a running preparation worker.

Without the capability request, ordinary synchronous calls and optional Tasks
remain available as before. No extra host configuration field is required.

## TypeScript and selection UI

`packages/client` includes compiled JavaScript, declarations, a typed client, a Node transport and a dependency-free web component.

```javascript
// Host backend
import { HSSClient } from './packages/client/lib/client.js';
import { pythonTransport } from './packages/client/node.mjs';
const client = new HSSClient(pythonTransport({python:'/path/to/python'}), '/research');
const plan = await client.plan(['bundle:interview-study']);
```

```javascript
// Product renderer: call the host's existing RPC bridge.
import { HSSClient } from './packages/client/lib/client.js';
import './packages/client/lib/picker.js';
const picker = document.querySelector('hss-picker');
await picker.connect(new HSSClient(request => host.call('hss', request), '/research'));
```

Render `<hss-picker></hss-picker>` in the product. The component keeps selections across filters and lets users inspect a plan or prepare only the selected modules. It emits `hss-prepared` and `hss-error`. The browser never directly invokes a shell; the host transport calls its existing execution interface.

## Direct Origo import

Add `https://github.com/EnvFoundry/HSS` through Origo's repository source import. The root `plugin.json` declares eight Skills and the stdio research service. Origo supplies `RESEARCH_PYTHON`, `PACKAGE_ROOT` and `WORKSPACE_ROOT`; no separate HSS package installation is needed to browse or prepare resources.

Origo installs this environment plugin as `System/env/hss-research`. New software
and HSS state use `System/software/hss`. An existing `System/env/hss` is reused
when the new location is absent; explicit resource-area mappings take precedence.
Knowledge, Skills, workflows and project material retain their resource-specific
locations. Keep the plugin name `hss-research` distinct from the mutable software
directory when importing or renaming it.

This path was exercised with the actual `Oxelra-AI/agentic-research-os` extension loader: repository package discovery, materialization, installation into the environment area, eight Skill declarations and an MCP catalogue call all completed. No private product code is included in HSS. The product's existing source importer is used; no new built-in catalogue tile is required.

## Complete research UI

Render `<hss-workbench></hss-workbench>` and connect it exactly like the picker. It adds research formulation, blueprint composition, project creation, task execution and manuscript assembly. The exported `httpTransport` reads streamed progress; the host can instead supply its own RPC transport. For a standalone process use `node packages/client/server.mjs --space /research`.

The workbench emits `hss-result` after completed requests; the module picker emits `hss-prepared`. Both retain data and execute through the supplied client. See [workbench](workbench.md) for concrete R, SQL and project-code contracts.
