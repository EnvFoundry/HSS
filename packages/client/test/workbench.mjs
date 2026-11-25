import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { HSSClient, httpTransport } from "../lib/client.js";
import { createWorkbench } from "../server.mjs";

test("Workbench HTTP transport runs a project and writes actual SQL results", async () => {
  const space = await mkdtemp(join(tmpdir(), "hss-web-"));
  const server = createWorkbench({
    space,
    python: process.env.PYTHON || "python",
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const url = "http://127.0.0.1:" + server.address().port;
  try {
    const page = await fetch(url);
    assert.equal(page.status, 200);
    assert.match(await page.text(), /hss-workbench/);
    const client = new HSSClient(httpTransport(url + "/api"));
    const catalogue = await client.browse();
    assert.equal(catalogue.module_count, 91);
    const plan = await client.plan(["corpus-assembly"], [], {
      "corpus-assembly": "rust",
    });
    assert.equal(plan.actions[0].component, "native-corpus");
    const project = await client.project("Projects/study", "A study", {
      selections: ["data-linkage"],
      brief: { question: "How do groups differ?" },
    });
    assert.equal(project.project, join(space, "Projects/study"));
    await writeFile(
      join(project.project, "data.csv"),
      "group_name,value\nA,2\nA,4\nB,8\n",
    );
    const result = await client.run(
      {
        tasks: [
          {
            id: "mean",
            operation: "sql",
            datasets: [
              { name: "d", path: "data.csv", types: { value: "REAL" } },
            ],
            queries: [
              {
                name: "groups",
                sql: "SELECT group_name, AVG(value) AS mean FROM d GROUP BY group_name",
              },
            ],
          },
        ],
      },
      "Projects/study/results/run",
      "Projects/study",
    );
    const results = JSON.parse(await readFile(result.results, "utf8"));
    assert.deepEqual(results.mean.tables.groups, [
      { group_name: "A", mean: 3 },
      { group_name: "B", mean: 8 },
    ]);
    await assert.rejects(
      () => client.describe("nonexistent"),
      /Unknown operation/,
    );
  } finally {
    await new Promise((resolve) => server.close(resolve));
    await rm(space, { recursive: true, force: true });
  }
});

test("HTTP progress parser handles records split across chunks", async () => {
  const original = globalThis.fetch;
  const encoder = new TextEncoder(),
    progress = [];
  globalThis.fetch = async () =>
    new Response(
      new ReadableStream({
        start(controller) {
          for (const value of [
            '{"type":"pro',
            'gress","value":{"component":"R","step":"install"}}\n{"type":"result",',
            '"value":{"ready":true}}\n',
          ])
            controller.enqueue(encoder.encode(value));
          controller.close();
        },
      }),
    );
  try {
    const value = await httpTransport()({ action: "prepare" }, (event) =>
      progress.push(event),
    );
    assert.deepEqual(value, { ready: true });
    assert.equal(progress[0].component, "R");
  } finally {
    globalThis.fetch = original;
  }
});
