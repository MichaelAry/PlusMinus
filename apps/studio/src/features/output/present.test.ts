import { describe, expect, it } from "vitest";
import { formatMetric, renderOutput } from "./present";
import type { RunnerReport } from "../../api/contracts";

const report: RunnerReport = {
  ok: true, output: "", result: "0", variables: "", bytecode: "", error: "",
  diagnostics: [], trace: [], trace_truncated: false,
  metrics: { compile_ms: 0, execute_ms: null, program_instructions: 0, executed_instructions: 0, opcode_hits: {} },
};

describe("faithful presentation of C++ runner data", () => {
  it("preserves empty stdout and numeric zero", () => {
    expect(renderOutput(report)).toContain("(No stdout produced)");
    expect(renderOutput(report)).toContain("Return value: 0");
  });
  it("does not replace unavailable measurements with zero", () => {
    expect(formatMetric(null, "ms")).toBe("not measured");
    expect(formatMetric(0, "ms")).toBe("0.00 ms");
  });
  it("preserves explicit runtime errors", () => {
    expect(renderOutput({ ...report, ok: false })).toContain("Execution failed");
  });
});
