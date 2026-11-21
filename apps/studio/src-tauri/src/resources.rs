//! Observed Rust desktop-process resource samples.
//! This intentionally does not claim to include WebView or VM child memory.
use serde::Serialize;
use sysinfo::{get_current_pid,ProcessesToUpdate,System};

#[derive(Default)]
pub struct Sampler {
    system:System,
    initialized:bool,
}
#[derive(Serialize)]
pub struct Sample {
    pub process:String,
    pub pid:u32,
    pub rss_mb:f64,
    pub cpu_percent:Option<f32>,
}
pub fn snapshot(sampler:&mut Sampler)->Result<Sample,String>{
    let pid=get_current_pid().map_err(|e|e.to_string())?;
    sampler.system.refresh_processes(ProcessesToUpdate::Some(&[pid]),true);
    let process=sampler.system.process(pid).ok_or("Rust desktop process unavailable")?;
    let cpu=if sampler.initialized{Some(process.cpu_usage())}else{None};
    sampler.initialized=true;
    Ok(Sample{
      process:"Tauri/Rust backend (excludes WebView and VM children)".into(),
      pid:pid.as_u32(),
      rss_mb:process.memory() as f64 / 1048576.0,
      cpu_percent:cpu,
    })
}
