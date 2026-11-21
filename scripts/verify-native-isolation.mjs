#!/usr/bin/env node
// Exercise all 225 unmodified C++ test cases as independent OS processes.
// This supplements ctest's quick suite and verifies the --run JSONL contract.
import {spawnSync} from "node:child_process";
import {existsSync} from "node:fs";
import {resolve,join} from "node:path";
import {fileURLToPath} from "node:url";

const repo=resolve(fileURLToPath(new URL("../",import.meta.url)));
const params=process.argv.slice(2);
const index=params.indexOf("--build-dir");
const root=resolve(repo,index>=0?params[index+1]:"build/studio5");
const extension=process.platform==="win32"?".exe":"";
const binary=[join(root,"plusminus_native_tests"+extension),
              join(root,"Release","plusminus_native_tests"+extension),
              join(root,"Debug","plusminus_native_tests"+extension)].find(existsSync);
if(!binary)throw Error("C++ test executable missing under "+root);
function invoke(args,timeout) {
  const result=spawnSync(binary,args,{encoding:"utf8",timeout,maxBuffer:256*1024});
  if(result.error)throw Error(args.join(" ")+": "+result.error.message);
  return result;
}
const listing=invoke(["--list"],12_000);
if(listing.status!==0)throw Error("Native manifest discovery failed: "+listing.stderr);
const cases=listing.stdout.trim().split(/\r?\n/).filter(Boolean).map(x=>JSON.parse(x));
if(cases.length!==225 || new Set(cases.map(x=>x.id)).size!==225 ||
   cases.some(x=>x.type!=="test" || typeof x.slow!=="boolean"))
  throw Error("Expected exactly 225 distinct, typed native test cases");
const started=Date.now();
const failures=[];
let completed=0;
for(const test of cases){
  try {
    const result=invoke(["--run",test.id],test.slow?180_000:20_000);
    const rows=result.stdout.trim().split(/\r?\n/).filter(Boolean).map(x=>JSON.parse(x));
    if(rows.length!==1 || rows[0].type!=="result" || rows[0].id!==test.id ||
       rows[0].status!=="PASS" || result.status!==0)
      throw Error("Native result/exit mismatch: "+JSON.stringify(rows[0])+
                  ", exit="+result.status+", stderr="+result.stderr.slice(0,500));
  } catch(error){failures.push({id:test.id,detail:String(error)});}
  completed++;
  if(completed%25===0 || completed===cases.length){
    console.log("Isolated native tests: "+completed+"/"+cases.length+
      " (failed "+failures.length+", "+Math.round((Date.now()-started)/1000)+" s)");
  }
}
if(failures.length){
  for(const f of failures)console.error("FAIL "+f.id+": "+f.detail);
  throw Error(failures.length+" of 225 independent native test processes failed");
}
console.log("PASS: 225 of 225 native tests in independent processes, each with an exact JSONL result");
