import { useCallback, useEffect, useRef, useState } from "react";
import { DockviewReact, themeDark, type DockviewReadyEvent } from "dockview-react";
import { native } from "./api/native";
import { parity } from "./api/parity";
import type { RunMode, TreeEntry } from "./api/contracts";
import { useStudio } from "./model/studio";
import { hasUnsavedNotebookDrafts, discardWorkspaceNotebooks } from "./model/notebook";
import { EditorPane } from "./features/editor/EditorPane";
import { OutputPane } from "./features/output/OutputPane";
import { TestLab } from "./features/parity/TestLab";
import { SourceTestsPanel } from "./features/parity/SourceTestsPanel";
import { HistoryPanel } from "./features/parity/HistoryPanel";
 import { ProfilerPanel } from "./features/parity/ProfilerPanel";
import { ResourcePanel } from "./features/parity/ResourcePanel";
import { GraphPanel } from "./features/parity/GraphPanel";
import { NotebookPanel } from "./features/parity/NotebookPanel";
import { LanguagePanel } from "./features/parity/LanguagePanel";
import { GitPanel } from "./features/parity/GitPanel";
import "./features/parity/ParityStyle.css";

const panels = {
  editor: EditorPane, results: OutputPane, tests: TestLab, sourcetests: SourceTestsPanel, history: HistoryPanel,
  profiler: ProfilerPanel, resources: ResourcePanel, graphs: GraphPanel, notebook: NotebookPanel,
  language: LanguagePanel, git: GitPanel,
};
type PanelName = keyof typeof panels;
const modes: RunMode[] = ["run","compile","profile","trace"];
const panelTitles:Record<PanelName,string> = {
  editor:"Editor",results:"Results",tests:"Native Test Lab",sourcetests:"Source Tests",history:"History",
  profiler:"Profiler",resources:"Resources",graphs:"Compiler Explorer",notebook:"Notebooks",
  language:"Language Internals",git:"Git Inspector",
};
const paletteCommands:{label:string;id:PanelName}[] = [
  {label:"Show code editor",id:"editor"},{label:"Open Native Test Lab",id:"tests"},
  {label:"Open history and baseline comparison",id:"history"},
  {label:"Open performance profiler",id:"profiler"},
  {label:"Open measured resource graphs",id:"resources"},
  {label:"Open compiler graphs",id:"graphs"},
  {label:"Open isolated notebooks",id:"notebook"},
  {label:"Browse C++ language implementation",id:"language"},
  {label:"Open Git inspector",id:"git"},
];

export default function App() {
  const workspace=useStudio(s=>s.workspace),entries=useStudio(s=>s.entries);
  const docs=useStudio(s=>s.documents),activeId=useStudio(s=>s.activeId);
  const mode=useStudio(s=>s.mode),runningJob=useStudio(s=>s.runningJob);
  const response=useStudio(s=>s.response),transportError=useStudio(s=>s.transportError);
  const setWorkspace=useStudio(s=>s.setWorkspace),setEntries=useStudio(s=>s.setEntries);
  const open=useStudio(s=>s.open),saved=useStudio(s=>s.saved);
  const started=useStudio(s=>s.started),finished=useStudio(s=>s.finished),setMode=useStudio(s=>s.setMode);
  const active=docs.find(d=>d.id===activeId)??docs[0];
  const dockApi=useRef<DockviewReadyEvent["api"]|null>(null);
  const [engine,setEngine]=useState("Checking C++ runner…");
  const [message,setMessage]=useState("Graphite Research / Studio 5");
  const [busy,setBusy]=useState(false);
  const [palette,setPalette]=useState(false);
  const [search,setSearch]=useState("");

  useEffect(()=>{
    void native.engineStatus().then(setEngine).catch(e=>setEngine("Runner unavailable: "+String(e)));
  },[]);
  const refresh=useCallback(async()=>{
    try{setEntries(await native.listWorkspace());}
    catch(e){setMessage("Workspace: "+String(e));}
  },[setEntries]);
  const chooseWorkspace=useCallback(async()=>{
    if(!window.dispatchEvent(new Event("studio:workspace-switch",{cancelable:true})))return;
    if((useStudio.getState().documents.some(d=>d.dirty)||hasUnsavedNotebookDrafts(workspace))&&
      !window.confirm("Switch workspace and discard unsaved documents/notebooks?"))return;
    try{
      const folder=await native.chooseWorkspace();
      const tree=await native.listWorkspace();
      if(workspace)discardWorkspaceNotebooks(workspace);
      setWorkspace(folder,tree);
      setMessage("Workspace selected: "+folder);
    }catch(e){setMessage(String(e));}
  },[setWorkspace,workspace]);
  const showPanel=useCallback((name:PanelName)=>{
    const api=dockApi.current;if(!api)return;
    const id=name==="editor"?"source-editor":name==="results"?"run-results":"tool-"+name;
    const old=api.getPanel(id);
    if(old){old.api.setActive();return;}
    const reference=api.getPanel("source-editor");
    api.addPanel({id,component:name,title:panelTitles[name],
      position:reference?{referencePanel:reference,direction:name==="tests"?"right":"below"}:undefined});
  },[]);
  const openFile=useCallback(async(path:string,anchor?:string)=>{
    if(path.endsWith(".ipynb")){
      sessionStorage.setItem("studio5:open-notebook",path);
      showPanel("notebook");
      window.dispatchEvent(new CustomEvent("studio:notebook-open",{detail:{path}}));
      return;
    }
    const existing=useStudio.getState().documents.find(d=>d.path===path);
    if(existing){useStudio.getState().select(existing.id);}
    else try{
      const doc=path.endsWith(".pm")?await native.openSource(path):await parity.openDocument(path);
      open(doc);setMessage("Opened "+path);
    }catch(e){setMessage("Open failed: "+String(e));return;}
    showPanel("editor");
    if(anchor)requestAnimationFrame(()=>setTimeout(()=>{
      window.dispatchEvent(new CustomEvent("studio:goto-anchor",{detail:{path,anchor}}));
    },50));
  },[open,showPanel]);
  const saveFile=useCallback(async()=>{
    if(dockApi.current?.activePanel?.id==="tool-notebook"){
      window.dispatchEvent(new Event("studio:save-notebook"));return;
    }
    const state=useStudio.getState(),doc=state.documents.find(d=>d.id===state.activeId);
    if(!doc||busy)return;
    if(!state.workspace){setMessage("Select a workspace before saving");return;}
    setBusy(true);
    try{
      let path=doc.path,digest=doc.digest;
      if(!path){
        const entered=window.prompt("New .pm file (workspace relative)", "experiment.pm");
        if(!entered)return;
        const created=await native.createSource(entered);
        path=created.path;digest=created.digest;
      }
      const next=path.endsWith(".pm")?await native.saveSource(path,doc.source,digest):
        await parity.saveDocument(path,doc.source,digest);
      saved(doc.id,next);setMessage("Saved "+path);await refresh();
    }catch(e){setMessage("Save failed: "+String(e));}
    finally{setBusy(false);}
  },[busy,refresh,saved]);
  const newFile=useCallback(async()=>{
    if(!workspace){setMessage("Choose workspace first");return;}
    const path=window.prompt("New PlusMinus source filename", "new-program.pm");
    if(!path)return;
    try{open(await native.createSource(path));await refresh();showPanel("editor");}
    catch(e){setMessage("Create failed: "+String(e));}
  },[workspace,open,refresh,showPanel]);
  const execute=useCallback(async(override?:RunMode)=>{
    const state=useStudio.getState();
    if(state.runningJob)return;
    const doc=state.documents.find(d=>d.id===state.activeId);
    if(!doc || (doc.path && !doc.path.endsWith(".pm"))){setMessage("Select a PlusMinus .pm document to execute");return;}
    const job=crypto.randomUUID();started(job);
    try{
      const result=await native.runSource(job,doc.source,override??state.mode,10000);
      finished(job,result,null);
      setMessage(result.report.ok?"Native execution completed":"PlusMinus error — see Diagnostics");
    }catch(e){finished(job,null,String(e));setMessage("Execution failed: "+String(e));}
    showPanel("results");
  },[started,finished,showPanel]);
  const stop=useCallback(async()=>{
    const id=useStudio.getState().runningJob;
    if(id)try{await native.cancelRun(id);}catch(e){setMessage(String(e));}
  },[]);

  useEffect(()=>{
    const refreshEvent=()=>void refresh();
    const openEvent=(event:Event)=>{
      const {path,anchor}=(event as CustomEvent<{path:string;anchor?:string}>).detail;
      if(path)void openFile(path,anchor);
    };
    window.addEventListener("studio:open-path",openEvent);
    window.addEventListener("studio:refresh-workspace",refreshEvent);
    return()=>{
      window.removeEventListener("studio:open-path",openEvent);
      window.removeEventListener("studio:refresh-workspace",refreshEvent);
    };
  },[openFile,refresh]);
  useEffect(()=>{
    const guard=(e:BeforeUnloadEvent)=>{
      if(hasUnsavedNotebookDrafts()||useStudio.getState().documents.some(d=>d.dirty)){
        e.preventDefault();e.returnValue="";
      }
    };
    window.addEventListener("beforeunload",guard);
    return()=>window.removeEventListener("beforeunload",guard);
  },[]);
  useEffect(()=>{
    function onKey(e:KeyboardEvent){
      if((e.ctrlKey||e.metaKey)&&e.shiftKey&&e.key.toLowerCase()==="p"){
        e.preventDefault();setPalette(p=>!p);return;
      }
      if(e.key==="Escape" && palette){setPalette(false);return;}
      if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==="s"){
        e.preventDefault();void saveFile();
      }
      if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==="o"){
        e.preventDefault();void chooseWorkspace();
      }
      if(e.key==="F5"){e.preventDefault();void execute("run");}
      if(e.key==="F6"){e.preventDefault();void execute("profile");}
      if(e.key==="F7"){e.preventDefault();void execute("trace");}
      if(e.key==="Escape"&&useStudio.getState().runningJob){e.preventDefault();void stop();}
    }
    window.addEventListener("keydown",onKey);
    return()=>window.removeEventListener("keydown",onKey);
  },[palette,chooseWorkspace,execute,saveFile,stop]);
  const onDockReady=useCallback((event:DockviewReadyEvent)=>{
    dockApi.current=event.api;
    let restored=false;
    const saved=localStorage.getItem("studio5:dockview:layout");
    if(saved)try{event.api.fromJSON(JSON.parse(saved));restored=true;}catch{localStorage.removeItem("studio5:dockview:layout");}
    if(!restored){
      event.api.addPanel({id:"source-editor",component:"editor",title:"Source"});
      event.api.addPanel({id:"run-results",component:"results",title:"Results",
        position:{referencePanel:"source-editor",direction:"below"}});
    }
    event.api.onDidLayoutChange(()=>{
      try{localStorage.setItem("studio5:dockview:layout",JSON.stringify(event.api.toJSON()));}catch{/* Private mode */}
    });
  },[]);
  const split=()=>{const api=dockApi.current;if(!api)return;const target=api.getPanel("source-editor");
    api.addPanel({id:"split-editor-"+Date.now(),component:"editor",title:"Split editor",
      position:target?{referencePanel:target,direction:"right"}:undefined});
  };
  const menu=paletteCommands.filter(item=>item.label.toLowerCase().includes(search.toLowerCase()));
  return <div className="studio">
    <header className="topbar">
      <div className="brand"><div className="brand-glyph">±</div><span>PLUSMINUS</span>
        <span className="brand-divider">/</span><span className="brand-sub">STUDIO 5</span></div>
      <div className="top-actions">
        <button onClick={()=>void chooseWorkspace()}>Workspace <kbd>Ctrl+O</kbd></button>
        <button disabled={!workspace} onClick={()=>void newFile()}>New</button>
        <button disabled={busy} onClick={()=>void saveFile()}>Save <kbd>Ctrl+S</kbd></button>
        <button onClick={split}>Split</button>
        <button onClick={()=>{setPalette(true);setSearch("");}}>Commands</button>
        <span className="toolbar-divider"/>
        <select aria-label="Execution mode" value={mode} onChange={e=>setMode(e.target.value as RunMode)}>
          {modes.map(m=><option key={m}>{m}</option>)}</select>
        <button className="primary" disabled={!!runningJob} onClick={()=>void execute()}>▶ Run <kbd>F5</kbd></button>
        <button className="stop" disabled={!runningJob} onClick={()=>void stop()}>■ Stop</button>
      </div>
      <div className={"backend-pill "+(engine==="Runner ready"?"connected":"disconnected")}>{engine}</div>
    </header>
    <div className="main-area">
      <aside className="activity-rail" aria-label="Workspace navigation">
        {(["editor","tests","sourcetests","notebook","profiler","resources","graphs","history","language","git"] as PanelName[]).map((n,i)=>
          <button key={n} title={panelTitles[n]} aria-label={panelTitles[n]} onClick={()=>showPanel(n)}>
            {["⌘","✓","≡","▤","◫","▥","⌁","◷","✥","⑂"][i]}</button>)}
      </aside>
      <aside className="explorer">
        <div className="pane-label"><span>EXPLORER</span><button onClick={()=>void refresh()} disabled={!workspace}>↻</button></div>
        <div className="workspace-name" title={workspace??""}>{workspace?workspace.split(/[\\/]/).at(-1):"NO WORKSPACE"}</div>
        {!workspace&&<div className="explorer-empty">Choose the PlusMinus checkout or another project folder.
          <button onClick={()=>void chooseWorkspace()}>Select folder</button></div>}
        {workspace&&<div className="file-list">{entries.length?entries.map((entry:TreeEntry)=>
          <button key={entry.path} className={"file-item "+(entry.directory?"directory":"")+
            (active?.path===entry.path?" current":"")}
            style={{paddingLeft:14+entry.depth*14}} disabled={entry.directory} onClick={()=>void openFile(entry.path)}>
            <span className="file-marker">{entry.directory?"▸":entry.path.endsWith(".ipynb")?"▤":"±"}</span>
            <span>{entry.name}</span>
          </button>):<span className="explorer-empty">No source files found.</span>}</div>}
        <div className="explorer-footnote">C++20 · isolated process · Studio 5 parity</div>
      </aside>
      <main className="workbench">
        <div className="workspace-header"><span>RESEARCH WORKBENCH</span>
          <span className="workspace-breadcrumb">{active?.path||"Untitled.pm"}</span>
          <span className="workspace-hint">Ctrl+Shift+P / COMMAND PALETTE</span></div>
        <div className="dock-host"><DockviewReact components={panels} onReady={onDockReady} theme={themeDark}/></div>
      </main>
    </div>
    <footer className="statusbar"><span className="status-indicator">●</span><span>{message}</span>
      <span className="status-spacer"/>
      <span>{runningJob?"RUNNING":response?(response.report.ok?"SUCCESS":"FAILED"):transportError?"ERROR":"READY"}</span>
      <span className="status-separator">│</span><span>UTF-8</span>
      <span className="status-separator">│</span><span>RUST / C++20</span>
    </footer>
    {palette&&<div className="command-overlay" role="presentation" onMouseDown={()=>setPalette(false)}>
      <section className="command-dialog" role="dialog" aria-modal="true" aria-label="Command palette"
        onMouseDown={e=>e.stopPropagation()}>
        <input aria-label="Command search" autoFocus placeholder="Search commands…" value={search} onChange={e=>setSearch(e.target.value)}/>
        {menu.map(command=><button key={command.id} onClick={()=>{showPanel(command.id);setPalette(false);}}>
          {command.label}</button>)}
        <button onClick={()=>setPalette(false)}>Close · Escape</button>
      </section></div>}
  </div>;
}
