import { useCallback, useEffect, useRef, useState } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { parity, type HistoryOverview, type HistoryRow, type Session, type NativeResult, type SessionDiff } from "../../api/parity";

export function HistoryPanel() {
  const [overview, setOverview] = useState<HistoryOverview | null>(null);
  const [runs, setRuns] = useState<HistoryRow[]>([]);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [results, setResults] = useState<NativeResult[]>([]);
  const [active, setActive] = useState<number | null>(null);
  const [diff, setDiff] = useState<SessionDiff | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const parent = useRef<HTMLDivElement>(null);
  const v = useVirtualizer({count:runs.length,getScrollElement:()=>parent.current,estimateSize:()=>33,overscan:7});
  const refresh = useCallback(async () => {
    try {
      const [o,r,s] = await Promise.all([parity.overview(),parity.runs(),parity.sessions()]);
      setOverview(o);setRuns(r);setSessions(s);setError("");
    } catch(e) {setError(String(e));}
  }, []);
  useEffect(() => {void refresh();},[refresh]);
  async function exportHistory(format:"csv"|"json") {
    try {setMessage(await parity.exportHistory(format));setError("");}
    catch(e){setError(String(e));}
  }
  async function inspect(id:number) {
    try {setResults(await parity.results(id));setActive(id);setDiff(null);}
    catch(e){setError(String(e));}
  }
  async function setBaseline() {
    if(active === null)return;
    try{await parity.setBaseline(active);await refresh();}
    catch(e){setError(String(e));}
  }
  async function compare() {
    if(active === null || overview?.baseline == null)return;
    try{setDiff(await parity.compare(overview.baseline,active));}
    catch(e){setError(String(e));}
  }
  return <div className="lab-page">
    <header className="lab-heading"><div><small>RESEARCH / STORAGE</small><h2>Execution & Test History</h2>
      <p>Studio 4 SQLite history is copied; the source database remains untouched.</p></div>
      <div className="lab-actions">
        <button onClick={() => void refresh()}>Refresh</button>
        <button onClick={() => void exportHistory("csv")}>Export CSV</button>
        <button onClick={() => void exportHistory("json")}>Export JSON</button>
      </div></header>
    {error && <div role="alert" className="lab-error">{error}</div>}
    {message && <p className="lab-muted">{message}</p>}
    <div className="metrics-grid">{Object.entries(overview?.counts ?? {}).map(([key,value]) =>
      <div className="metric" key={key}><small>{key.replaceAll("_"," ")}</small><strong>{value}</strong></div>)}</div>
    <div className="lab-two-col">
      <section><h3>Native sessions</h3><div className="lab-mini-scroll">{sessions.map(s =>
        <button className={"session-row " + (s.id===active?"selected":"")} key={s.id} onClick={()=>void inspect(s.id)}>
          <span>#{s.id}</span><span>{s.label}</span><span>{s.platform}</span><span>{s.total_ms.toFixed(1)} ms</span>
          {overview?.baseline===s.id && <strong>BASELINE</strong>}
        </button>)}</div></section>
      <section><h3>Session inspector</h3>
        {active===null?<p className="lab-muted">Choose a native session.</p>:<>
          <div className="lab-actions"><button onClick={()=>void setBaseline()}>Set baseline</button>
          <button disabled={overview?.baseline==null} onClick={()=>void compare()}>Compare</button></div>
          <div className="lab-mini-scroll">{results.map(r=><div className="session-row" key={r.id}>
            <span className={"test-result "+r.status.toLowerCase()}>{r.status}</span><span>{r.id}</span>
            <span>{r.elapsed_ms.toFixed(2)} ms</span></div>)}</div>
          {diff && <pre className="lab-inspector">{"Introduced: "+diff.introduced.join(", ")+
            "\nFixed: "+diff.fixed.join(", ")+
            "\nComparable platforms: "+String(diff.comparable_platform)+
            "\nSame source: "+String(diff.same_source)}</pre>}</>}
      </section>
    </div>
    <h3>Recent program executions</h3>
    <div className="lab-table" ref={parent} style={{maxHeight:290}}>
      <div style={{height:v.getTotalSize(),position:"relative"}}>
        {v.getVirtualItems().map(row=>{
          const record=runs[row.index];
          return <div key={record.id} className="session-row" style={{height:row.size,position:"absolute",
            width:"100%",transform:"translateY("+row.start+"px)"}}>
            <span>#{record.id}</span><span className={record.ok?"test-result pass":"test-result fail"}>{record.ok?"PASS":"FAIL"}</span>
            <span>{record.category}</span><span>{record.label}</span><span>{record.elapsed_ms.toFixed(2)} ms</span>
          </div>;
        })}
      </div>
    </div>
    <p className="lab-muted">Database: {overview?.v5_path??"Loading…"} · Single-run timings are not statistically validated benchmarks.</p>
  </div>;
}
