import type { RunnerReport } from "../../api/contracts";

export function formatMetric(value: number | null | undefined, suffix = ""): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "not measured";
  return suffix ? value.toFixed(2) + " " + suffix : String(value);
}

export function renderOutput(report: RunnerReport): string {
  const lines: string[] = [report.output || "(No stdout produced)"];
  if (report.result !== "") lines.push("Return value: " + report.result);
  if (!report.ok) lines.push("Execution failed — see Diagnostics.");
  return lines.join("\n");
}
