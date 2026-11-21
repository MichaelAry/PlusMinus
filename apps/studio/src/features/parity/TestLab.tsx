import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { parity, freshJobId, type NativeCase, type NativeResult, type NativeEvent, type SessionDiff } from "../../api/parity";

type Selection = "quick" | "full" | "selected" | "filtered" | "failed";

export function TestLab() {
  const [tests, setTests] = useState<NativeCase[]>([]);
  const [results, setResults] = useState<Record<string, NativeResult>>({});
  const [search, setSearch] = useState("");
  const [group, setGroup] = useState("All groups");
  const [filter, setFilter] = useState("all");
  const [selected, setSelected] = useState("");
  const [error, setError] = useState("");
  const [running, setRunning] = useState<string | null>(null);
  const [progress, setProgress] = useState({ done: 0, total: 0 });
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [baselineId, setBaselineId] = useState<number | null>(null);
  const [comparison, setComparison] = useState<SessionDiff | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const jobRef = useRef<string | null>(null);
  const mounted = useRef(true);

  useEffect(()=>{
    const onSwitch=(event:Event)=>{
      if(jobRef.current){event.preventDefault();setError("Stop native tests before changing workspace");}
    };
    window.addEventListener("studio:workspace-switch",onSwitch);
    return()=>window.removeEventListener("studio:workspace-switch",onSwitch);
  },[]);
  const refresh = useCallback(async () => {
    try {
      const [rows, overview] = await Promise.all([parity.listNative(), parity.overview()]);
      if (mounted.current) { setTests(rows); setBaselineId(overview.baseline); setError(""); }
    } catch(e) { if (mounted.current) setError(String(e)); }
  }, []);
  useEffect(() => {
    mounted.current = true;
    void refresh();
    return () => { mounted.current = false; };
  }, [refresh]);

  const groups = useMemo(() => ["All groups", ...new Set(tests.map(t => t.group))], [tests]);
  const visible = useMemo(() => tests.filter(t => {
    const record = results[t.id];
    return (group === "All groups" || t.group === group)
      && (filter === "all" || (filter === "failed" ? (record && record.status !== "PASS") :
        filter === "not_run" ? !record : record?.status === filter))
      && (t.id.toLowerCase().includes(search.toLowerCase()) || t.source.toLowerCase().includes(search.toLowerCase()));
  }), [tests, group, filter, results, search]);
  const virtualizer = useVirtualizer({
    count: visible.length, getScrollElement: () => scrollRef.current,
    estimateSize: () => 39, overscan: 8,
  });
  const chosen = tests.find(t => t.id === selected);
  const result = results[selected];

  const run = useCallback(async (selection: Selection) => {
    if (jobRef.current) return;
    const chosen = selection === "full" ? tests
      : selection === "quick" ? tests.filter(t => !t.slow)
      : selection === "selected" ? tests.filter(t => t.id === selected)
      : selection === "failed" ? tests.filter(t => results[t.id] && results[t.id].status !== "PASS")
      : visible;
    if (!chosen.length) { setError("No native tests match this selection"); return; }
    const job = freshJobId();
    jobRef.current = job; setRunning(job);
    setProgress({done: 0, total: chosen.length}); setComparison(null); setError("");
    try {
      await parity.runSuite(job, chosen.map(t => t.id), selection, (event: NativeEvent) => {
        if (!mounted.current || jobRef.current !== job) return;
        if (event.type === "started") setProgress({done: 0, total: event.total});
        if (event.type === "test_finished") {
          setResults(prev => ({...prev, [event.result.id]: event.result}));
          setProgress({done: event.done, total: event.total});
        }
        if (event.type === "completed") {
          jobRef.current = null; setRunning(null);
          if (event.session_id) setSessionId(event.session_id);
          if (event.error) setError(event.error);
          if (event.canceled) setError("Canceled; completed results preserved");
        }
      });
    } catch(e) { jobRef.current = null; setRunning(null); setError(String(e)); }
  }, [tests, selected, results, visible]);

  const cancel = async () => {
    if (jobRef.current) {
      try { await parity.cancel(jobRef.current); } catch(e) { setError(String(e)); }
    }
  };
  const setBaseline = async () => {
    if (sessionId === null) return;
    try { await parity.setBaseline(sessionId); setBaselineId(sessionId); } catch(e) { setError(String(e)); }
  };
  const compare = async () => {
    if (sessionId === null || baselineId === null) return;
    try { setComparison(await parity.compare(baselineId, sessionId)); } catch(e) { setError(String(e)); }
  };
  return <div className="lab-page">
    <header className="lab-heading"><div><small>RESEARCH / C++</small><h2>Native Test Laboratory</h2>
      <p>Independent C++ process for each test; status and output from the native runner.</p></div>
      <strong>{tests.length} DISCOVERED</strong>
    </header>
    <div className="lab-actions">
      <button onClick={() => void refresh()} disabled={!!running}>Discover</button>
      <button onClick={() => void run("quick")} disabled={!!running}>Quick</button>
      <button onClick={() => void run("full")} disabled={!!running}>Full</button>
      <button onClick={() => void run("selected")} disabled={!selected || !!running}>Selected</button>
      <button onClick={() => void run("filtered")} disabled={!visible.length || !!running}>Filtered</button>
      <button onClick={() => void run("failed")} disabled={!!running}>Failures</button>
      <button onClick={() => void cancel()} disabled={!running}>Stop</button>
    </div>
    {error && <div className="lab-error" role="alert">{error}</div>}
    {progress.total > 0 && <div className="progress-line"><div style={{width: (100 * progress.done / progress.total) + "%"}}/></div>}
    <div className="lab-summary">{progress.done}/{progress.total || tests.length} completed · {
      Object.values(results).filter(r => r.status === "PASS").length} passed · {
      Object.values(results).filter(r => r.status !== "PASS").length} nonpassing</div>
    <div className="lab-filters">
      <input aria-label="Search C++ tests" placeholder="Search test IDs or source…" value={search} onChange={e => setSearch(e.target.value)} />
      <select aria-label="Test group" value={group} onChange={e => setGroup(e.target.value)}>
        {groups.map(g => <option key={g}>{g}</option>)}
      </select>
      <select aria-label="Test status filter" value={filter} onChange={e => setFilter(e.target.value)}>
        {["all","PASS","FAIL","ERROR","TIMEOUT","CANCELED","failed","not_run"].map(x => <option key={x}>{x}</option>)}
      </select>
    </div>
    <div className="lab-table" ref={scrollRef}>
      <div style={{height: virtualizer.getTotalSize(),position:"relative"}}>
        {virtualizer.getVirtualItems().map(row => {
          const test = visible[row.index], record = results[test.id];
          return <button key={test.id} className={"test-row " + (test.id === selected ? "selected" : "")}
            onClick={() => setSelected(test.id)}
            style={{position:"absolute",top:0,left:0,width:"100%",height:row.size,transform:"translateY(" + row.start + "px)"}}>
            <span className={"test-result " + (record?.status.toLowerCase() ?? "not-run")}>{record?.status ?? "NOT RUN"}</span>
            <span className="test-name">{test.id}</span>
            {test.slow && <small>slow</small>}
            <span className="test-duration">{record ? record.elapsed_ms.toFixed(2) + " ms" : "—"}</span>
          </button>;
        })}
      </div>
    </div>
    {chosen && <section className="lab-inspector">
      <div className="lab-actions"><strong>{chosen.id}</strong>
        <button onClick={() => window.dispatchEvent(new CustomEvent("studio:open-path",{
          detail:{path:chosen.source,anchor:"TEST_METHOD("+chosen.id.split(".").at(-1)+")"}
        }))}>Open C++ source</button></div>
      <div className="lab-muted">{chosen.source} · {chosen.group}{chosen.slow ? " · slow" : ""}</div>
      <pre>{result ? result.status + " · " + result.elapsed_ms.toFixed(2) + " ms\n" +
        (result.error || "No native error returned") : "Run this test to inspect its result."}</pre>
    </section>}
    <div className="lab-actions">
      <span>Current session: {sessionId ?? "—"} · Baseline: {baselineId ?? "—"}</span>
      <button disabled={sessionId === null} onClick={() => void setBaseline()}>Set baseline</button>
      <button disabled={baselineId === null || sessionId === null} onClick={() => void compare()}>Compare</button>
    </div>
    {comparison && <pre className="lab-inspector">{"New failures: " + comparison.introduced.join(", ") +
      "\nFixed: " + comparison.fixed.join(", ") +
      "\nPlatform comparable: " + comparison.comparable_platform +
      "\nSource comparable: " + comparison.same_source}</pre>}
  </div>;
}
