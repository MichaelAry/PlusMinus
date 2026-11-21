import { useEffect, useRef, useState } from "react";
import { native } from "../../api/native";
import { benchmarkStats, freshJobId } from "../../api/parity";
import type { RunResponse } from "../../api/contracts";
import { useStudio } from "../../model/studio";

export function ProfilerPanel() {
  const activeId=useStudio(s=>s.activeId);
  const documents=useStudio(s=>s.documents);
  const lastReport=useStudio(s=>s.response);
  const active=documents.find(d=>d.id===activeId);
  const [runs,setRuns]=useState(10);
  const [warm,setWarm]=useState(true);
  const [samples,setSamples]=useState<number[]>([]);
  const [vmSamples,setVmSamples]=useState<number[]>([]);
  const [error,setError]=useState("");
  const [busy,setBusy]=useState(false);
  const [latest,setLatest]=useState<RunResponse|null>(null);
  const stopRef=useRef(false);
  const pendingJob=useRef<string|null>(null);
  const chart=useRef<HTMLDivElement>(null);

  useEffect(()=>{
    if(!chart.current||samples.length===0)return;
    let disposed=false;
    let instance:import("echarts").ECharts|null=null;
    void import("echarts").then(echarts=>{
      if(disposed||!chart.current)return;
      instance=echarts.init(chart.current,null,{renderer:"canvas"});
      instance.setOption({
        backgroundColor:"transparent",
        textStyle:{color:"#c8d0d6"},
        tooltip:{trigger:"axis"},
        xAxis:{type:"category",data:samples.map((_,i)=>i+1),axisLabel:{color:"#a4aab2"}},
        yAxis:{type:"value",name:"ms",axisLabel:{color:"#a4aab2"}},
        series:[{type:"line",smooth:false,showSymbol:true,data:samples,name:"End-to-end"}],
      });
    }).catch(e=>setError(String(e)));
    return ()=>{disposed=true;instance?.dispose();};
  },[samples]);

  async function benchmark(){
    if(busy||!active)return;
    setBusy(true);stopRef.current=false;setError("");setSamples([]);setVmSamples([]);
    const collected:number[]=[],internal:number[]=[];
    try {
      const runOnce=async()=>{
        const id=freshJobId();pendingJob.current=id;
        const report=await native.runSource(id,active.source,"run",10000);
        pendingJob.current=null;
        if(!report.report.ok)throw Error(report.report.error||"Native execution failed");
        setLatest(report);
        return report;
      };
      if(warm)await runOnce();
      for(let i=0;i<runs;i++){
        if(stopRef.current)break;
        const report=await runOnce();
        collected.push(report.wall_ms);
        if(report.report.metrics.execute_ms!==null)internal.push(report.report.metrics.execute_ms);
        setSamples([...collected]);setVmSamples([...internal]);
      }
    }catch(e){setError(String(e));}
    finally{pendingJob.current=null;setBusy(false);}
  }
  async function cancel(){
    stopRef.current=true;
    if(pendingJob.current)await native.cancelRun(pendingJob.current).catch(e=>setError(String(e)));
  }
  const stats=benchmarkStats(samples);
  const prof=latest??lastReport;
  const hits=Object.entries(prof?.report.metrics.opcode_hits??{}).sort((a,b)=>b[1]-a[1]).slice(0,25);
  return <div className="lab-page">
    <header className="lab-heading"><div><small>RESEARCH / PERFORMANCE</small><h2>Native Profiler</h2>
      <p>VM counters from C++; repeated native process timings (not CPU samples).</p></div></header>
    <div className="lab-actions">
      <label>Iterations <input type="number" min={1} max={80} value={runs} onChange={e=>setRuns(Math.max(1,Math.min(80,Number(e.target.value))))}/></label>
      <label><input type="checkbox" checked={warm} onChange={e=>setWarm(e.target.checked)}/> Warm-up</label>
      <button onClick={()=>void benchmark()} disabled={busy}>Run benchmark</button>
      <button onClick={()=>void cancel()} disabled={!busy}>Stop</button>
    </div>
    {error&&<div className="lab-error" role="alert">{error}</div>}
    <div className="metrics-grid">
      <Metric label="Samples" value={String(samples.length)}/>
      <Metric label="Mean wall" value={stats?stats.mean.toFixed(2)+" ms":"—"}/>
      <Metric label="Median wall" value={stats?stats.median.toFixed(2)+" ms":"—"}/>
      <Metric label="p95 wall" value={stats?stats.p95.toFixed(2)+" ms":"—"}/>
      <Metric label="Mean VM execute" value={vmSamples.length?(vmSamples.reduce((a,b)=>a+b,0)/vmSamples.length).toFixed(3)+" ms":"not measured"}/>
      <Metric label="CPU / RSS" value="not measured"/>
    </div>
    <div ref={chart} className="lab-chart" role="img" aria-label="Execution time by benchmark iteration"/>
    <h3>Native opcode counters</h3>
    {hits.length ? <div className="lab-mini-scroll">{hits.map(([op,count])=><div className="session-row" key={op}><strong>{op}</strong><span>{count}</span></div>)}</div>
      : <p className="lab-muted">Run Profile/Trace in the editor to collect native VM counters.</p>}
    <p className="lab-muted">Metrics describe the unchanged runner. OS-level CPU/RSS sampling is not yet integrated.</p>
  </div>;
}
function Metric({label,value}:{label:string;value:string}){
 return <div className="metric"><small>{label}</small><strong>{value}</strong></div>;
}
