import { describe, expect, it } from "vitest";
import { bytecodeGraph, callGraph } from "./graphs";

describe("compiler visualization parity",()=>{
  it("preserves Jz target and fallthrough",()=>{
    const g=bytecodeGraph("0 Push 1\n1 Jz -> 3\n2 Print\n3 Halt");
    expect(g.edges).toContainEqual({source:"1",target:"3",label:"Jz"});
    expect(g.edges).toContainEqual({source:"1",target:"2",label:"fallthrough"});
  });
  it("masks comments and strings before call graph",()=>{
    const g=callGraph('func alpha(){ print("beta()"); }\n// beta()\nalpha();');
    expect(g.nodes.map(x=>x.id)).toContain("alpha");
    expect(g.edges).toContainEqual({source:"__main__",target:"alpha",label:"call"});
  });
});
