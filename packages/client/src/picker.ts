import {
  HSSClient,
  SelectionSet,
  type Catalogue,
  type ResearchModule,
} from "./client.js";

/** The host supplies the request transport; this element owns no job service. */
export class HSSPicker extends HTMLElement {
  private client?: HSSClient;
  private catalogue?: Catalogue;
  private modules: ResearchModule[] = [];
  private selected = new SelectionSet();
  private field = "";
  private direction = "";
  private query = "";
  private busy = false;
  private status = "";
  private software = false;
  private chosenBackends: Record<string, string> = {};
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
  }
  async connect(client: HSSClient): Promise<void> {
    this.client = client;
    [this.catalogue, this.modules] = await Promise.all([
      client.browse(),
      client.search(),
    ]);
    this.render();
  }
  get selections(): string[] {
    return this.selected.list();
  }
  get backends(): Record<string, string> {
    return Object.fromEntries(
      Object.entries(this.chosenBackends).filter(([key]) =>
        this.selected.has(key),
      ),
    );
  }
  private text(tag: string, value: string): HTMLElement {
    const node = document.createElement(tag);
    node.textContent = value;
    return node;
  }
  private button(label: string, action: () => void): HTMLButtonElement {
    const b = document.createElement("button");
    b.textContent = label;
    b.disabled = this.busy;
    b.onclick = action;
    return b;
  }
  private render(): void {
    const root = this.shadowRoot!;
    root.replaceChildren();
    const css = document.createElement("style");
    css.textContent =
      ":host{display:block;font:15px system-ui;color:#182a2b}header,nav,footer{display:flex;flex-wrap:wrap;gap:10px;margin:14px 0}select,input,button{font:inherit;padding:8px}button{cursor:pointer}article{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:10px}label.card{display:block;border:1px solid #ccd9d5;border-radius:9px;padding:12px}small{display:block;color:#49615c;margin:7px 0}pre{white-space:pre-wrap;background:#f0f5f3;padding:14px}h2{font-size:22px}";
    root.append(css);
    root.append(this.text("h2", "HSS · 人文与社会科学"));
    if (!this.catalogue) return;
    const nav = document.createElement("nav");
    const fieldSelect = document.createElement("select");
    fieldSelect.setAttribute("aria-label", "领域");
    fieldSelect.add(new Option("全部领域", ""));
    this.catalogue.fields.forEach((f) =>
      fieldSelect.add(new Option(f.name, f.id)),
    );
    fieldSelect.value = this.field;
    fieldSelect.disabled = this.busy;
    fieldSelect.onchange = () => {
      this.field = fieldSelect.value;
      this.direction = "";
      this.render();
    };
    nav.append(fieldSelect);
    const field = this.catalogue.fields.find((f) => f.id === this.field);
    const directions = document.createElement("select");
    directions.setAttribute("aria-label", "方向");
    directions.add(new Option("全部方向", ""));
    field?.directions.forEach((d) => directions.add(new Option(d.name, d.id)));
    directions.value = this.direction;
    directions.disabled = this.busy;
    directions.onchange = () => {
      this.direction = directions.value;
      this.render();
    };
    nav.append(directions);
    const search = document.createElement("input");
    search.placeholder = "搜索模块";
    search.setAttribute("aria-label", "搜索模块");
    search.value = this.query;
    search.onchange = () => {
      this.query = search.value;
      this.render();
    };
    nav.append(search);
    root.append(nav);
    const direction = field?.directions.find((d) => d.id === this.direction);
    const visibleIds = new Set(
      direction?.modules ??
        field?.directions.flatMap((d) => d.modules) ??
        this.modules.map((m) => m.id),
    );
    const query = this.query.toLocaleLowerCase();
    const visible = this.modules.filter(
      (m) =>
        visibleIds.has(m.id) &&
        [m.id, m.name, m.summary].join(" ").toLocaleLowerCase().includes(query),
    );
    const actions = document.createElement("header");
    actions.append(
      this.button("选择当前结果", () => {
        this.selected.addAll(visible.map((m) => m.id));
        this.render();
      }),
      this.button("清空选择", () => {
        this.selected.clear();
        this.render();
      }),
      this.text("span", `已选 ${this.selected.list().length} 个共享模块`),
    );
    root.append(actions);
    const grid = document.createElement("article");
    for (const m of visible) {
      const card = document.createElement("label");
      card.className = "card";
      const input = document.createElement("input");
      input.type = "checkbox";
      input.checked = this.selected.has(m.id);
      input.disabled = this.busy;
      input.onchange = () => {
        this.selected.set(m.id, input.checked);
        this.render();
      };
      card.append(
        input,
        document.createTextNode(m.name),
        this.text("small", m.summary),
        this.text(
          "small",
          m.execution + " · " + (m.components.join(", ") || "研究资源"),
        ),
      );
      if (m.backends) {
        const choice = document.createElement("select");
        choice.setAttribute("aria-label", m.name + "实现");
        choice.add(new Option("默认实现", ""));
        for (const name of Object.keys(m.backends))
          choice.add(new Option(name, name));
        choice.value = this.chosenBackends[m.id] || "";
        choice.disabled = this.busy;
        choice.onchange = () => {
          if (choice.value) this.chosenBackends[m.id] = choice.value;
          else delete this.chosenBackends[m.id];
        };
        card.append(choice);
      }
      grid.append(card);
    }
    root.append(grid);
    const footer = document.createElement("footer"),
      software = document.createElement("label"),
      flag = document.createElement("input");
    flag.type = "checkbox";
    flag.checked = this.software;
    flag.disabled = this.busy;
    flag.onchange = () => {
      this.software = flag.checked;
    };
    software.append(flag, document.createTextNode("同时准备所选软件"));
    footer.append(software);
    footer.append(
      this.button("查看安装计划", () => {
        void this.perform("plan");
      }),
      this.button("准备所选模块", () => {
        void this.perform("prepare");
      }),
    );
    root.append(
      footer,
      this.text(
        "pre",
        this.status ||
          "目录浏览不安装软件。选择领域、方向或具体模块后，查看计划或准备资源。",
      ),
    );
  }
  private async perform(action: "plan" | "prepare"): Promise<void> {
    if (!this.client || this.busy) return;
    this.busy = true;
    this.status =
      action === "plan" ? "正在计算所选模块的依赖…" : "正在准备所选模块…";
    this.render();
    try {
      const selections = this.selected.list();
      if (action === "plan") {
        const p = await this.client.plan(selections, [], this.backends);
        this.status =
          `${p.modules.length} 个模块，${p.assets.length} 个资源文件，${p.resource_bytes} 字节研究资源\n` +
          p.actions
            .map((a) => `${a.component}: ${a.action} → ${a.destination}`)
            .join("\n") +
          "\n软件下载量和安装大小由实际包解析决定。";
      } else {
        const p = await this.client.prepare(
          selections,
          { software: this.software, backends: this.backends },
          (event) => {
            this.status = `${event.component}: ${event.step}`;
            this.render();
          },
        );
        this.status =
          `已配置 ${p.modules.length} 个模块；软件就绪 ${p.ready.length}，待准备或连接 ${p.pending.length}，失败 ${p.failed.length}。\n` +
          p.failed.map((f) => `${f.component}: ${f.error}`).join("\n");
        this.dispatchEvent(
          new CustomEvent("hss-prepared", {
            detail: p,
            bubbles: true,
            composed: true,
          }),
        );
      }
    } catch (e) {
      this.status = e instanceof Error ? e.message : String(e);
      this.dispatchEvent(
        new CustomEvent("hss-error", {
          detail: this.status,
          bubbles: true,
          composed: true,
        }),
      );
    } finally {
      this.busy = false;
      this.render();
    }
  }
}
if (!customElements.get("hss-picker"))
  customElements.define("hss-picker", HSSPicker);
