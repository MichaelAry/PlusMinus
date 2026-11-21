import { useEffect, useState } from "react";
import { parity, type GitSummary } from "../../api/parity";
import { useStudio } from "../../model/studio";

export function GitPanel(){
  const workspace=useStudio(s=>s.workspace);
  const [data,setData]=useState<GitSummary|null>(null);
  const [error,setError]=useState("");
  async function refresh(){
    try{setData(await parity.git());setError("");}
    catch(e){setError(String(e));}
  }
  useEffect(()=>{if(workspace)void refresh();else setData(null);},[workspace]);
  return <div className="lab-page">
    <header className="lab-heading"><div><small>RESEARCH / SOURCE CONTROL</small><h2>Git Inspector</h2>
      <p>Read-only repository status, recent commits, and diff statistics.</p></div>
      <button onClick={()=>void refresh()} disabled={!workspace}>Refresh</button></header>
    {error&&<div className="lab-error" role="alert">{error}</div>}
    {data?.available?<><div className="metrics-grid">
      <div className="metric"><small>Branch</small><strong>{data.branch||"detached HEAD"}</strong></div>
      <div className="metric"><small>HEAD</small><strong>{data.sha}</strong></div>
      <div className="metric"><small>Working tree</small><strong>{data.dirty?"Dirty":"Clean"}</strong></div>
    </div><div className="lab-two-col">
      <section><h3>Changes</h3><pre className="lab-mini-scroll">{data.changes||"No changes"}</pre></section>
      <section><h3>Diff stats</h3><pre className="lab-mini-scroll">{data.diff||"No diff"}</pre></section>
    </div><h3>Recent commits</h3><pre className="lab-mini-scroll">{data.commits}</pre></>:
    <p className="lab-muted">{data?.error||"Open a Git working directory to inspect history."}</p>}
  </div>;
}
