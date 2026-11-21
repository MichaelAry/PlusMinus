import { describe, expect, it } from "vitest";
import { benchmarkStats } from "./parity";
describe("benchmark statistics",()=>{
  it("computes actual sample aggregates",()=>{
    expect(benchmarkStats([3,1,2])?.median).toBe(2);
    expect(benchmarkStats([3,1,2])?.mean).toBe(2);
    expect(benchmarkStats([])).toBeNull();
  });
});
