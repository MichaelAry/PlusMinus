import { useEffect, useRef, useState } from "react";
import { native } from "../../api/native";
import { parity, freshJobId } from "../../api/parity";
import { useStudio } from "../../model/studio";

export interface SourceTest {
  name:string;source:string;kind:"output"|"result"|"bytecode_contains"|"error_contains";
  expected:string;mode:"run"|"compile"|"profile"|"trace";expect_ok:boolean;timeout:number;
}
const builtin:SourceTest[]=[
  {name:"Arithmetic precedence",source:"print(2 + 3 * 4);",mode:"run",kind:"output",expected:"14\n",expect_ok:true,timeout:5},
  {name:"Variable assignment",source:"x = 10; print(x);",mode:"run",kind:"output",expected:"10\n",expect_ok:true,timeout:5},
  {name:"Compilation and bytecode",source:"print(2);",mode:"compile",kind:"bytecode_contains",expected:"Call",expect_ok:true,timeout:5},
  {name:"Syntax error detected",source:"if (1) {",mode:"run",kind:"error_contains",expected:"compile:",expect_ok:false,timeout:5},
  {name:"Infinite loop timeout",source:"while (1) {}",mode:"run",kind:"error_contains",expected:"timed out",expect_ok:false,timeout:0.2},
];
function judge(test:SourceTest,actual:{ok:boolean;output:string;result:string;bytecode:string;error:string}) {
  if(actual.ok!==test.expect_ok)return {pass:false,detail:"Unexpected execution state: "+actual.error};
  const kind=test.kind.replace("_contains","") as "output"|"result"|"bytecode"|"error";
  const got=actual[kind],expected=test.expected;
  const pass=test.kind.endsWith("_contains")?got.includes(expected):
    got.replace(/\r\n/g,"\n")===expected.replace(/\r\n/g,"\n");
  return {pass,detail:pass?"OK":"Expected: "+JSON.stringify(expected)+"\nActual: "+JSON.stringify(got)};
}

export function SourceTestsPanel(){
  const docs=useStudio(s=>s.documents),activeId=useStudio(s=>s.activeId);
  const active=docs.find(d=>d.id===activeId);
  const [user,setUser]=useState<SourceTest[]>([]);
  const [revision,setRevision]=useState("");
  const [selected,setSelected]=useState(0);
  const [running,setRunning]=useState(false);
  const [outcomes,setOutcomes]=useState<Record<string,{pass:boolean;detail:string;ms:number}>>({});
  const [error,setError]=useState("");
  const job=useRef<string|null>(null),cancel=useRef(false);
  const all=[...builtin,...user];
  const refresh=async()=>{
    try{
      const bundle=await parity.userTests();
      setUser(bundle.cases as SourceTest[]);setRevision(bundle.revision);setError("");
    }catch(e){setError(String(e));}
  };
  useEffect(()=>{void refresh();},[]);
  const edit=async()=>{
    if(!active){setError("Open a PlusMinus document to define a test");return;}
    const name=window.prompt("New test name","Custom source test");
    if(!name)return;
    const expected=window.prompt("Exact expected stdout (newlines preserved by the dialog)", "");
    if(expected===null)return;
    const updated=[...user,{name,source:active.source,kind:"output" as const,expected,
      mode:"run" as const,expect_ok:true,timeout:5}];
    try{const bundle=await parity.saveUserTests(updated,revision);setUser(bundle.cases as SourceTest[]);setRevision(bundle.revision);}
    catch(e){setError(String(e));}
  };
  const erase=async()=>{
    if(selected<builtin.length)return;
    const index=selected-builtin.length;
    if(!window.confirm("Delete this Studio 5 user test?"))return;
    try{
      const bundle=await parity.saveUserTests(user.filter((_,i)=>i!==index),revision);
      setUser(bundle.cases as SourceTest[]);setRevision(bundle.revision);setSelected(0);
    }catch(e){setError(String(e));}
  };
  const importTests=async()=>{
    try{
      const bundle=await parity.importUserTests(revision);
      setUser(bundle.cases as SourceTest[]);setRevision(bundle.revision);
    }catch(e){setError(String(e));}
  };
  const exportTests=async()=>{
    try{const path=await parity.exportUserTests();setError("Exported user tests: "+path);}
    catch(e){setError(String(e));}
  };
  const execute=async(allTests:boolean)=>{
    if(running)return;
    const entries=allTests?all:[all[selected]].filter(Boolean);
    if(!entries.length)return;
    setRunning(true);cancel.current=false;setError("");
    const next:Record<string,{pass:boolean;detail:string;ms:number}>={...outcomes};
    try{
      for(const test of entries){
        if(cancel.current)break;
        const id=freshJobId();job.current=id;
        const start=performance.now();
        let actual:{ok:boolean;output:string;result:string;bytecode:string;error:string};
        try{
          const result=await native.runSource(id,test.source,test.mode,Math.round(test.timeout*1000));
          actual=result.report;
        }catch(e){
          actual={ok:false,output:"",result:"",bytecode:"",error:String(e)};
        }
        const verdict=judge(test,actual);
        next[test.name]= {...verdict,ms:performance.now()-start};
        setOutcomes({...next});
      }
    }finally{job.current=null;setRunning(false);}
  };
  const stop=async()=>{
    cancel.current=true;
    if(job.current)await parity.cancel(job.current).catch(e=>setError(String(e)));
  };
  return <div className="lab-page">
    <header className="lab-heading"><div><small>RESEARCH / REGRESSION</small><h2>PlusMinus Source Tests</h2>
      <p>Built-in Studio 4 test cases and user-defined cases; each uses the unchanged C++ runner.</p></div>
      <strong>{all.length} CASES</strong></header>
    <div className="lab-actions">
      <button onClick={()=>void execute(true)} disabled={running}>Run all</button>
      <button onClick={()=>void execute(false)} disabled={running}>Run selected</button>
      <button onClick={()=>void stop()} disabled={!running}>Stop</button>
      <button onClick={()=>void edit()}>Add from editor</button>
      <button onClick={()=>void erase()} disabled={selected<builtin.length}>Remove user case</button>
      <button onClick={()=>void importTests()}>Import JSON</button>
      <button onClick={()=>void exportTests()}>Export JSON</button>
      <button onClick={()=>void refresh()}>Reload</button>
    </div>
    {error&&<div className="lab-error" role="status">{error}</div>}
    <div className="lab-two-col"><div className="lab-mini-scroll">
      {all.map((test,i)=><button key={i} className={"session-row "+(selected===i?"selected":"")}
        onClick={()=>setSelected(i)}>
        <span className={"test-result "+(outcomes[test.name]?.pass===true?"pass":outcomes[test.name]?"fail":"not-run")}>
          {outcomes[test.name]?(outcomes[test.name].pass?"PASS":"FAIL"):"NOT RUN"}</span>
        <span>{test.name}</span><small>{i<builtin.length?"BUILT-IN":"USER"}</small>
      </button>)}
    </div><section>
      <h3>{all[selected]?.name??"No test selected"}</h3>
      <p className="lab-muted">Mode: {all[selected]?.mode} · {all[selected]?.kind}</p>
      <pre className="lab-inspector">{all[selected]?.source}</pre>
      <pre className="lab-inspector">Expected: {JSON.stringify(all[selected]?.expected??"")}</pre>
      {all[selected]&&outcomes[all[selected].name]&&
        <pre className="lab-inspector">{outcomes[all[selected].name].detail}</pre>}
    </section></div>
    <p className="lab-muted">User definitions copied from the original Studio 4 JSON file into user_tests-v5.json. The original is never overwritten.</p>
  </div>;
}
