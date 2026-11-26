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
export type Transport = <T>(request: Request, progress?: (event: Progress) => void) => Promise<T>;
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
    design_questions: {
        field: string;
        question: string;
    }[];
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
    ready: {
        component: string;
        status: string;
    }[];
    pending: {
        component: string;
        status: string;
    }[];
    failed: {
        component: string;
        error: string;
    }[];
    assets?: string[];
}
export declare class HSSClient {
    transport: Transport;
    space?: string | undefined;
    constructor(transport: Transport, space?: string | undefined);
    request<T>(action: string, args?: Record<string, unknown>, progress?: (event: Progress) => void): Promise<T>;
    browse(): Promise<Catalogue>;
    search(query?: string, field?: string): Promise<ResearchModule[]>;
    plan(selections: Selection[], existing?: Binding[], backends?: Record<string, string>): Promise<Plan>;
    prepare(selections: Selection[], options?: {
        software?: boolean;
        existing?: Binding[];
        backends?: Record<string, string>;
        options?: Record<string, unknown>;
    }, progress?: (event: Progress) => void): Promise<Preparation>;
    context(selections: Selection[]): Promise<unknown>;
    describe(operation: string): Promise<Operation>;
    operations(): Promise<{
        operations: Omit<Operation, "example" | "input_schema">[];
    }>;
    explore(brief: ResearchBrief): Promise<Exploration>;
    blueprint(selections: Selection[], brief?: ResearchBrief): Promise<Blueprint>;
    project(path: string, title: string, options?: {
        brief?: ResearchBrief;
        selections?: Selection[];
        study?: Study;
    }): Promise<{
        project: string;
        brief: string;
        study: string;
    }>;
    run(study: Study, output: string, base?: string): Promise<StudyResult>;
    manuscript(document: Record<string, unknown>, output: string, base?: string): Promise<{
        manuscript: string;
        sections: number;
        references: number;
    }>;
    installed(): Promise<{
        modules: string[];
        bindings: Record<string, Binding>;
    }>;
    connect(provider: string, query: string, options?: Record<string, unknown>, limit?: number): Promise<unknown>;
    remove(selections: Selection[], prune?: boolean): Promise<unknown>;
    uninstall(selections: Selection[]): Promise<unknown>;
    export(output: string, selections: Selection[]): Promise<unknown>;
}
/** NDJSON streams preparation progress before the final response. */
export declare function httpTransport(url?: string): Transport;
export declare class SelectionSet {
    private values;
    set(module: string, selected: boolean): void;
    addAll(modules: string[]): void;
    has(module: string): boolean;
    clear(): void;
    list(): string[];
}
