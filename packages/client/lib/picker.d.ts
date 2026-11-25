import { HSSClient } from "./client.js";
/** The host supplies the request transport; this element owns no job service. */
export declare class HSSPicker extends HTMLElement {
    private client?;
    private catalogue?;
    private modules;
    private selected;
    private field;
    private direction;
    private query;
    private busy;
    private status;
    private software;
    private chosenBackends;
    constructor();
    connect(client: HSSClient): Promise<void>;
    get selections(): string[];
    get backends(): Record<string, string>;
    private text;
    private button;
    private render;
    private perform;
}
