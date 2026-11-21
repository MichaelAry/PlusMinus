import {describe,expect,it} from "vitest";
import {diagnose} from "./sourceDiagnostics";
describe("lexical editing hints",()=>{
  it("ignores bracket symbols in strings and comments",()=>{
    expect(diagnose('print(")"); // }\n x = 1;')).toHaveLength(0);
  });
  it("locates mismatched and unclosed brackets",()=>{
    const issues=diagnose('if (x] {\n');
    expect(issues.map(p=>p.code)).toContain("PM1002");
    expect(issues.map(p=>p.code)).toContain("PM1001");
  });
  it("warns when go lacks sync",()=>{
    expect(diagnose('go compute();').some(p=>p.code==="PM3001")).toBe(true);
    expect(diagnose('go compute(); sync;').some(p=>p.code==="PM3001")).toBe(false);
  });
});
