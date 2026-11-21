import {describe,it,expect} from "vitest";
import {analyzeSource} from "./sourceMetrics";
describe("Studio4-compatible source metrics",()=>{
  it("ignores string/comment tokens and counts expressions",()=>{
    const m=analyzeSource("func f(){ // if while\n print('if'); x = 1; if(x>0){go f();}}\n");
    expect(m.functions).toBe(1);
    expect(m.branches).toBe(1);
    expect(m.loops).toBe(0);
    expect(m.go_calls).toBe(1);
    expect(m.variables).toBe(1);
    expect(m.warnings.some(w=>w.includes("sync"))).toBe(true);
    expect(m.method).toContain("Lexical");
  });
  it("counts comments and complexity decisions",()=>{
    const m=analyzeSource("/* test */ if(x && y) { while(0){} }\n");
    expect(m.comments).toBe(1);
    expect(m.complexity_estimate).toBe(4);
  });
});
