import { useEffect, useState } from "react";
import { parity, type SourceTarget } from "../../api/parity";
import { useStudio } from "../../model/studio";

const words=["if","else","while","func","proc","return","go","sync","lock","unlock",
  "int","float","double","print","len","resize","sin","cos","pow","fact","multifact"];
export function LanguagePanel(){
  const workspace=useStudio(s=>s.workspace);
  const [keyword,setKeyword]=useState("if");
  const [targets,setTargets]=useState<SourceTarget[]>([]);
  const [stale,setStale]=useState(false);
  const [busy,setBusy]=useState(false);
  const [log,setLog]=useState("");
  const [error,setError]=useState("");
  useEffect(()=>{void parity.stale().then(setStale).catch(()=>{});},[workspace]);
  async function locate(){
    try{setTargets(await parity.targets(keyword));setError("");}
    catch(e){setTargets([]);setError(String(e));}
  }
  async function rebuild(){
    if(busy||!window.confirm("Rebuild the existing C++ core with CMake?"))return;
    setBusy(true);setLog("");setError("");
    try{setLog(await parity.rebuild());setStale(false);}
    catch(e){setError(String(e));setStale(true);}
    finally{setBusy(false);}
  }
  return <div className="lab-page">
    <header className="lab-heading"><div><small>RESEARCH / INTERNALS</small><h2>Language Implementation</h2>
      <p>Navigate actual checked-out C++ implementation by PlusMinus keyword. No C++ source rewritten automatically.</p></div></header>
    <div className="lab-actions">
      <select value={keyword} onChange={e=>setKeyword(e.target.value)}>
        {words.map(word=><option key={word}>{word}</option>)}</select>
      <button onClick={()=>void locate()} disabled={!workspace}>Find implementation</button>
      <button onClick={()=>void rebuild()} disabled={!workspace||busy}>CMake rebuild</button>
      <strong>{stale?"C++ changed: rebuild required":"Native engine state: unchanged"}</strong>
    </div>
    {error&&<div className="lab-error" role="alert">{error}</div>}
    {!workspace&&<p className="lab-muted">Select the PlusMinus repository checkout to browse its C++ implementation.</p>}
    {targets.map(target=><button key={target.path+target.label} className="session-row" onClick={()=>{
      window.dispatchEvent(new CustomEvent("studio:open-path",{detail:{path:target.path,anchor:target.anchor}}));
    }}>
      <strong>{target.label}</strong><span>{target.path}</span><span>Line {target.line}</span>
    </button>)}
    {log&&<><h3>Real CMake build log</h3><pre className="lab-mini-scroll">{log}</pre></>}
    <p className="lab-muted">Editing C++ files marks the running native engine stale. Running VM/tests is blocked until a successful rebuild; packaged binaries are not silently replaced.</p>
  </div>;
}
