import { HSSClient } from './client.js';
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
    constructor();
    connect(client: HSSClient): Promise<void>;
    get selections(): string[];
    private text;
    private button;
    private render;
    private perform;
}
