import { HSSClient, type ResearchBrief, type Study } from "./client.js";
import { HSSPicker } from "./picker.js";

/** Research hosts provide their existing transport and model conversation. */
export class HSSWorkbench extends HTMLElement {
  private client?: HSSClient;
  private picker = new HSSPicker();
  private status = document.createElement("pre");
  private working = false;
  private tabs: HTMLButtonElement[] = [];
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
  }
  async connect(client: HSSClient): Promise<void> {
    this.client = client;
    this.render();
    await this.picker.connect(client);
  }
  private element<K extends keyof HTMLElementTagNameMap>(
    tag: K,
    text = "",
  ): HTMLElementTagNameMap[K] {
    const node = document.createElement(tag);
    node.textContent = text;
    return node;
  }
  private input(
    parent: HTMLElement,
    label: string,
    value = "",
    multiline = false,
  ): HTMLInputElement | HTMLTextAreaElement {
    const wrapper = this.element("label", label),
      input = multiline ? this.element("textarea") : this.element("input");
    input.value = value;
    input.setAttribute("aria-label", label);
    wrapper.append(input);
    parent.append(wrapper);
    return input;
  }
  private button(
    parent: HTMLElement,
    label: string,
    action: () => Promise<unknown>,
  ): void {
    const button = this.element("button", label);
    button.onclick = () => {
      void this.perform(action);
    };
    parent.append(button);
  }
  private async perform(action: () => Promise<unknown>): Promise<void> {
    if (this.working) return;
    this.working = true;
    this.status.textContent = "正在执行…";
    this.shadowRoot!.querySelectorAll("button").forEach(
      (b) => (b.disabled = true),
    );
    try {
      const result = await action();
      this.status.textContent = JSON.stringify(result, null, 2);
      this.dispatchEvent(
        new CustomEvent("hss-result", {
          detail: result,
          bubbles: true,
          composed: true,
        }),
      );
    } catch (error) {
      this.status.textContent =
        error instanceof Error ? error.message : String(error);
    } finally {
      this.working = false;
      this.shadowRoot!.querySelectorAll("button").forEach(
        (b) => (b.disabled = false),
      );
    }
  }
  private render(): void {
    const root = this.shadowRoot!;
    root.replaceChildren();
    this.tabs = [];
    const style = this.element("style");
    style.textContent =
      ":host{display:block}nav{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:22px}button{border:1px solid #b9c9bc;border-radius:7px;padding:11px 17px;background:#fff;color:#244b3b;font:inherit;cursor:pointer}button.active{background:#244b3b;color:white}button:disabled{opacity:.6;cursor:wait}section{background:#fff;border:1px solid #d6ddd3;border-radius:12px;padding:24px;margin-bottom:20px}section[hidden]{display:none}h2{font:25px Georgia;margin:0 0 12px}p{line-height:1.7;color:#51665a}label{display:block;margin:15px 0;color:#314b3c}input,textarea,select{display:block;box-sizing:border-box;width:100%;font:14px system-ui;line-height:1.5;padding:10px;border:1px solid #bdcdbf;border-radius:6px;margin-top:7px;color:#182d23;background:#fcfdfb}textarea{height:160px;resize:vertical;font:13px ui-monospace,monospace}footer{display:flex;flex-wrap:wrap;gap:10px;margin-top:18px}pre{white-space:pre-wrap;overflow:auto;max-height:450px;padding:20px;border-radius:10px;background:#e8eee5;font:13px ui-monospace,monospace;line-height:1.6}hss-picker{display:block;max-height:650px;overflow:auto}";
    root.append(style);
    const nav = this.element("nav");
    root.append(nav);
    const panels = [
      "选择研究环境",
      "形成研究方案",
      "执行研究任务",
      "组织论文成果",
    ].map((name, index) => {
      const panel = this.element("section");
      panel.hidden = index !== 0;
      const tab = this.element("button", `${index + 1} · ${name}`);
      tab.className = index === 0 ? "active" : "";
      tab.onclick = () => {
        panels.forEach((p, i) => {
          p.hidden = i !== index;
          this.tabs[i].className = i === index ? "active" : "";
        });
      };
      this.tabs.push(tab);
      nav.append(tab);
      root.append(panel);
      return panel;
    });
    panels[0].append(this.picker);
    const design = panels[1];
    design.append(
      this.element("h2", "从研究问题到研究方案"),
      this.element(
        "p",
        "填写现象、问题和现有材料。工作台返回需要明确的问题、候选方法和所选模块的研究路径；研究者与 Agent 在此基础上确定方案。",
      ),
    );
    const title = this.input(design, "研究标题"),
      phenomenon = this.input(design, "研究现象"),
      question = this.input(design, "研究问题");
    const goalLabel = this.element("label", "研究目标"),
      goal = this.element("select");
    for (const [value, label] of [
      ["interpretation", "意义与解释"],
      ["theory", "理论建构"],
      ["normative", "规范论证"],
      ["description", "描述"],
      ["association", "关联"],
      ["causal", "因果效应"],
      ["prediction", "预测"],
      ["experience", "经验与实践"],
      ["synthesis", "文献综合"],
    ])
      goal.add(new Option(label, value));
    goalLabel.append(goal);
    design.append(goalLabel);
    const scope = this.input(design, "研究范围"),
      material = this.input(design, "已有材料（每行一项）", "", true),
      project = this.input(design, "项目目录", "Projects/my-study");
    const brief = (): ResearchBrief => ({
      title: title.value,
      phenomenon: phenomenon.value,
      question: question.value,
      goal: goal.value,
      scope: scope.value,
      materials: material.value.split("\n").filter(Boolean),
    });
    const designActions = this.element("footer");
    design.append(designActions);
    this.button(designActions, "探索研究问题", () =>
      this.client!.explore(brief()),
    );
    this.button(designActions, "组合所选研究路径", () =>
      this.client!.blueprint(this.picker.selections, brief()),
    );
    this.button(designActions, "创建研究项目", () => {
      if (!title.value.trim()) throw new Error("请填写研究标题");
      return this.client!.project(project.value, title.value, {
        brief: brief(),
        selections: this.picker.selections,
        study: JSON.parse(study.value),
      });
    });
    const execution = panels[2];
    execution.append(
      this.element("h2", "数据、材料与分析"),
      this.element(
        "p",
        "任务 JSON 可组合内置分析、R 方法、SQL、Rust/C++ 文本工具，以及项目自己的 Python、R、JavaScript 程序。使用操作示例填写实际数据路径和变量。",
      ),
    );
    const operation = this.element("select");
    operation.setAttribute("aria-label", "研究操作");
    operation.add(new Option("选择操作并载入示例", ""));
    execution.append(operation);
    void this.client!.operations()
      .then((value) =>
        value.operations.forEach((op) =>
          operation.add(new Option(`${op.id} · ${op.name}`, op.id)),
        ),
      )
      .catch((error) => {
        this.status.textContent = String(error);
      });
    const study = this.input(
      execution,
      "研究任务 JSON",
      '{\n  "title": "Research study",\n  "tasks": []\n}',
      true,
    );
    study.style.height = "300px";
    operation.onchange = () => {
      if (operation.value)
        void this.perform(async () => {
          const op = await this.client!.describe(operation.value);
          const plan: Study = JSON.parse(study.value);
          plan.tasks.push(op.example);
          study.value = JSON.stringify(plan, null, 2);
          return op;
        });
    };
    const base = this.input(execution, "材料路径起点", "."),
      output = this.input(
        execution,
        "结果目录",
        "Projects/my-study/results/run-01",
      );
    const executionActions = this.element("footer");
    execution.append(executionActions);
    this.button(executionActions, "运行研究任务", () =>
      this.client!.run(JSON.parse(study.value), output.value, base.value),
    );
    this.button(executionActions, "查看已准备环境", () =>
      this.client!.installed(),
    );
    const writing = panels[3];
    writing.append(
      this.element("h2", "将论述与实际结果组织成文稿"),
      this.element(
        "p",
        "由研究者或宿主 Agent 提供正文与参考文献；tables 可引用真实 result.json 中的表。这里生成可继续用 Quarto 或 Pandoc 排版的 Markdown 文稿。",
      ),
    );
    const document = this.input(
      writing,
      "文稿 JSON",
      JSON.stringify(
        {
          title: "",
          abstract: "",
          sections: [
            { heading: "Introduction", text: "" },
            { heading: "Methods", text: "" },
            { heading: "Results", text: "" },
            { heading: "Discussion", text: "" },
          ],
          references: [],
        },
        null,
        2,
      ),
      true,
    );
    document.style.height = "330px";
    const writingBase = this.input(writing, "结果文件路径起点", "."),
      writingOutput = this.input(
        writing,
        "文稿输出目录",
        "Projects/my-study/writing/draft-01",
      );
    const writingActions = this.element("footer");
    writing.append(writingActions);
    this.button(writingActions, "生成文稿", () =>
      this.client!.manuscript(
        JSON.parse(document.value),
        writingOutput.value,
        writingBase.value,
      ),
    );
    this.status.setAttribute("aria-live", "polite");
    this.status.textContent =
      "选择研究需要的模块。软件和资源会按组合准备，浏览目录不会启动下载。";
    root.append(this.status);
  }
}
if (!customElements.get("hss-workbench"))
  customElements.define("hss-workbench", HSSWorkbench);
