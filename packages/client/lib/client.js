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
    browse() {
        return this.request("browse");
    }
    search(query = "", field) {
        return this.request("search", { query, field });
    }
    plan(selections, existing = [], backends = {}) {
        return this.request("plan", { selections, existing, backends });
    }
    prepare(selections, options = {}, progress) {
        return this.request("prepare", { selections, ...options }, progress);
    }
    context(selections) {
        return this.request("context", { selections });
    }
    describe(operation) {
        return this.request("describe", { operation });
    }
    operations() {
        return this.request("describe");
    }
    explore(brief) {
        return this.request("explore", { brief });
    }
    blueprint(selections, brief = {}) {
        return this.request("blueprint", { selections, brief });
    }
    project(path, title, options = {}) {
        return this.request("project", { path, title, ...options });
    }
    run(study, output, base) {
        return this.request("run", { study, output, base });
    }
    manuscript(document, output, base) {
        return this.request("manuscript", { document, output, base });
    }
    installed() {
        return this.request("installed");
    }
    connect(provider, query, options = {}, limit = 10) {
        return this.request("connect", { provider, query, options, limit });
    }
    remove(selections, prune = false) {
        return this.request("remove", { selections, prune });
    }
    export(output, selections) {
        return this.request("export", { output, selections });
    }
}
/** NDJSON streams preparation progress before the final response. */
export function httpTransport(url = "/api") {
    return async (request, progress) => {
        const response = await fetch(url, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(request),
        });
        if (!response.ok || !response.body)
            throw new Error(await response.text());
        const reader = response.body.getReader(), decoder = new TextDecoder();
        let buffer = "";
        let result;
        const consume = (line) => {
            if (!line.trim())
                return;
            const frame = JSON.parse(line);
            if (frame.type === "error")
                throw new Error(frame.message);
            if (frame.type === "progress")
                progress?.(frame.value);
            if (frame.type === "result")
                result = frame.value;
        };
        try {
            while (true) {
                const { done, value } = await reader.read();
                if (done)
                    break;
                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split("\n");
                buffer = lines.pop();
                for (const line of lines)
                    consume(line);
            }
            buffer += decoder.decode();
            consume(buffer);
            if (result === undefined)
                throw new Error("HSS returned no result");
            return result;
        }
        finally {
            reader.releaseLock();
        }
    };
}
export class SelectionSet {
    values = new Set();
    set(module, selected) {
        selected ? this.values.add(module) : this.values.delete(module);
    }
    addAll(modules) {
        modules.forEach((m) => this.values.add(m));
    }
    has(module) {
        return this.values.has(module);
    }
    clear() {
        this.values.clear();
    }
    list() {
        return [...this.values];
    }
}
