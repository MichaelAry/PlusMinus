import { describe, expect, it } from "vitest";
import { completionCandidates, plusminusKeywords } from "./completion";

describe("PlusMinus Monaco completion",()=>{
  it("provides real language keywords and project identifiers",()=>{
    expect(plusminusKeywords).toContain("proc");
    const found=completionCandidates("func sample() { totalValue = 1; }","to");
    expect(found).toContain("totalValue");
    expect(completionCandidates("","pri")).toContain("print");
  });
  it("ignores comments and keeps suggestions bounded",()=>{
    expect(completionCandidates("// fakeNamedValue\nrealNamedValue=1;","fake")).toEqual([]);
    expect(completionCandidates("realNamedValue=1;","real",0)).toEqual([]);
    expect(completionCandidates("abc aba abb abd", "a", 2)).toHaveLength(2);
  });
});
