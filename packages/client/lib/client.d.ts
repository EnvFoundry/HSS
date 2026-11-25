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
    plan(selections: Selection[], existing?: Binding[]): Promise<Plan>;
    prepare(selections: Selection[], options?: {
        software?: boolean;
        existing?: Binding[];
        options?: Record<string, unknown>;
    }, progress?: (event: Progress) => void): Promise<Preparation>;
    context(selections: Selection[]): Promise<unknown>;
}
export declare class SelectionSet {
    private values;
    set(module: string, selected: boolean): void;
    addAll(modules: string[]): void;
    has(module: string): boolean;
    clear(): void;
    list(): string[];
}
