import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import { resolve } from "node:path";
import { JSDOM } from "jsdom";
import { HSSClient } from "../lib/client.js";
import { pythonTransport } from "../node.mjs";

async function until(check) {
  for (let i = 0; i < 200; i++) {
    if (check()) return;
    await new Promise((resolve) => setTimeout(resolve, 10));
  }
  throw new Error("Interface did not reach expected state");
}

test("Research interface keeps selections and connects actual module and operation data", async () => {
  const dom = new JSDOM("<!doctype html><body></body>", {
    url: "http://localhost",
  });
  for (const name of [
    "HTMLElement",
    "document",
    "customElements",
    "CustomEvent",
    "Option",
  ])
    globalThis[name] = dom.window[name];
  try {
    await import("../lib/workbench.js");
    const rootPath = fileURLToPath(new URL("../../../", import.meta.url));
    const client = new HSSClient(
      pythonTransport({
        python: process.env.PYTHON || "python",
        pythonPath: resolve(rootPath, "src"),
      }),
    );
    const workbench = document.createElement("hss-workbench");
    document.body.append(workbench);
    await workbench.connect(client);
    const root = workbench.shadowRoot,
      picker = root.querySelector("hss-picker"),
      pickerRoot = picker.shadowRoot;
    const field = pickerRoot.querySelector('select[aria-label="领域"]');
    field.value = "history";
    field.dispatchEvent(new dom.window.Event("change"));
    [...pickerRoot.querySelectorAll("button")]
      .find((b) => b.textContent === "选择当前结果")
      .click();
    assert.ok(picker.selections.includes("text-collation"));
    const change = root.querySelectorAll("nav button")[1];
    change.click();
    assert.equal(root.querySelectorAll("section")[1].hidden, false);
    root.querySelector('[aria-label="研究问题"]').value =
      "文本如何描述历史事件？";
    [...root.querySelectorAll("button")]
      .find((b) => b.textContent === "组合所选研究路径")
      .click();
    await until(() =>
      root.querySelector("pre").textContent.includes('"design_questions"'),
    );
    const blueprint = JSON.parse(root.querySelector("pre").textContent);
    assert.ok(blueprint.modules.some((m) => m.id === "text-collation"));
    root.querySelectorAll("nav button")[2].click();
    const operation = root.querySelector('[aria-label="研究操作"]');
    await until(() => operation.options.length > 30);
    operation.value = "sql";
    operation.dispatchEvent(new dom.window.Event("change"));
    await until(() =>
      root
        .querySelector('[aria-label="研究任务 JSON"]')
        .value.includes('"operation": "sql"'),
    );
    const study = JSON.parse(
      root.querySelector('[aria-label="研究任务 JSON"]').value,
    );
    assert.equal(study.tasks.length, 1);
    assert.ok(picker.selections.includes("text-collation"));
  } finally {
    dom.window.close();
  }
});
