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
  if (!n.metadata || typeof n.metadata !== "object" || Array.isArray(n.metadata)) n.metadata = {};
  const ids = new Set<string>();
  for (const cell of n.cells) {
    if (!cell || typeof cell !== "object") throw new Error("Notebook cell must be an object");
    if (cell.cell_type !== "code" && cell.cell_type !== "markdown") throw new Error("Only code and Markdown cells can be edited");
    if (typeof cell.source !== "string" && !(Array.isArray(cell.source) && cell.source.every((s) => typeof s === "string"))) throw new Error("Invalid cell source");
    // Jupyter notebook v4.0-v4.4 may have no cell ids. Studio 4 adds them at
    // validation time. Never use undefined as a key for executed cell results.
    if (typeof cell.id !== "string" || !cell.id.trim() || ids.has(cell.id)) {
      let next: string;
      do { next = crypto.randomUUID().replaceAll("-", "").slice(0, 8); } while (ids.has(next));
      cell.id = next;
    }
    ids.add(cell.id);
    if (!cell.metadata || typeof cell.metadata !== "object" || Array.isArray(cell.metadata)) cell.metadata = {};
    if (cell.cell_type === "code") {
      if (cell.execution_count === undefined) cell.execution_count = null;
      if (cell.outputs === undefined) cell.outputs = [];
      if (!Array.isArray(cell.outputs) || !cell.outputs.every(o => o && typeof o === "object" && !Array.isArray(o))) throw new Error("Invalid outputs");
      if (cell.execution_count !== null &&
        (!Number.isInteger(cell.execution_count) || (cell.execution_count as number) < 0))
        throw new Error("Invalid notebook execution_count");
    }
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

/** Recover unsaved edits when a Dockview notebook panel is closed/reopened.
 * This is process-local (no silent file writes or replacement of original .ipynb). */
export interface NotebookDraft {
  notebook: Notebook; digest: string; selected: number; stale: Record<string, boolean>;
}
const drafts = new Map<string, NotebookDraft>();
const keyOf = (workspace: string, path: string) => JSON.stringify([workspace,path]);
export function rememberNotebookDraft(workspace: string, path: string, draft: NotebookDraft) {
  if (workspace && path) drafts.set(keyOf(workspace,path),draft);
}
export function recoverNotebookDraft(workspace: string, path: string) {
  return drafts.get(keyOf(workspace,path)) ?? null;
}
export function latestNotebookDraft(workspace: string): {path:string;draft:NotebookDraft}|null {
  for (const [key,draft] of [...drafts].reverse()) {
    const [root,path]=JSON.parse(key) as [string,string];
    if (root===workspace) return {path,draft};
  }
  return null;
}
export function discardNotebookDraft(workspace:string,path:string) {
  drafts.delete(keyOf(workspace,path));
}
export function discardWorkspaceNotebooks(workspace:string) {
  for (const key of drafts.keys()) {
    const [root]=JSON.parse(key) as [string,string];
    if (root===workspace) drafts.delete(key);
  }
}
export function hasUnsavedNotebookDrafts(workspace?:string|null) {
  if (!workspace) return drafts.size>0;
  return latestNotebookDraft(workspace)!==null;
}
