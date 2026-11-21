import { Channel, invoke } from "@tauri-apps/api/core";
import type { RunResponse } from "./contracts";

export interface NativeCase {
  id: string;
  group: string;
  source: string;
  slow: boolean;
}
export type NativeStatus = "PASS" | "FAIL" | "ERROR" | "TIMEOUT" | "CANCELED";
export interface NativeResult extends NativeCase {
  status: NativeStatus;
  error: string;
  elapsed_ms: number;
  test_ms: number | null;
  cpu_ms: number | null;
  peak_rss_mb: number | null;
}
export type NativeEvent =
  | { type: "started"; job_id: string; total: number }
  | { type: "test_finished"; job_id: string; result: NativeResult; done: number; total: number }
  | { type: "completed"; job_id: string; session_id: number | null; passed: number; failed: number; canceled: boolean; error: string | null };

export interface Session {
  id: number;
  timestamp: string;
  label: string;
  git_sha: string;
  source_hash: string;
  dirty: boolean;
  platform: string;
  total_ms: number;
}
export interface HistoryRow {
  id: number;
  created: string;
  category: string;
  label: string;
  ok: boolean;
  elapsed_ms: number;
  source_hash: string;
  details: unknown;
}
export interface HistoryOverview {
  counts: { runs: number; native_sessions: number; native_results: number; native_baseline: number };
  baseline: number | null;
  v5_path: string;
}
export interface SessionDiff {
  introduced: string[];
  fixed: string[];
  remaining_failures: string[];
  added: string[];
  missing: string[];
  performance: Record<string, { before_ms: number; after_ms: number; delta_ms: number; delta_pct: number | null; metric: "body" | "wall" }>;
  baseline: Session;
  current: Session;
  comparable_platform: boolean;
  same_source: boolean;
}
export interface ExternalDocument { path: string; source: string; digest: string }
export interface SourceTarget { keyword: string; path: string; anchor: string; line: number; label: string }
export interface GitSummary { available: boolean; branch: string; sha: string; dirty: boolean; changes: string; diff: string; commits: string; error: string }

export interface UserCase {
  name:string;source:string;kind:"output"|"result"|"bytecode_contains"|"error_contains";
  expected:string;mode:"run"|"compile"|"profile"|"trace";
  expect_ok:boolean;timeout:number;
}
export interface UserBundle {cases:UserCase[];revision:string}
export const parity = {
  userTests:()=>invoke<UserBundle>("list_user_tests"),
  saveUserTests:(cases:UserCase[],expected:string)=>invoke<UserBundle>("save_user_tests",{cases,expected}),
  importUserTests:(expected:string)=>invoke<UserBundle>("import_user_tests",{expected}),
  exportUserTests:()=>invoke<string>("export_user_tests"),
  listNative: () => invoke<NativeCase[]>("list_native_tests"),
  runSuite: async (jobId: string, testIds: string[], label: string, onProgress: (event: NativeEvent) => void) => {
    const onEvent = new Channel<NativeEvent>();
    onEvent.onmessage = onProgress;
    return invoke<string>("start_native_suite", { jobId, testIds, label, onEvent });
  },
  cancel: (jobId: string) => invoke<boolean>("cancel_run", { jobId }),
  overview: () => invoke<HistoryOverview>("history_overview"),
  runs: (limit = 150) => invoke<HistoryRow[]>("recent_runs", { limit }),
  sessions: (limit = 50) => invoke<Session[]>("native_sessions", { limit }),
  results: (sessionId: number) => invoke<NativeResult[]>("session_results", { sessionId }),
  setBaseline: (sessionId: number) => invoke<void>("set_native_baseline", { sessionId }),
  compare: (baseId: number, currentId: number) => invoke<SessionDiff>("compare_native_sessions", { baseId, currentId }),
  openDocument: (path: string) => invoke<ExternalDocument>("open_workspace_document", { path }),
  saveDocument: (path: string, source: string, expected: string) =>
    invoke<ExternalDocument>("save_workspace_document", { path, source, expected }),
  createNotebook: (path: string, source: string) => invoke<ExternalDocument>("create_notebook", { path, source }),
  git: () => invoke<GitSummary>("git_summary"),
  targets: (keyword: string) => invoke<SourceTarget[]>("language_targets", { keyword }),
  rebuild: () => invoke<string>("rebuild_native"),
  stale: () => invoke<boolean>("native_source_stale"),
};
export function freshJobId(): string {
  return crypto.randomUUID();
}
export function benchmarkStats(samples: number[]) {
  if (!samples.length) return null;
  const sorted = [...samples].sort((a,b) => a-b);
  const average = sorted.reduce((sum,v) => sum+v,0)/sorted.length;
  const median = sorted[Math.floor((sorted.length-1)*0.5)];
  const p95 = sorted[Math.ceil(sorted.length*0.95)-1];
  const variance = sorted.reduce((sum,v) => sum+(v-average)**2,0)/(sorted.length>1?sorted.length-1:1);
  return { count:samples.length,mean:average,median,p95,min:sorted[0],max:sorted.at(-1)!,stdev:Math.sqrt(variance) };
}
export function reportElapsed(result: RunResponse): number {
  return result.wall_ms; // Child wall time, not CPU or VM execute_ms.
}
