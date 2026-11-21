import { describe, expect, it } from "vitest";
import { useStudio } from "./studio";

describe("document lifecycle", () => {
  it("retains dirty state if edits occur during an asynchronous save", () => {
    useStudio.getState().open({ path: "race.pm", source: "initial", digest: "old" });
    useStudio.getState().edit("race.pm", "first");
    useStudio.getState().edit("race.pm", "second");
    useStudio.getState().saved("race.pm", {
      path: "race.pm", source: "first", digest: "hash-of-first",
    });
    const doc = useStudio.getState().documents.find((d) => d.id === "race.pm");
    expect(doc?.source).toBe("second");
    expect(doc?.dirty).toBe(true);
    expect(doc?.digest).toBe("hash-of-first");
  });

  it("provides a new editor identity when changing the workspace", () => {
    useStudio.getState().setWorkspace("first", []);
    const before = useStudio.getState().activeId;
    useStudio.getState().edit(before, "modified");
    useStudio.getState().setWorkspace("second", []);
    const state = useStudio.getState();
    expect(state.activeId).not.toBe(before);
    expect(state.documents[0].source).not.toBe("modified");
    expect(state.documents[0].dirty).toBe(false);
  });
});

describe("multiple split panes sharing one source model",()=>{
  it("does not notify subscribers on duplicate or unknown source changes",()=>{
    useStudio.getState().setWorkspace("model-lifecycle",[]);
    useStudio.getState().open({path:"shared.pm",source:"print(1);",digest:"x"});
    let events=0;
    const unsub=useStudio.subscribe(()=>{events++;});
    const before=useStudio.getState().documents;
    useStudio.getState().edit("shared.pm","print(1);");
    useStudio.getState().edit("missing.pm","other");
    expect(useStudio.getState().documents).toBe(before);
    expect(events).toBe(0);
    useStudio.getState().edit("shared.pm","print(2);");
    expect(events).toBe(1);
    unsub();
  });
});

describe("execution diagnostics source identity",()=>{
  it("keeps native results associated with the executed snapshot, not a later tab",()=>{
    useStudio.getState().setWorkspace("diagnostics",[]);
    useStudio.getState().open({path:"original.pm",source:"print(1);",digest:"a"});
    const report={
      job_id:"job-correct",exit_code:1,wall_ms:0,stderr:"",history_error:null,
      report:{
        ok:false,output:"",result:"",variables:"",bytecode:"",
        error:"compile: invalid",diagnostics:[{severity:"error",phase:"compile",message:"invalid",line:1,column:1}],
        trace:[],trace_truncated:false,
        metrics:{compile_ms:0,execute_ms:null,program_instructions:0,executed_instructions:0,opcode_hits:{}}
      }
    };
    useStudio.getState().started("job-correct","original.pm","print(1);");
    useStudio.getState().open({path:"other.pm",source:"print(2);",digest:"b"});
    useStudio.getState().finished("wrong-job",report,null);
    expect(useStudio.getState().runningJob).toBe("job-correct");
    useStudio.getState().finished("job-correct",report,null);
    expect(useStudio.getState().reportedSource).toEqual({id:"original.pm",source:"print(1);"});
    expect(useStudio.getState().activeId).toBe("other.pm");
    useStudio.getState().edit("original.pm","print(3);");
    expect(useStudio.getState().reportedSource?.source).toBe("print(1);");
  });
});
