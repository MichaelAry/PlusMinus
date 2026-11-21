import { useEffect, useMemo, useRef, useState } from "react";
import { useStudio } from "../../model/studio";
import { bytecodeGraph, callGraph, type LanguageGraph } from "../../model/graphs";
import { analyzeSource } from "../../model/sourceMetrics";

export function GraphPanel(){
  const activeId=useStudio(s=>s.activeId);
  const documents=useStudio(s=>s.documents);
  const response=useStudio(s=>s.response);
  const source=documents.find(d=>d.id===activeId)?.source??"";
  const [mode,setMode]=useState<"bytecode"|"calls">("bytecode");
  const canvas=useRef<HTMLDivElement>(null);
  const [error,setError]=useState("");
  const sourceMetrics=useMemo(()=>analyzeSource(source),[source]);
  const computed:LanguageGraph=useMemo(()=>mode==="bytecode"?bytecodeGraph(response?.report.bytecode??""):callGraph(source),
    [mode,response?.report.bytecode,source]);
  const [graph,setGraph]=useState(computed);
  useEffect(()=>{
    const timer=setTimeout(()=>setGraph(computed),300);
    return()=>clearTimeout(timer);
  },[computed]);
  useEffect(()=>{
    if(!canvas.current)return;
    let disposed=false;
    let cy:import("cytoscape").Core|null=null;
    void import("cytoscape").then(module=>{
      if(disposed||!canvas.current)return;
      cy=module.default({
        container:canvas.current,
        elements:[
          ...graph.nodes.map(n=>({data:{id:n.id,label:n.label}})),
          ...graph.edges.map((e,i)=>({data:{id:"edge-"+i,source:e.source,target:e.target,label:e.label}})),
        ],
        layout:{name:"breadthfirst",directed:true,spacingFactor:1.1},
        style:[
          {selector:"node",style:{"background-color":"#48515b","label":"data(label)",
            "color":"#d7dde3","text-valign":"center","text-halign":"right",
            "font-size":11,"text-margin-x":5,"width":20,"height":20}},
          {selector:"edge",style:{"width":1.5,"line-color":"#737f8b",
            "target-arrow-color":"#737f8b","target-arrow-shape":"triangle",
            "curve-style":"bezier","label":"data(label)","font-size":8,"color":"#b1bac1"}},
        ],
      });
      cy.fit(undefined,25);
    }).catch(e=>setError(String(e)));
    return ()=>{disposed=true;cy?.destroy();};
  },[graph]);
  return <div className="lab-page">
    <header className="lab-heading"><div><small>RESEARCH / COMPILER</small><h2>Compiler Explorer</h2>
      <p>CFG from actual bytecode; call graph is heuristic source analysis, not an AST.</p></div></header>
    <div className="lab-actions"><button onClick={()=>setMode("bytecode")} aria-pressed={mode==="bytecode"}>Bytecode CFG</button>
      <button onClick={()=>setMode("calls")} aria-pressed={mode==="calls"}>Call graph</button>
      <span>{graph.nodes.length} nodes · {graph.edges.length} edges · {graph.method}</span></div>
    {error&&<div className="lab-error">{error}</div>}
    {graph.truncated&&<div className="lab-error">Graph truncated to first 200 bytecode instructions.</div>}
    {!graph.nodes.length?<p className="lab-muted">Compile or profile a PlusMinus program to display bytecode flow.</p>:null}
    <div ref={canvas} className="lab-graph" role="img" aria-label={mode==="bytecode"?"Bytecode control flow":"Function call graph"} />
    <h3>Lexical source metrics</h3>
    <div className="metrics-grid">
      {([
        ["Code lines",sourceMetrics.code_lines],["Functions",sourceMetrics.functions],
        ["Variables",sourceMetrics.variables],["Branches",sourceMetrics.branches],
        ["Loops",sourceMetrics.loops],["Max nesting",sourceMetrics.max_nesting],
        ["Complexity estimate",sourceMetrics.complexity_estimate],["Comments",sourceMetrics.comments],
      ] as Array<[string,number]>).map(([name,value])=>
        <div className="metric" key={name}><small>{name}</small><strong>{value}</strong></div>)}
    </div>
    <p className="lab-muted">{sourceMetrics.method}</p>
    {sourceMetrics.warnings.map(w=><div key={w} className="lab-error">{w}</div>)}
    <h3>Source / bytecode data</h3>
    <pre className="lab-mini-scroll">{mode==="bytecode"?(response?.report.bytecode||"No bytecode report yet."):source}</pre>
  </div>;
}
