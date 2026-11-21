import { useCallback, useEffect, useState } from "react";
import { DockviewReact, themeDark, type DockviewReadyEvent } from "dockview-react";
import { native } from "./api/native";
import type { RunMode, TreeEntry } from "./api/contracts";
import { useStudio } from "./model/studio";
import { EditorPane } from "./features/editor/EditorPane";
import { OutputPane } from "./features/output/OutputPane";

const panels = { editor: EditorPane, results: OutputPane };
const modes: RunMode[] = ["run", "compile", "profile", "trace"];

export default function App() {
  const workspace = useStudio((s) => s.workspace);
  const entries = useStudio((s) => s.entries);
  const documents = useStudio((s) => s.documents);
  const activeId = useStudio((s) => s.activeId);
  const mode = useStudio((s) => s.mode);
  const runningJob = useStudio((s) => s.runningJob);
  const response = useStudio((s) => s.response);
  const transportError = useStudio((s) => s.transportError);
  const setWorkspace = useStudio((s) => s.setWorkspace);
  const setEntries = useStudio((s) => s.setEntries);
  const open = useStudio((s) => s.open);
  const saved = useStudio((s) => s.saved);
  const started = useStudio((s) => s.started);
  const finished = useStudio((s) => s.finished);
  const setMode = useStudio((s) => s.setMode);
  const [engine, setEngine] = useState("Checking C++ runner…");
  const [message, setMessage] = useState("Welcome to Graphite Research");
  const [busy, setBusy] = useState(false);

  const active = documents.find((d) => d.id === activeId) ?? documents[0];

  useEffect(() => {
    void native.engineStatus().then(setEngine).catch((error) => setEngine("Runner unavailable: " + String(error)));
  }, []);

  const refresh = useCallback(async () => {
    try { setEntries(await native.listWorkspace()); }
    catch (error) { setMessage("Workspace: " + String(error)); }
  }, [setEntries]);

  const chooseWorkspace = useCallback(async () => {
    if (useStudio.getState().documents.some((d) => d.dirty) &&
      !window.confirm("Switch workspace and discard unsaved documents?")) return;
    try {
      const folder = await native.chooseWorkspace();
      const tree = await native.listWorkspace();
      setWorkspace(folder, tree);
      setMessage("Workspace selected: " + folder);
    } catch (error) { setMessage(String(error)); }
  }, [setWorkspace]);

  const openFile = useCallback(async (path: string) => {
    const existing = useStudio.getState().documents.find((d) => d.id === path);
    if (existing) { useStudio.getState().select(path); return; }
    try { open(await native.openSource(path)); setMessage("Opened " + path); }
    catch (error) { setMessage("Open failed: " + String(error)); }
  }, [open]);

  const saveFile = useCallback(async () => {
    const state = useStudio.getState();
    const document = state.documents.find((d) => d.id === state.activeId);
    if (!document || busy) return;
    if (!state.workspace) { setMessage("Select a workspace before saving"); return; }
    setBusy(true);
    try {
      let path = document.path;
      let digest = document.digest;
      if (!path) {
        const entered = window.prompt("Create .pm file in workspace (relative path)", "experiment.pm");
        if (!entered) return;
        const created = await native.createSource(entered);
        path = created.path;
        digest = created.digest;
      }
      const next = await native.saveSource(path, document.source, digest);
      saved(document.id, next);
      setMessage("Saved " + path);
      await refresh();
    } catch (error) { setMessage("Save failed: " + String(error)); }
    finally { setBusy(false); }
  }, [busy, refresh, saved]);

  const newFile = useCallback(async () => {
    if (!workspace) { setMessage("Select a workspace first"); return; }
    const path = window.prompt("New PlusMinus file (relative to workspace)", "new-program.pm");
    if (!path) return;
    try {
      const doc = await native.createSource(path);
      open(doc);
      await refresh();
    } catch (error) { setMessage("Create failed: " + String(error)); }
  }, [workspace, open, refresh]);

  const execute = useCallback(async (override?: RunMode) => {
    const state = useStudio.getState();
    if (state.runningJob) return;
    const doc = state.documents.find((d) => d.id === state.activeId);
    if (!doc) return;
    const jobId = crypto.randomUUID();
    started(jobId);
    try {
      const result = await native.runSource(jobId, doc.source, override ?? state.mode, 10000);
      finished(jobId, result, null);
      setMessage(result.report.ok ? "Native execution completed" : "Execution failed — see Diagnostics");
    } catch (error) {
      finished(jobId, null, String(error));
      setMessage("Execution failed: " + String(error));
    }
  }, [finished, started]);

  const stop = useCallback(async () => {
    const job = useStudio.getState().runningJob;
    if (job) {
      try { await native.cancelRun(job); }
      catch (error) { setMessage("Cancel failed: " + String(error)); }
    }
  }, []);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
        event.preventDefault(); void saveFile();
      }
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "o") {
        event.preventDefault(); void chooseWorkspace();
      }
      if (event.key === "F5") { event.preventDefault(); void execute("run"); }
      if (event.key === "F6") { event.preventDefault(); void execute("profile"); }
      if (event.key === "F7") { event.preventDefault(); void execute("trace"); }
      if (event.key === "Escape" && useStudio.getState().runningJob) {
        event.preventDefault(); void stop();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [chooseWorkspace, execute, saveFile, stop]);

  const onDockReady = useCallback((event: DockviewReadyEvent) => {
    event.api.addPanel({ id: "source-editor", component: "editor", title: "Source" });
    event.api.addPanel({
      id: "run-results", component: "results", title: "Run / Metrics",
      position: { referencePanel: "source-editor", direction: "below" },
    });
  }, []);

  return (
    <div className="studio">
      <header className="topbar">
        <div className="brand"><div className="brand-glyph">±</div><span>PLUSMINUS</span><span className="brand-divider">/</span><span className="brand-sub">STUDIO 5</span></div>
        <div className="top-actions">
          <button onClick={() => void chooseWorkspace()}>Open workspace <kbd>Ctrl+O</kbd></button>
          <button onClick={() => void newFile()} disabled={!workspace}>New</button>
          <button onClick={() => void saveFile()} disabled={busy}>Save <kbd>Ctrl+S</kbd></button>
          <span className="toolbar-divider" />
          <select aria-label="Execution mode" value={mode} onChange={(e) => setMode(e.target.value as RunMode)}>
            {modes.map((m) => <option key={m} value={m}>{m.toUpperCase()}</option>)}
          </select>
          <button className="primary" onClick={() => void execute()} disabled={!!runningJob}>▶ Run <kbd>F5</kbd></button>
          <button className="stop" onClick={() => void stop()} disabled={!runningJob}>■ Stop</button>
        </div>
        <div className={"backend-pill " + (engine === "Runner ready" ? "connected" : "disconnected")}>{engine}</div>
      </header>
      <div className="main-area">
        <aside className="activity-rail" aria-label="Workspace navigation">
          <button className="selected" title="Develop">⌘</button>
          <button disabled title="Test Lab: Stage 2">✓</button>
          <button disabled title="Notebooks: Stage 2">▤</button>
          <button disabled title="Language Lab: Stage 2">⌁</button>
          <button disabled title="Performance: Stage 2">◫</button>
          <div className="rail-bottom"><button title="Migration Stage 1" disabled>⚙</button></div>
        </aside>
        <aside className="explorer">
          <div className="pane-label"><span>EXPLORER</span><button onClick={() => void refresh()} title="Refresh workspace" disabled={!workspace}>↻</button></div>
          <div className="workspace-name" title={workspace ?? ""}>{workspace ? workspace.split(/[\\/]/).at(-1) : "NO WORKSPACE"}</div>
          {!workspace && <div className="explorer-empty">Choose a project folder to browse .pm files.<button onClick={() => void chooseWorkspace()}>Select folder</button></div>}
          {workspace && <div className="file-list">{entries.length ? entries.map((entry: TreeEntry) =>
            <button key={entry.path} className={"file-item " + (entry.directory ? "directory" : "") + (active?.path === entry.path ? " current" : "")}
              style={{ paddingLeft: 14 + entry.depth * 14 }}
              disabled={entry.directory}
              onClick={() => void openFile(entry.path)}>
              <span className="file-marker">{entry.directory ? "▸" : "±"}</span><span>{entry.name}</span>
            </button>
          ) : <span className="explorer-empty">No .pm files found (depth limit: 4).</span>}</div>}
          <div className="explorer-footnote">Native C++ engine · isolated process</div>
        </aside>
        <main className="workbench">
          <div className="workspace-header"><span>DEVELOPMENT</span><span className="workspace-breadcrumb">{active?.path || "Untitled.pm"}</span><span className="workspace-hint">RUN / COMPILE / PROFILE / TRACE</span></div>
          <div className="dock-host"><DockviewReact components={panels} onReady={onDockReady} theme={themeDark} /></div>
        </main>
      </div>
      <footer className="statusbar">
        <span className="status-indicator">●</span><span>{message}</span><span className="status-spacer" />
        <span>{runningJob ? "RUNNING" : response ? (response.report.ok ? "SUCCESS" : "FAILED") : transportError ? "ERROR" : "READY"}</span>
        <span className="status-separator">│</span><span>UTF-8</span><span className="status-separator">│</span><span>TAURI / RUST / C++20</span>
      </footer>
    </div>
  );
}
