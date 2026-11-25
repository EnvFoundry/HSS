export type Selection = string;
export interface Request { action: string; space?: string; [key: string]: unknown }
export interface Progress { component: string; step: string }
export type Transport = <T>(request: Request, progress?: (event: Progress) => void) => Promise<T>;
export interface Direction { id: string; name: string; modules: string[] }
export interface Field { id: string; name: string; directions: Direction[]; module_count: number }
export interface Bundle { id: string; name: string; modules: string[] }
export interface Catalogue { fields: Field[]; module_count: number; bundles: Bundle[] }
export interface ResearchModule { id: string; name: string; summary: string; kind: string; components: string[]; execution: string }
export interface Binding { command: string[]; environment?: Record<string, string>; kind?: string; managed?: boolean; location?: string }
export interface Plan { modules: string[]; actions: { component: string; kind: string; action: "install" | "reuse" | "connect"; disk_bytes: number | null; download_bytes: number | null; destination: string }[]; assets: string[]; resource_bytes: number; layout: Record<string,string> }
export interface Preparation { modules: string[]; ready: { component: string; status: string }[]; pending: { component: string; status: string }[]; failed: { component: string; error: string }[]; assets?: string[] }
export class HSSClient {
  constructor(public transport: Transport, public space?: string) {}
  request<T>(action: string, args: Record<string,unknown> = {}, progress?: (event: Progress) => void): Promise<T> {
    return this.transport<T>({...args, action, ...(this.space ? {space:this.space} : {})}, progress);
  }
  browse(): Promise<Catalogue> { return this.request("browse"); }
  search(query = "", field?: string): Promise<ResearchModule[]> { return this.request("search", {query, field}); }
  plan(selections: Selection[], existing: Binding[] = []): Promise<Plan> { return this.request("plan", {selections,existing}); }
  prepare(selections: Selection[], options: {software?: boolean; existing?: Binding[]; options?: Record<string,unknown>} = {}, progress?: (event: Progress) => void): Promise<Preparation> {
    return this.request("prepare", {selections,...options}, progress);
  }
  context(selections: Selection[]): Promise<unknown> { return this.request("context", {selections}); }
}
export class SelectionSet {
  private values = new Set<string>();
  set(module: string, selected: boolean): void { selected ? this.values.add(module) : this.values.delete(module); }
  addAll(modules: string[]): void { modules.forEach(m => this.values.add(m)); }
  has(module: string): boolean { return this.values.has(module); }
  clear(): void { this.values.clear(); }
  list(): string[] { return [...this.values]; }
}
