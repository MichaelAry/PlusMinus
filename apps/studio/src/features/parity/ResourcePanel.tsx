import { useEffect, useState } from "react";
import { useEChart } from "./useEChart";
import { parity, type ResourceSnapshot } from "../../api/parity";

export function ResourcePanel(){
  const [samples,setSamples]=useState<ResourceSnapshot[]>([]);
  const [error,setError]=useState("");

  useEffect(()=>{
    let active=true;
    const sample=async()=>{
      try{
        const value=await parity.resources();
        if(active){setSamples(old=>[...old.slice(-159),value]);setError("");}
      }catch(e){if(active)setError(String(e));}
    };
    void sample();
    const timer=setInterval(()=>void sample(),1000);
    return()=>{active=false;clearInterval(timer);};
  },[]);
  const chart=useEChart(samples.length?{
    textStyle:{color:"#cbd2d8"},tooltip:{trigger:"axis"},
    xAxis:{type:"category",data:samples.map((_,i)=>i+1),axisLabel:{color:"#a6b0b8"}},
    yAxis:[{type:"value",name:"RSS MB",axisLabel:{color:"#a6b0b8"}},
      {type:"value",name:"CPU %",axisLabel:{color:"#a6b0b8"}}],
    series:[
      {type:"line",name:"Rust RSS MB",showSymbol:false,data:samples.map(s=>s.rss_mb)},
      {type:"line",name:"Rust CPU %",showSymbol:false,yAxisIndex:1,data:samples.map(s=>s.cpu_percent)},
    ],
  }:null);
  const last=samples.at(-1);
  return <div className="lab-page">
    <header className="lab-heading"><div><small>RESEARCH / TELEMETRY</small><h2>Process Resources</h2>
      <p>Measured Rust process sampling every 1 second. WebView and native VM child processes not included.</p></div></header>
    {error&&<div className="lab-error" role="alert">{error}</div>}
    <div className="metrics-grid">
      <div className="metric"><small>Rust backend RSS</small><strong>{last?last.rss_mb.toFixed(2)+" MiB":"—"}</strong></div>
      <div className="metric"><small>Rust backend CPU</small><strong>{last?.cpu_percent==null?"not measured":last.cpu_percent.toFixed(2)+" %"}</strong></div>
      <div className="metric"><small>Sample count</small><strong>{samples.length}</strong></div>
    </div>
    <div className="lab-chart" ref={chart} role="img" aria-label="Measured backend memory and CPU graph"/>
    <p className="lab-muted">The total application memory footprint needs a later OS process-tree monitor. CPU usage may exceed 100% on multicore machines.</p>
  </div>;
}
