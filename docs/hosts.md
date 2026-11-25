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

Actions: `browse`, `search`, `methods`, `resources`, `context`, `plan`, `prepare`, `installed`, `bind`, `remove`, `exec`, `explore`, `project`, `run`, `connect`, `index`, `lookup`, `export-r`, `export`. The implementation is in `src/hss/api.py`; examples show concrete payloads.

The host owns its task ID, process group, cancellation and account state. It records the returned interpreter command and resources with the rest of its environment registrations. HSS reuses SeedEnv interpreters when their packages meet the selected component requirements. This integration shape does not require either environment to import the other.

## MCP and plugins

```bash
hss export bundle:policy-study --output ./hss-plugin
```

The resulting package includes its stdio server, runtime, selected Skills, `mcp.json`, `plugin.json` and `configure.py`. Generic MCP clients use `mcp.json`. The plugin manifest follows EnvFoundry's `skills`, `environment.resources`, `mcpServers`, `${RESEARCH_PYTHON}` and `${PACKAGE_ROOT}` conventions. The host supplies the actual persistent space.

After moving the package, run `python configure.py` inside it. This writes the current interpreter and package paths into the MCP configuration. Set `HSS_RESEARCH_SPACE` before configuring if the host uses a nondefault space. Register this configuration through the host's existing MCP mechanism.

The server supports the MCP 2025-11-25 lifecycle with stdio tools, resources and prompts. It can negotiate the earlier supported protocol dates listed in its implementation. The interface has been exercised with the official Python MCP client. Newer protocol generations and each product's packaging rules must be integrated through that product's supported interface.

Tools cover catalogue browsing, context, research formulation, preparation, studies, data queries and R code export. Resources expose knowledge guides and workflow descriptions; prompts help develop a design and interpret findings. Tool errors return `isError` with the underlying cause.

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

There is no claim that a running Origo product or every Agent application has already loaded this package. This repository provides the integration implementation and protocol checks; product-specific registration belongs in the relevant host repository.
