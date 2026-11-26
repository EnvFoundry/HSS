export type Selection = string;
export interface Request {
  action: string;
  space?: string;
  [key: string]: unknown;
}
export interface Progress {
  component: string;
  step: string;
}
export type Transport = <T>(
  request: Request,
  progress?: (event: Progress) => void,
) => Promise<T>;
export interface Direction {
  id: string;
  name: string;
  modules: string[];
}
export interface Field {
  id: string;
  name: string;
  directions: Direction[];
  module_count: number;
}
export interface Bundle {
  id: string;
  name: string;
  modules: string[];
}
export interface Catalogue {
  fields: Field[];
  module_count: number;
  bundles: Bundle[];
}
export interface ResearchModule {
  id: string;
  name: string;
  summary: string;
  kind: string;
  components: string[];
  execution: string;
  backends?: Record<string, string[]>;
}
export interface Study {
  title?: string;
  question?: string;
  tasks: Record<string, unknown>[];
}
export interface StudyResult {
  output: string;
  tasks: string[];
  results: string;
  report: string;
}
export interface ResearchBrief {
  phenomenon?: string;
  question?: string;
  goal?: string;
  scope?: string;
  materials?: unknown[];
  [key: string]: unknown;
}
export interface Exploration {
  brief: ResearchBrief;
  next_questions: string[];
  design_questions: { field: string; question: string }[];
  candidate_routes: {
    module: string;
    purpose: string;
    inputs: string[];
    outputs: string[];
  }[];
}
export interface Blueprint {
  modules: {
    id: string;
    name: string;
    purpose: string;
    inputs: string[];
    outputs: string[];
  }[];
  operations: Record<string, unknown>[];
  design: Exploration;
  [key: string]: unknown;
}
export interface Operation {
  id: string;
  name: string;
  kind: string;
  scope: string;
  input_schema: Record<string, unknown>;
  example: Record<string, unknown>;
}
export interface Binding {
  command: string[];
  environment?: Record<string, string>;
  kind?: string;
  managed?: boolean;
  location?: string;
}
export interface Plan {
  modules: string[];
  actions: {
    component: string;
    kind: string;
    action: "install" | "reuse" | "connect";
    disk_bytes: number | null;
    download_bytes: number | null;
    destination: string;
  }[];
  assets: string[];
  resource_bytes: number;
  layout: Record<string, string>;
}
export interface Preparation {
  modules: string[];
  ready: { component: string; status: string }[];
  pending: { component: string; status: string }[];
  failed: { component: string; error: string }[];
  assets?: string[];
}
export class HSSClient {
  constructor(
    public transport: Transport,
    public space?: string,
  ) {}
  request<T>(
    action: string,
    args: Record<string, unknown> = {},
    progress?: (event: Progress) => void,
  ): Promise<T> {
    return this.transport<T>(
      { ...args, action, ...(this.space ? { space: this.space } : {}) },
      progress,
    );
  }
  browse(): Promise<Catalogue> {
    return this.request("browse");
  }
  search(query = "", field?: string): Promise<ResearchModule[]> {
    return this.request("search", { query, field });
  }
  plan(
    selections: Selection[],
    existing: Binding[] = [],
    backends: Record<string, string> = {},
  ): Promise<Plan> {
    return this.request("plan", { selections, existing, backends });
  }
  prepare(
    selections: Selection[],
    options: {
      software?: boolean;
      existing?: Binding[];
      backends?: Record<string, string>;
      options?: Record<string, unknown>;
    } = {},
    progress?: (event: Progress) => void,
  ): Promise<Preparation> {
    return this.request("prepare", { selections, ...options }, progress);
  }
  context(selections: Selection[]): Promise<unknown> {
    return this.request("context", { selections });
  }
  describe(operation: string): Promise<Operation> {
    return this.request("describe", { operation });
  }
  operations(): Promise<{
    operations: Omit<Operation, "example" | "input_schema">[];
  }> {
    return this.request("describe");
  }
  explore(brief: ResearchBrief): Promise<Exploration> {
    return this.request("explore", { brief });
  }
  blueprint(
    selections: Selection[],
    brief: ResearchBrief = {},
  ): Promise<Blueprint> {
    return this.request("blueprint", { selections, brief });
  }
  project(
    path: string,
    title: string,
    options: {
      brief?: ResearchBrief;
      selections?: Selection[];
      study?: Study;
    } = {},
  ): Promise<{ project: string; brief: string; study: string }> {
    return this.request("project", { path, title, ...options });
  }
  run(study: Study, output: string, base?: string): Promise<StudyResult> {
    return this.request("run", { study, output, base });
  }
  manuscript(
    document: Record<string, unknown>,
    output: string,
    base?: string,
  ): Promise<{ manuscript: string; sections: number; references: number }> {
    return this.request("manuscript", { document, output, base });
  }
  installed(): Promise<{
    modules: string[];
    bindings: Record<string, Binding>;
  }> {
    return this.request("installed");
  }
  connect(
    provider: string,
    query: string,
    options: Record<string, unknown> = {},
    limit = 10,
  ): Promise<unknown> {
    return this.request("connect", { provider, query, options, limit });
  }
  remove(selections: Selection[], prune = false): Promise<unknown> {
    return this.request("remove", { selections, prune });
  }
  uninstall(selections: Selection[]): Promise<unknown> {
    return this.request("uninstall", { selections });
  }
  export(output: string, selections: Selection[]): Promise<unknown> {
    return this.request("export", { output, selections });
  }
}

/** NDJSON streams preparation progress before the final response. */
export function httpTransport(url = "/api"): Transport {
  return async <T>(
    request: Request,
    progress?: (event: Progress) => void,
  ): Promise<T> => {
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    });
    if (!response.ok || !response.body) throw new Error(await response.text());
    const reader = response.body.getReader(),
      decoder = new TextDecoder();
    let buffer = "";
    let result: T | undefined;
    const consume = (line: string): void => {
      if (!line.trim()) return;
      const frame = JSON.parse(line);
      if (frame.type === "error") throw new Error(frame.message);
      if (frame.type === "progress") progress?.(frame.value);
      if (frame.type === "result") result = frame.value;
    };
    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop()!;
        for (const line of lines) consume(line);
      }
      buffer += decoder.decode();
      consume(buffer);
      if (result === undefined) throw new Error("HSS returned no result");
      return result;
    } finally {
      reader.releaseLock();
    }
  };
}
export class SelectionSet {
  private values = new Set<string>();
  set(module: string, selected: boolean): void {
    selected ? this.values.add(module) : this.values.delete(module);
  }
  addAll(modules: string[]): void {
    modules.forEach((m) => this.values.add(m));
  }
  has(module: string): boolean {
    return this.values.has(module);
  }
  clear(): void {
    this.values.clear();
  }
  list(): string[] {
    return [...this.values];
  }
}
