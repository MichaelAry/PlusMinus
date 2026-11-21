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
            Ok(Ok(status))=>{
                // Nonzero taskkill is acceptable only when the leader already exited.
                if child.try_wait().map(|s|s.is_none()).unwrap_or(true) {
                    cleanup_error=Some(format!("taskkill exited with {status}"));
                }
            },
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

#[cfg(all(test,target_os="linux"))]
mod tests {
    use super::*;
    use tokio::io::{AsyncBufReadExt,BufReader};
    use std::process::Stdio;

    fn still_running(pid:u32)->bool {
        let Ok(contents)=std::fs::read_to_string(format!("/proc/{pid}/stat")) else {return false};
        contents.rsplit_once(") ").and_then(|(_,rest)|rest.chars().next())
            .is_some_and(|state|state!='Z' && state!='X')
    }

    #[tokio::test]
    async fn linux_group_cancellation_stops_real_grandchild() {
        // A non-interactive shell inherits our dedicated process group and
        // launches a descendant that would outlive a kill of the shell PID.
        let mut cmd=Command::new("sh");
        configure(&mut cmd);
        let mut child=cmd.args(["-c","sleep 30 & echo $!; wait"])
            .stdout(Stdio::piped()).stderr(Stdio::null()).stdin(Stdio::null())
            .kill_on_drop(true).spawn().expect("spawn shell");
        let stdout=child.stdout.take().expect("shell stdout");
        let mut lines=BufReader::new(stdout).lines();
        let grandchild=timeout(Duration::from_secs(2),lines.next_line())
            .await.expect("PID timeout").expect("read pid").expect("missing pid")
            .parse::<u32>().expect("invalid descendant pid");
        assert!(still_running(grandchild),"descendant never started");
        terminate(&mut child).await.expect("kill process group");
        for _ in 0..30 {
            if !still_running(grandchild){return;}
            tokio::time::sleep(Duration::from_millis(50)).await;
        }
        panic!("live process tree descendant {grandchild} survived cancellation");
    }
}
