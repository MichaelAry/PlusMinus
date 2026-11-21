import { invoke } from "@tauri-apps/api/core";
import type { Document, RunMode, RunResponse, TreeEntry } from "./contracts";

export const native = {
  chooseWorkspace: () => invoke<string>("choose_workspace"),
  listWorkspace: () => invoke<TreeEntry[]>("list_workspace"),
  openSource: (path: string) => invoke<Document>("open_source", { path }),
  createSource: (path: string) => invoke<Document>("create_source", { path }),
  saveSource: (path: string, source: string, expected: string) =>
    invoke<Document>("save_source", { path, source, expected }),
  runSource: (job_id: string, source: string, mode: RunMode, timeout_ms: number) =>
    invoke<RunResponse>("run_source", { request: { job_id, source, mode, timeout_ms } }),
  cancelRun: (jobId: string) => invoke<boolean>("cancel_run", { jobId }),
  engineStatus: () => invoke<string>("engine_status"),
  nativeTestStatus: () => invoke<string>("native_test_status"),
};
