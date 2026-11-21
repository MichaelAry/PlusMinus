//! Read-only Git metadata for the selected workspace. No generic user command.
use serde::Serialize;
use std::{path::Path,process::Stdio,time::Duration};
use tokio::process::Command;

#[derive(Serialize)]
pub struct GitSummary {
    pub available:bool,pub branch:String,pub sha:String,pub changes:String,
    pub diff:String,pub commits:String,pub dirty:bool,pub error:String,
}

async fn fixed_git(root:&Path,args:&[&str])->Result<String,String>{
  let r=tokio::time::timeout(Duration::from_secs(5),
    Command::new("git").arg("-C").arg(root).args(args).stdin(Stdio::null())
      .kill_on_drop(true).output()
  ).await.map_err(|_|"Git command timed out".to_string())?
   .map_err(|e|e.to_string())?;
  if r.stdout.len()>512*1024||r.stderr.len()>128*1024 {return Err("Git output too large".into());}
  if !r.status.success(){return Err(String::from_utf8_lossy(&r.stderr).to_string());}
  Ok(String::from_utf8_lossy(&r.stdout).trim_end().to_string())
}

pub async fn summary(root:&Path)->GitSummary{
  let branch=match fixed_git(root,&["branch","--show-current"]).await {
    Ok(branch)=>branch,Err(e)=>return GitSummary{
      available:false,branch:String::new(),sha:String::new(),changes:String::new(),
      diff:String::new(),commits:String::new(),dirty:false,error:e}
  };
  let sha=fixed_git(root,&["rev-parse","--short","HEAD"]).await.unwrap_or_default();
  let changes=fixed_git(root,&["status","--short"]).await.unwrap_or_default();
  let diff=fixed_git(root,&["diff","--stat"]).await.unwrap_or_default();
  let commits=fixed_git(root,&["log","-6","--date=short","--pretty=format:%h %ad %s"])
    .await.unwrap_or_default();
  GitSummary{available:true,branch,sha,dirty:!changes.is_empty(),
    changes,diff,commits,error:String::new()}
}
