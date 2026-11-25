import { HSSClient } from "./client.js";
/** Research hosts provide their existing transport and model conversation. */
export declare class HSSWorkbench extends HTMLElement {
    private client?;
    private picker;
    private status;
    private working;
    private tabs;
    constructor();
    connect(client: HSSClient): Promise<void>;
    private element;
    private input;
    private button;
    private perform;
    private render;
}
