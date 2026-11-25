export class HSSClient {
    transport;
    space;
    constructor(transport, space) {
        this.transport = transport;
        this.space = space;
    }
    request(action, args = {}, progress) {
        return this.transport({ ...args, action, ...(this.space ? { space: this.space } : {}) }, progress);
    }
    browse() { return this.request("browse"); }
    search(query = "", field) { return this.request("search", { query, field }); }
    plan(selections, existing = []) { return this.request("plan", { selections, existing }); }
    prepare(selections, options = {}, progress) {
        return this.request("prepare", { selections, ...options }, progress);
    }
    context(selections) { return this.request("context", { selections }); }
}
export class SelectionSet {
    values = new Set();
    set(module, selected) { selected ? this.values.add(module) : this.values.delete(module); }
    addAll(modules) { modules.forEach(m => this.values.add(m)); }
    has(module) { return this.values.has(module); }
    clear() { this.values.clear(); }
    list() { return [...this.values]; }
}
