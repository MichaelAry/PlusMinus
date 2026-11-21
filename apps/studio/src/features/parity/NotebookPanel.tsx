import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import { monaco } from "../editor/monaco";
import { native } from "../../api/native";
import { parity, freshJobId } from "../../api/parity";
import { useStudio } from "../../model/studio";
import { freshNotebook, validateNotebook, encodeNotebook, withCell, makeCell, sourceText, streamOutput, errorOutput,
  rememberNotebookDraft, recoverNotebookDraft, latestNotebookDraft, discardNotebookDraft,
  type Notebook, type NotebookCell } from "../../model/notebook";

function CodeCell({source,onChange,onRun,onSave,selected}:{source:string;onChange:(v:string)=>void;onRun:(next:boolean)=>void;onSave:()=>void;selected:boolean}){
  const host=useRef<HTMLDivElement>(null),editor=useRef<monaco.editor.IStandaloneCodeEditor|null>(null);
  const callbacks=useRef({onChange,onRun,onSave});callbacks.current={onChange,onRun,onSave};
  useEffect(()=>{
    if(!host.current)return;
    const e=monaco.editor.create(host.current,{
      value:source,language:"plusminus",theme:"plusminus-graphite",automaticLayout:true,
      minimap:{enabled:false},scrollBeyondLastLine:false,lineNumbers:"on",fontSize:12,
      wordWrap:"on",lineHeight:19,
    });
    editor.current=e;
    const subscription=e.onDidChangeModelContent(()=>callbacks.current.onChange(e.getValue()));
    e.addCommand(monaco.KeyMod.Shift|monaco.KeyCode.Enter,()=>callbacks.current.onRun(true));
    e.addCommand(monaco.KeyMod.CtrlCmd|monaco.KeyCode.Enter,()=>callbacks.current.onRun(false));
    // Monaco may consume Ctrl+S before the window-level shortcut receives it.
    e.addCommand(monaco.KeyMod.CtrlCmd|monaco.KeyCode.KeyS,()=>callbacks.current.onSave());
    return()=>{subscription.dispose();e.dispose();editor.current=null;};
  },[]);
  useEffect(()=>{
    const e=editor.current;
    if(e&&e.getValue()!==source)e.setValue(source);
  },[source]);
  return <div className={"notebook-code "+(selected?"selected":"")} ref={host}/>;
}
function sameString(a:string,b:string){return a===b;}
export function NotebookPanel(){
  const workspace=useStudio(s=>s.workspace),entries=useStudio(s=>s.entries);
  const available=entries.filter(e=>e.path.endsWith(".ipynb")&&!e.directory);
  const [path,setPath]=useState("");
  const [notebook,setNotebook]=useState<Notebook|null>(null);
  const current=useRef<Notebook|null>(null);
  const [digest,setDigest]=useState("");
  const [dirty,setDirty]=useState(false);
  const [selected,setSelected]=useState(0);
  const [running,setRunning]=useState<string|null>(null);
  const activeJob=useRef<string|null>(null);
  const [stale,setStale]=useState<Record<string,boolean>>({});
  const [error,setError]=useState("");
  const [message,setMessage]=useState("");
  const [visibleCount,setVisibleCount]=useState(40);
  const openRef=useRef<(path:string)=>Promise<void>>(async()=>{});
  const saveRef=useRef<()=>Promise<void>>(async()=>{});
  const open=async(p:string)=>{
    if(dirty&&!window.confirm("Discard unsaved notebook changes?"))return;
    const discardPrevious=Boolean(dirty&&workspace&&path);
    const cached=workspace?recoverNotebookDraft(workspace,p):null;
    if(cached){
      if(discardPrevious&&workspace)discardNotebookDraft(workspace,path);
      setPath(p);setNotebook(cached.notebook);current.current=cached.notebook;
      setDigest(cached.digest);setSelected(cached.selected);setStale(cached.stale);
      setDirty(true);setError("");setMessage("Recovered unsaved notebook "+p);return;
    }
    try {
      const doc=await parity.openDocument(p);
      const parsed=validateNotebook(JSON.parse(doc.source.replace(/^\uFEFF/,"")));
      if(discardPrevious&&workspace)discardNotebookDraft(workspace,path);
      setPath(p);setNotebook(parsed);current.current=parsed;
      setDigest(doc.digest);setDirty(false);setStale({});setSelected(0);setError("");setMessage("Opened "+p);
    }catch(e){setError(String(e));}
  };
  openRef.current=open;
  useEffect(() => {
    const handler = (event: Event) => {
      const path=(event as CustomEvent<{path:string}>).detail.path;
      if(path)void openRef.current(path);
    };
    window.addEventListener("studio:notebook-open",handler);
    const requested=sessionStorage.getItem("studio5:open-notebook");
    if(requested){
      sessionStorage.removeItem("studio5:open-notebook");
      void openRef.current(requested);
    }
    return()=>window.removeEventListener("studio:notebook-open",handler);
  },[workspace]);
  useEffect(() => {
    const recovered=workspace?latestNotebookDraft(workspace):null;
    if(recovered){
      const {path:cachedPath,draft}=recovered;
      setPath(cachedPath);setNotebook(draft.notebook);current.current=draft.notebook;
      setDigest(draft.digest);setDirty(true);setStale(draft.stale);setSelected(draft.selected);
    }else{
      setNotebook(null);current.current=null;setPath("");setDigest("");setDirty(false);setStale({});setSelected(0);
    }
  },[workspace]);

  useEffect(()=>{
    const onSwitch=(event:Event)=>{
      if(activeJob.current){event.preventDefault();setError("Stop notebook execution before changing workspace");return;}
      // App-level guard handles dirty drafts even when this Dockview panel is closed.
    };
    window.addEventListener("studio:workspace-switch",onSwitch);
    return()=>window.removeEventListener("studio:workspace-switch",onSwitch);
  },[dirty]);
  const update=(next:Notebook)=>{
    current.current=next;setNotebook(next);setDirty(true);
    if(workspace && path) rememberNotebookDraft(workspace,path,{notebook:next,digest,selected,stale});
  };
  const create=async()=>{
    if(!workspace){setError("Choose workspace first");return;}
    if(dirty&&!window.confirm("Discard unsaved notebook changes?"))return;
    const discardPrevious=Boolean(dirty&&workspace&&path);
    const name=window.prompt("New notebook (.ipynb)", "research.ipynb");
    if(!name)return;
    try{
      const doc=await parity.createNotebook(name,encodeNotebook(freshNotebook()));
      const parsed=validateNotebook(JSON.parse(doc.source));
      if(discardPrevious)discardNotebookDraft(workspace,path);
      setPath(doc.path);setNotebook(parsed);current.current=parsed;setDigest(doc.digest);
      setDirty(false);setError("");setMessage("Created "+doc.path);
      window.dispatchEvent(new Event("studio:refresh-workspace"));
    }catch(e){setError(String(e));}
  };
  const save=async()=>{
    if(!notebook||!path)return;
    const source=encodeNotebook(notebook);
    try{
      const result=await parity.saveDocument(path,source,digest);
      setDigest(result.digest);
      if(sameString(encodeNotebook(current.current??notebook),source)){
        setDirty(false);
        if(workspace)discardNotebookDraft(workspace,path);
      }else if(workspace){
        rememberNotebookDraft(workspace,path,{notebook:current.current??notebook,digest:result.digest,selected,stale});
      }
      setMessage("Saved "+path);setError("");
    }catch(e){setError(String(e));}
  };
  saveRef.current=save;
  useEffect(()=>{
    const handler=()=>void saveRef.current();
    window.addEventListener("studio:save-notebook",handler);
    return()=>window.removeEventListener("studio:save-notebook",handler);
  },[]);
  const replaceSource=(index:number,source:string)=>{
    const n=current.current;if(!n)return;
    const cell=n.cells[index]; if(!cell)return;
    const next=withCell(n,index,c=>({...c,source}));
    update(next);setStale(s=>({...s,[cell.id]:true}));
  };
  const add=(kind:"code"|"markdown",index?:number)=>{
    const n=current.current;if(!n)return;
    const position=index??n.cells.length;
    const next={...n,cells:[...n.cells.slice(0,position),makeCell(kind),...n.cells.slice(position)]};
    update(next);setSelected(position);setVisibleCount(Math.max(visibleCount,position+1));
  };
  const remove=(index:number)=>{
    const n=current.current;if(!n)return;
    update({...n,cells:n.cells.filter((_,i)=>i!==index)});setSelected(Math.max(0,index-1));
  };
  const move=(index:number,delta:number)=>{
    const n=current.current;if(!n)return;
    const to=index+delta;if(to<0||to>=n.cells.length)return;
    const cells=[...n.cells];[cells[index],cells[to]]=[cells[to],cells[index]];
    update({...n,cells});setSelected(to);
  };
  const run=async(index:number,next:boolean):Promise<boolean>=>{
    const snapshot=current.current;if(!snapshot)return false;
    const cell=snapshot.cells[index];if(cell?.cell_type!=="code"||activeJob.current||!sourceText(cell.source).trim())return false;
    const source=sourceText(cell.source),job=freshJobId();
    activeJob.current=job;setRunning(job);setError("");
    try{
      const report=await native.runSource(job,source,"run",10000);
      const output:Record<string,unknown>[]=[];
      if(report.report.output)output.push(streamOutput(report.report.output));
      if(!report.report.ok)output.push(errorOutput(report.report.error));
      const latest=current.current;
      const actualIndex=latest?.cells.findIndex(c=>c.id===cell.id)??-1;
      if(latest&&actualIndex>=0){
        let updated=withCell(latest,actualIndex,c=>({...c,execution_count:(c.execution_count??0)+1,
          outputs:output,metadata:{...c.metadata,plusminus:{execution_mode:"isolated",metrics:report.report.metrics}}}));
        const hasLaterCode=updated.cells.slice(actualIndex+1).some(c=>c.cell_type==="code");
        if(!hasLaterCode){
          updated={...updated,cells:[...updated.cells,makeCell()]};
        }
        update(updated);
        const changedDuringExecution=sourceText(latest.cells[actualIndex].source)!==source;
        setStale(s=>({...s,[cell.id]:changedDuringExecution}));
        if(next){setSelected(Math.min(actualIndex+1,updated.cells.length-1));setVisibleCount(v=>Math.max(v,actualIndex+2));}
      }
      setMessage(report.report.ok?"Cell executed in isolated process":"Native execution returned error");
      return report.report.ok;
    }catch(e){setError(String(e));return false;}
    finally{activeJob.current=null;setRunning(null);}
  };
  const runAll=async()=>{
    const queue=(current.current?.cells??[]).filter(c=>c.cell_type==="code"&&sourceText(c.source).trim()).map(c=>c.id);
    for(const id of queue){
      const index=current.current?.cells.findIndex(c=>c.id===id)??-1;
      if(index<0)continue;
      const success=await run(index,false);
      if(!success)break;
    }
  };
  const stop=async()=>{
    if(activeJob.current)await parity.cancel(activeJob.current).catch(e=>setError(String(e)));
  };
  return <div className="lab-page">
    <header className="lab-heading"><div><small>RESEARCH / NOTEBOOKS</small><h2>Isolated PlusMinus Notebooks</h2>
      <p>Jupyter nbformat v4 · code cells do not share VM variables · persistent outputs only on save.</p></div></header>
    <div className="lab-actions">
      <select aria-label="Open a notebook" value={path} onChange={e=>void open(e.target.value)}>
        <option value="">Choose notebook</option>{available.map(e=><option key={e.path} value={e.path}>{e.path}</option>)}
      </select>
      <button onClick={()=>void create()}>New notebook</button>
      <button disabled={!notebook||!dirty} onClick={()=>void save()}>Save {dirty?"●":""}</button>
      <button disabled={!notebook} onClick={()=>add("code")}>+ Code</button>
      <button disabled={!notebook||!!running} onClick={()=>void runAll()}>Run all</button>
      <button disabled={!notebook} onClick={()=>add("markdown")}>+ Markdown</button>
      <button disabled={!running} onClick={()=>void stop()}>Stop</button>
    </div>
    {error&&<div className="lab-error" role="alert">{error}</div>}
    {message&&<p className="lab-muted">{message}</p>}
    {!notebook?<p className="lab-muted">Choose an existing .ipynb file from the workspace or create a new notebook.</p>:
      <div className="notebook-cells">
        {notebook.cells.slice(0,visibleCount).map((cell:NotebookCell,index)=>{
          const value=sourceText(cell.source);
          return <section key={cell.id} className={"notebook-cell "+(index===selected?"selected":"")}>
            <div className="lab-actions">
              <strong>{cell.cell_type==="code"?"[ "+(cell.execution_count??" ")+" ]":"MD"} · Cell {index+1}</strong>
              <button disabled={!!running||cell.cell_type!=="code"} onClick={()=>void run(index,true)}>Run & next</button>
              <button disabled={!!running||cell.cell_type!=="code"} onClick={()=>void run(index,false)}>Run</button>
              <button onClick={()=>move(index,-1)} disabled={index===0}>↑</button>
              <button onClick={()=>move(index,1)} disabled={index===notebook.cells.length-1}>↓</button>
              <button onClick={()=>remove(index)}>Delete</button>
            </div>
            {cell.cell_type==="code"?
              index===selected?<CodeCell key={cell.id} selected source={value}
                onChange={s=>replaceSource(index,s)} onRun={n=>void run(index,n)} onSave={()=>void save()}/>:
                <pre className="notebook-preview" onClick={()=>setSelected(index)}>{value||"(empty code cell)"}</pre>:
              <><textarea aria-label="Markdown cell" className="lab-textarea" value={value}
                onFocus={()=>setSelected(index)} onChange={e=>replaceSource(index,e.target.value)}/>
              <div className="notebook-markdown"><ReactMarkdown>{value}</ReactMarkdown></div></>}
            {stale[cell.id]&&<div className="lab-error">Output is stale (source edited since execution)</div>}
            {cell.cell_type==="code" && <pre className="notebook-output">{
              (cell.outputs??[]).map(out=>String(out.text??out.evalue??"")).join("\n")||"(no cell output)"
            }</pre>}
          </section>;
        })}
        {notebook.cells.length>visibleCount&&<button onClick={()=>setVisibleCount(c=>c+40)}>
          Show next 40 cells ({notebook.cells.length-visibleCount} hidden)
        </button>}
      </div>}
  </div>;
}
