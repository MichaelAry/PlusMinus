export interface NotebookCell {
  cell_type: "code" | "markdown";
  id: string;
  metadata: Record<string, unknown>;
  source: string | string[];
  execution_count?: number | null;
  outputs?: Array<Record<string, unknown>>;
  [key: string]: unknown;
}
export interface Notebook {
  cells: NotebookCell[];
  metadata: {
    kernelspec?: { display_name?: string; language?: string; name?: string };
    language_info?: { name?: string; file_extension?: string };
    plusminus?: { execution_mode?: string };
    [key: string]: unknown;
  };
  nbformat: 4;
  nbformat_minor: number;
  [key: string]: unknown;
}
export const sourceText = (text: string | string[]) => typeof text === "string" ? text : text.join("");
export function makeCell(kind: "code" | "markdown" = "code"): NotebookCell {
  const cell: NotebookCell = { id: crypto.randomUUID().slice(0,8), cell_type: kind, metadata: {}, source: "" };
  if (kind === "code") { cell.execution_count = null; cell.outputs = []; }
  return cell;
}
export function freshNotebook(): Notebook {
  return {
    cells: [makeCell()],
    metadata: {
      kernelspec: { display_name: "PlusMinus (isolated)", language: "plusminus", name: "plusminus-isolated" },
      language_info: { name: "plusminus", file_extension: ".pm" },
      plusminus: { execution_mode: "isolated" },
    },
    nbformat: 4, nbformat_minor: 5,
  };
}
export function validateNotebook(parsed: unknown): Notebook {
  if (!parsed || typeof parsed !== "object") throw new Error("Notebook must be an object");
  const n = parsed as Notebook;
  if (n.nbformat !== 4 || !Array.isArray(n.cells) || n.cells.length > 2000) throw new Error("Only Jupyter v4 notebooks with ≤2000 cells");
  if (n.metadata?.kernelspec?.name && !n.metadata.kernelspec.name.startsWith("plusminus")) throw new Error("Notebook kernel is not PlusMinus");
  if (n.metadata?.language_info?.name && n.metadata.language_info.name !== "plusminus") throw new Error("Notebook language is not PlusMinus");
  for (const cell of n.cells) {
    if (cell.cell_type !== "code" && cell.cell_type !== "markdown") throw new Error("Only code and Markdown cells can be edited");
    if (typeof cell.source !== "string" && !(Array.isArray(cell.source) && cell.source.every((s) => typeof s === "string"))) throw new Error("Invalid cell source");
    if (!cell.metadata || typeof cell.metadata !== "object") throw new Error("Invalid cell metadata");
    if (cell.cell_type === "code" && (!Array.isArray(cell.outputs) || !cell.outputs.every((o) => o && typeof o === "object"))) throw new Error("Invalid outputs");
  }
  return n;
}
export function encodeNotebook(n: Notebook): string {
  return JSON.stringify(validateNotebook(n), null, 2) + "\n";
}
export function withCell(n: Notebook, index: number, update: (c: NotebookCell) => NotebookCell): Notebook {
  return { ...n, cells: n.cells.map((c,i)=>i===index?update(c):c) };
}
export function streamOutput(content: string): Record<string, unknown> {
  return { output_type: "stream", name: "stdout", text: content };
}
export function errorOutput(content: string): Record<string, unknown> {
  return { output_type: "error", ename:"PlusMinusError",evalue:content,traceback:[content] };
}
