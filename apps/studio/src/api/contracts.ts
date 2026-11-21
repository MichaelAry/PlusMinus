export type RunMode = "run" | "compile" | "profile" | "trace";
export type Metric = number | null;

export interface Diagnostic {
  severity: string;
  phase: string;
  message: string;
  line: number;
  column: number;
}

export interface TraceEvent {
  ip: number;
  opcode: string;
  thread: number;
  stack_depth: number;
}

export interface RunnerMetrics {
  compile_ms: Metric;
  execute_ms: Metric;
  program_instructions: Metric;
  executed_instructions: Metric;
  opcode_hits: Record<string, number>;
}

export interface RunnerReport {
  ok: boolean;
  output: string;
  result: string;
  variables: string;
  bytecode: string;
  error: string;
  diagnostics: Diagnostic[];
  trace: TraceEvent[];
  trace_truncated: boolean;
  metrics: RunnerMetrics;
}

export interface RunResponse {
  job_id: string;
  report: RunnerReport;
  exit_code: number | null;
  wall_ms: number;
}

export interface Document {
  path: string;
  source: string;
  digest: string;
}

export interface TreeEntry {
  path: string;
  name: string;
  directory: boolean;
  depth: number;
}
