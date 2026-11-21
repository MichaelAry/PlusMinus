//! Best-effort descendant termination for native C++ sidecars.
//! Linux uses a dedicated process group. Windows uses taskkill /T /F as a
//! fallback; it is NOT an atomic Job Object guarantee against escaping children.
use tokio::{process::{Child,Command},time::{timeout,Duration}};

pub fn configure(command:&mut Command){
    #[cfg(unix)]
    command.process_group(0);
    #[cfg(windows)]
    command.creation_flags(0x0000_0200); // CREATE_NEW_PROCESS_GROUP
    #[cfg(not(any(unix,windows)))]
    let _=command;
}

/// Attempt group/tree termination and always reap the immediate child.
pub async fn terminate(child:&mut Child)->Result<(),String>{
    let pid=child.id();
    let mut cleanup_error=None;
    #[cfg(unix)]
    if let Some(pid)=pid {
        if let Ok(group)=i32::try_from(pid) {
            // The launched child is its own process-group leader.
            if unsafe{libc::kill(-group,libc::SIGKILL)}!=0 {
                let err=std::io::Error::last_os_error();
                if err.raw_os_error()!=Some(libc::ESRCH){cleanup_error=Some(err.to_string());}
            }
        }
    }
    #[cfg(windows)]
    if let Some(pid)=pid {
        let mut taskkill=Command::new("taskkill");
        taskkill.args(["/F","/T","/PID",&pid.to_string()])
            .stdin(std::process::Stdio::null())
            .stdout(std::process::Stdio::null())
            .stderr(std::process::Stdio::null())
            .kill_on_drop(true);
        match timeout(Duration::from_secs(4),taskkill.status()).await {
            Ok(Ok(status)) if status.success()=>{},
            Ok(Ok(_))=>{}, // Process may already be gone; still kill/reap below.
            Ok(Err(e))=>cleanup_error=Some(format!("taskkill launch failed: {e}")),
            Err(_)=>cleanup_error=Some("taskkill timeout".into()),
        }
    }
    let _=child.start_kill();
    if timeout(Duration::from_secs(2),child.wait()).await.is_err(){
        return Err("Native child could not be reaped after cancellation".into());
    }
    if let Some(e)=cleanup_error{return Err(format!("Native descendant cleanup unavailable: {e}"));}
    Ok(())
}
