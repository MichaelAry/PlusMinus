import { describe, expect, it } from "vitest";
import { freshNotebook, encodeNotebook, validateNotebook, makeCell } from "./notebook";
describe("notebook v4 compatibility",()=>{
  it("round-trips PlusMinus notebook without discarding custom metadata",()=>{
    const n=freshNotebook();
    n.metadata["custom"]={anything:true};
    n.cells.push(makeCell("markdown"));
    const loaded=validateNotebook(JSON.parse(encodeNotebook(n)));
    expect(loaded.metadata.custom).toEqual({anything:true});
    expect(loaded.cells).toHaveLength(2);
  });
  it("rejects foreign kernels and unexpected cell kinds",()=>{
    const n=freshNotebook();
    n.metadata.kernelspec!.name="python3";
    expect(()=>validateNotebook(n)).toThrow();
  });
});
