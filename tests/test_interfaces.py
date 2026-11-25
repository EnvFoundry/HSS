import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from hss.api import request
from hss.connectors import search
from hss.hosts import export
from hss.manager import Manager
from hss.mcp import dispatch

ROOT = Path(__file__).resolve().parents[1]


class InterfaceTests(unittest.TestCase):
    def test_json_cli_keeps_stdout_parseable(self):
        result = subprocess.run(
            [sys.executable, "-m", "hss", "request", "-"],
            input=json.dumps({"action": "search", "query": "文本"}),
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        )
        self.assertTrue(json.loads(result.stdout))

    def test_exported_server_survives_relocation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            export(Manager(root / "space"), root / "package", ["argument-analysis"])
            (root / "package").rename(root / "moved")
            subprocess.run(
                [sys.executable, str(root / "moved/configure.py")],
                capture_output=True,
                check=True,
            )
            conf = json.loads((root / "moved/mcp.json").read_text(encoding="utf-8"))[
                "mcpServers"
            ]["hss"]
            r = subprocess.run(
                [conf["command"], *conf["args"]],
                input=json.dumps(
                    {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
                )
                + "\n",
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=True,
            )
            self.assertGreater(len(json.loads(r.stdout)["result"]["tools"]), 10)
            self.assertTrue((root / "moved/skills/hss-theory/SKILL.md").exists())

    def test_mcp_tool_errors_are_tool_results(self):
        result = dispatch(
            "tools/call",
            {"name": "hss_context", "arguments": {"selections": ["missing"]}},
        )
        self.assertTrue(result["isError"])

    def test_local_index_respects_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            indexed = request(
                {"action": "index", "space": tmp, "selections": ["argument-analysis"]}
            )
            self.assertGreater(indexed["documents"], 0)
            found = request({"action": "lookup", "space": tmp, "query": "论证"})
            self.assertTrue(found["results"])
            self.assertEqual(
                request({"action": "lookup", "space": tmp, "query": "random_forest"})[
                    "results"
                ],
                [],
            )

    def test_crossref_maps_actual_metadata(self):
        fixture = {
            "message": {
                "items": [
                    {
                        "DOI": "10.test/example",
                        "title": ["Example"],
                        "author": [{"given": "A", "family": "Researcher"}],
                        "issued": {"date-parts": [[2025]]},
                        "URL": "https://example.org",
                    }
                ],
                "total-results": 1,
            }
        }
        with patch("hss.connectors.fetch", return_value=fixture) as call:
            result = search("crossref", "community education", 5)
        self.assertEqual(result["records"][0]["authors"], ["A Researcher"])
        self.assertIn("rows=5", call.call_args.args[0])

    def test_official_mcp_client(self):
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
        except ImportError:
            self.skipTest("Install the optional mcp test dependency")

        async def connect():
            env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
            async with stdio_client(
                StdioServerParameters(
                    command=sys.executable, args=["-m", "hss", "serve"], env=env
                )
            ) as (reader, writer):
                async with ClientSession(reader, writer) as session:
                    initialized = await session.initialize()
                    self.assertEqual(
                        initialized.model_dump(by_alias=True)["serverInfo"]["name"],
                        "hss",
                    )
                    tools = await session.list_tools()
                    self.assertIn("hss_run", [t.name for t in tools.tools])
                    result = await session.call_tool("hss_browse", {})
                    self.assertFalse(result.model_dump(by_alias=True)["isError"])
                    self.assertIn("fields", json.loads(result.content[0].text))
                    resources = await session.list_resources()
                    self.assertTrue(resources.resources)
                    guide = await session.read_resource("hss://knowledge/research.md")
                    self.assertTrue(guide.contents[0].text)
                    prompt = await session.get_prompt(
                        "hss_design", arguments={"phenomenon": "Urban mobility"}
                    )
                    self.assertIn("Urban mobility", prompt.messages[0].content.text)

        asyncio.run(connect())


if __name__ == "__main__":
    unittest.main()
