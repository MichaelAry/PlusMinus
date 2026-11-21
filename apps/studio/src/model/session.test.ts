import { describe, expect, it } from "vitest";
import { MAX_SESSION_TABS, parseSession, snapshotSession, validSessionPath } from "./session";

describe("workspace clean-tab restoration",()=>{
  it("retains order and active document, omitting unsaved source",()=>{
    const documents=[{path:""},{path:"a.pm",source:"secret"},{path:"lib/b.pm"},{path:"a.pm"}];
    const snapshot=snapshotSession(documents,"a.pm");
    expect(snapshot).toEqual({version:1,paths:["a.pm","lib/b.pm"],activePath:"a.pm"});
    expect(JSON.stringify(snapshot)).not.toContain("secret");
    expect(parseSession(JSON.stringify(snapshot))).toEqual(snapshot);
  });
  it("rejects corrupt, escaping and unsupported paths",()=>{
    for(const path of ["../private.pm","/secret.pm","dir\\a.pm","./test.pm","a.txt","a//b.pm"])expect(validSessionPath(path)).toBe(false);
    expect(parseSession("{")).toEqual({version:1,paths:[],activePath:null});
    expect(parseSession(JSON.stringify({version:20,paths:["a.pm"]})).paths).toEqual([]);
    expect(parseSession(JSON.stringify({version:1,paths:["../secret.pm","a.pm"],activePath:"../secret.pm"})).activePath).toBeNull();
  });
  it("deduplicates and caps a large snapshot",()=>{
    const paths=Array.from({length:150},(_,i)=>"file"+i+".pm");
    const result=parseSession(JSON.stringify({version:1,paths,activePath:"file149.pm"}));
    expect(result.paths).toHaveLength(MAX_SESSION_TABS);
    expect(result.activePath).toBeNull();
  });
});
