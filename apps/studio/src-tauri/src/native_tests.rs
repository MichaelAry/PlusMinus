//! Isolated C++ native test orchestration; zero changes to the C++ suite.
use crate::{history::{self,NativeResult},process,StudioState};
use serde::{Deserialize,Serialize};
use std::{collections::HashSet,process::Stdio,time::{Duration,Instant}};
use tauri::{AppHandle,State,Manager,ipc::Channel};
use std::sync::atomic::Ordering;
use tokio::{process::Command,task::JoinSet};
use tokio_util::sync::CancellationToken;

#[derive(Debug,Clone,Serialize,Deserialize)]
pub struct NativeCase {
    pub id:String,
    pub group:String,
    pub source:String,
    pub slow:bool,
}

#[derive(Clone,Serialize)]
#[serde(tag="type",rename_all="snake_case")]
pub enum NativeEvent {
    Started { job_id:String,total:usize },
    TestFinished { job_id:String,result:NativeResult,done:usize,total:usize },
    Completed { job_id:String,session_id:Option<i64>,passed:usize,failed:usize,canceled:bool,error:Option<String> },
}

pub async fn discover(app: &AppHandle) -> Result<Vec<NativeCase>,String> {
    let executable=process::resolve_native(app,"plusminus_native_tests")?;
    let output=tokio::time::timeout(Duration::from_secs(12),Command::new(executable)
      .arg("--list").stdin(Stdio::null()).kill_on_drop(true).output())
      .await.map_err(|_|"Native manifest discovery timed out".to_string())?
      .map_err(|e|e.to_string())?;
    if !output.status.success(){return Err(format!("Native discovery failed: {}",String::from_utf8_lossy(&output.stderr)));}
    if output.stdout.len()>2*1024*1024{return Err("Native test list exceeds limit".into());}
    let text=std::str::from_utf8(&output.stdout).map_err(|e|e.to_string())?;
    let mut result=Vec::new();let mut ids=HashSet::new();
    for line in text.lines().filter(|line|!line.trim().is_empty()){
        let row:serde_json::Value=serde_json::from_str(line).map_err(|e|e.to_string())?;
        if row["type"]!="test"{return Err("Unexpected native manifest row".into());}
        let item:NativeCase=serde_json::from_value(row).map_err(|e|e.to_string())?;
        if item.id.is_empty()||!ids.insert(item.id.clone()){return Err("Duplicate/invalid test id".into());}
        result.push(item);
    }
    if result.is_empty(){return Err("Native test list is empty".into());}
    Ok(result)
}

fn failed(case:&NativeCase,status:&str,error:String,elapsed:f64) -> NativeResult {
    NativeResult{id:case.id.clone(),group:case.group.clone(),source:case.source.clone(),
      slow:case.slow,status:status.into(),error,elapsed_ms:elapsed,test_ms:None,
      cpu_ms:None,peak_rss_mb:None}
}

async fn run_single(path:&std::path::Path,case:NativeCase,timeout_sec:u64,
    token:CancellationToken)->NativeResult{
    let start=Instant::now();
    if token.is_cancelled(){return failed(&case,"CANCELED","Canceled".into(),0.0);}
    let child=Command::new(path).arg("--run").arg(&case.id)
       .stdin(Stdio::null()).stdout(Stdio::piped()).stderr(Stdio::piped())
       .kill_on_drop(true).spawn();
    let child=match child{Ok(ch)=>ch,Err(e)=>return failed(&case,"ERROR",e.to_string(),0.0)};
    let output=tokio::select!{
      _=token.cancelled()=>Err("CANCELED"),
      r=tokio::time::timeout(Duration::from_secs(timeout_sec),child.wait_with_output())=>{
        match r {Ok(x)=>x.map_err(|_|"ERROR"),Err(_)=>Err("TIMEOUT")}
      }
    };
    let elapsed=start.elapsed().as_secs_f64()*1000.0;
    let output=match output{
      Ok(x)=>x,
      Err("CANCELED")=>return failed(&case,"CANCELED","Execution canceled".into(),elapsed),
      Err("TIMEOUT")=>return failed(&case,"TIMEOUT",format!("Time limit exceeded ({timeout_sec}s)"),elapsed),
      Err(_)=>return failed(&case,"ERROR","Native process failed".into(),elapsed)
    };
    if output.stdout.len()>256*1024||output.stderr.len()>128*1024{
        return failed(&case,"ERROR","Native test output exceeded limit".into(),elapsed);
    }
    let text=String::from_utf8_lossy(&output.stdout);
    let record=text.lines().filter(|l|!l.trim().is_empty())
      .find_map(|l|serde_json::from_str::<serde_json::Value>(l).ok()
       .filter(|v|v["type"]=="result"));
    let Some(data)=record else {
        return failed(&case,"ERROR",format!("No native JSON result: {}",String::from_utf8_lossy(&output.stderr)),elapsed);
    };
    if data["id"]!=case.id||!matches!(data["status"].as_str(),Some("PASS"|"FAIL")){
        return failed(&case,"ERROR","Native result id/status mismatch".into(),elapsed);
    }
    let status=data["status"].as_str().unwrap_or("ERROR");
    let expected_exit=if status=="PASS"{0}else{1};
    if output.status.code()!=Some(expected_exit){
        return failed(&case,"ERROR",format!("Unexpected process exit: {:?}",output.status.code()),elapsed);
    }
    let test_ms=data["elapsed_ms"].as_f64();
    NativeResult{id:case.id,group:case.group,source:case.source,slow:case.slow,
      status:status.into(),error:data["error"].as_str().unwrap_or("").chars().take(4000).collect(),
      elapsed_ms:elapsed,test_ms,cpu_ms:None,peak_rss_mb:None}
}

pub async fn run_suite(app:AppHandle,job_id:String,cases:Vec<NativeCase>,
  label:String,on_event:Channel<NativeEvent>,token:CancellationToken,
  root:Option<std::path::PathBuf>){
    let _=on_event.send(NativeEvent::Started{job_id:job_id.clone(),total:cases.len()});
    let binary=match process::resolve_native(&app,"plusminus_native_tests"){
      Ok(p)=>p,
      Err(e)=>{
        app.state::<StudioState>().tasks.complete(&job_id,None,false,Some(e.clone()));
        let _=on_event.send(NativeEvent::Completed{job_id,session_id:None,passed:0,failed:0,canceled:false,error:Some(e)});
        return;
      }
    };
    let total=cases.len();let mut pending=cases.into_iter();
    let mut jobs=JoinSet::new();let mut results=Vec::new();
    let mut canceled=false;
    loop {
        while jobs.len()<2 && !token.is_cancelled() {
            let Some(case)=pending.next() else {break};
            let path=binary.clone();let child_token=token.clone();
            let seconds=if case.slow{180}else{20};
            jobs.spawn(async move{run_single(&path,case,seconds,child_token).await});
        }
        if jobs.is_empty(){break;}
        tokio::select!{
            _=token.cancelled()=>{
                canceled=true;
                jobs.abort_all();
                // Aborting drops the wait_with_output future, and
                // kill_on_drop terminates the individual test process.
                while jobs.join_next().await.is_some(){}
                break;
            }
            item=jobs.join_next()=>{
                if let Some(Ok(result))=item{
                    let registry=app.state::<StudioState>();
                    let _=registry.tasks.advance(&job_id,result.status=="PASS");
                    let done=results.len()+1;
                    let _=on_event.send(NativeEvent::TestFinished{job_id:job_id.clone(),result:result.clone(),done,total});
                    results.push(result);
                }
            }
        }
    }
    let passed=results.iter().filter(|r|r.status=="PASS").count();
    let failed=results.len()-passed;
    let storage_results=results.clone();
    let saved=if storage_results.is_empty(){Ok(None)}else{
        tauri::async_runtime::spawn_blocking(move||
          history::save_native_session(&label,&storage_results,root.as_deref()).map(Some))
          .await.map_err(|e|e.to_string()).and_then(|r|r)
    };
    let (session_id,error)=match saved {Ok(id)=>(id,None),Err(e)=>(None,Some(e))};
    app.state::<StudioState>().tasks.complete(&job_id,session_id,canceled,error.clone());
    let _=on_event.send(NativeEvent::Completed{job_id,session_id,passed,failed,canceled,error});
}

#[tauri::command]
pub async fn list_native_tests(app:AppHandle)->Result<Vec<NativeCase>,String>{
    if app.state::<StudioState>().source_stale.load(Ordering::SeqCst) {
        return Err("C++ source edited: rebuild before discovering tests".into());
    }
    discover(&app).await
}

#[tauri::command]
pub async fn start_native_suite(app:AppHandle,state:State<'_,StudioState>,
  job_id:String,test_ids:Vec<String>,label:String,
  on_event:Channel<NativeEvent>)->Result<String,String>{
    if state.source_stale.load(Ordering::SeqCst) {
        return Err("C++ source edited: rebuild before running tests".into());
    }
    if job_id.len()<8||job_id.len()>80 || !job_id.bytes().all(|b|b.is_ascii_alphanumeric()||b==b'-'){
        return Err("Invalid job ID".into());
    }
    if test_ids.is_empty()||test_ids.len()>500{return Err("Select 1..500 tests".into());}
    let manifest=discover(&app).await?;
    let ids:HashSet<String>=test_ids.into_iter().collect();
    if !ids.iter().all(|id|manifest.iter().any(|c|c.id==*id)){
        return Err("Unknown test identifier".into());
    }
    let cases:Vec<_>=manifest.into_iter().filter(|c|ids.contains(&c.id)).collect();
    let root=state.root.lock().map_err(|e|e.to_string())?.clone();
    let token=state.tasks.register(&job_id,"native-tests",cases.len())?;
    let return_id=job_id.clone();
    tokio::spawn(async move {
        run_suite(app,job_id,cases,label,on_event,token,root).await;
    });
    Ok(return_id)
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test] fn record_is_explicitly_unmeasured(){
      let case=NativeCase{id:"X.Y".into(),group:"X".into(),source:"test.cpp".into(),slow:false};
      let r=failed(&case,"TIMEOUT","Timed out".into(),30.0);
      assert!(r.cpu_ms.is_none()&&r.peak_rss_mb.is_none());
    }
}
