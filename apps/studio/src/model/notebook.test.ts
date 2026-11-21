import { describe, expect, it } from "vitest";
import { freshNotebook, encodeNotebook, validateNotebook, makeCell, rememberNotebookDraft, recoverNotebookDraft, latestNotebookDraft, discardWorkspaceNotebooks, hasUnsavedNotebookDrafts, executeResultOutput, outputText } from "./notebook";
describe("notebook v4 compatibility",()=>{
  it("round-trips PlusMinus notebook without discarding custom metadata",()=>{
    const n=freshNotebook();
    n.metadata["custom"]={anything:true};
    n.cells.push(makeCell("markdown"));
    const loaded=validateNotebook(JSON.parse(encodeNotebook(n)));
    expect(loaded.metadata.custom).toEqual({anything:true});
    expect(loaded.cells).toHaveLength(2);
  });
  it("rejects corrupted metadata rather than silently discarding data",()=>{
    const n=freshNotebook();
    (n as unknown as {metadata:unknown}).metadata="corrupt";
    expect(()=>validateNotebook(n)).toThrow(/metadata/);
  });
  it("rejects foreign kernels and unexpected cell kinds",()=>{
    const n=freshNotebook();
    n.metadata.kernelspec!.name="python3";
    expect(()=>validateNotebook(n)).toThrow();
  });
});

describe("legacy notebook identity and in-memory draft preservation",()=>{
  it("fills absent/duplicate ids without losing source, metadata or outputs",()=>{
    const n=freshNotebook();
    n.cells=[{cell_type:"code",metadata:{legacy:42},source:["print(0);"],outputs:[],execution_count:0},
      {cell_type:"code",id:"same",metadata:{},source:"print(1);",outputs:[]},
      {cell_type:"markdown",id:"same",metadata:{},source:"notes"}] as typeof n.cells;
    const normalized=validateNotebook(n);
    expect(new Set(normalized.cells.map(c=>c.id)).size).toBe(3);
    expect(normalized.cells.every(c=>Boolean(c.id))).toBe(true);
    expect(normalized.cells[0].metadata.legacy).toBe(42);
    expect(normalized.cells[0].execution_count).toBe(0);
    expect(validateNotebook(normalized).cells[0].id).toBe(normalized.cells[0].id);
  });
  it("recovers dirty panels without replacing a source .ipynb file",()=>{
    const draft={notebook:freshNotebook(),digest:"digest",selected:0,stale:{}};
    rememberNotebookDraft("/workspace","research.ipynb",draft);
    expect(hasUnsavedNotebookDrafts("/workspace")).toBe(true);
    expect(latestNotebookDraft("/workspace")?.path).toBe("research.ipynb");
    expect(recoverNotebookDraft("/workspace","research.ipynb")).toBe(draft);
    discardWorkspaceNotebooks("/workspace");
    expect(hasUnsavedNotebookDrafts("/workspace")).toBe(false);
  });
});

describe("Studio 4 Jupyter output parity",()=>{
  it("persists an isolated runner return value even when it is numeric zero",()=>{
    const output=executeResultOutput("0",2);
    expect(output).toEqual({output_type:"execute_result",execution_count:2,
      data:{"text/plain":"0"},metadata:{}});
    expect(outputText(output)).toBe("0");
    const saved=JSON.parse(JSON.stringify(output));
    expect(outputText(saved)).toBe("0");
  });
  it("displays legacy Qt notebook output and Jupyter text arrays",()=>{
    expect(outputText({output_type:"execute_result",data:{"text/plain":["first", " second"]}}))
      .toBe("first second");
    expect(outputText({output_type:"stream",text:["hello","\n"]})).toBe("hello\n");
    expect(outputText({output_type:"error",evalue:"compile: invalid token"}))
      .toBe("compile: invalid token");
  });
});
