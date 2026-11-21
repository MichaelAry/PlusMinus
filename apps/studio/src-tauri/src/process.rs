//! Adapter for the UNMODIFIED one-shot PlusMinus C++ runner.
//! The executable accepts exactly one mode argv, UTF-8 source until stdin EOF,
//! and returns exactly one JSON object. This is NOT a JSON-RPC or DAP server.
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::{path::PathBuf, process::Stdio, time::{Duration, Instant}};
use tauri::{AppHandle, Manager};
use crate::StudioState;
use tokio::{io::{AsyncRead, AsyncReadExt, AsyncWriteExt}, process::Command};
use tokio_util::sync::CancellationToken;

const MAX_SOURCE_BYTES: usize = 1024 * 1024;
const MAX_STDOUT_BYTES: usize = 8 * 1024 * 1024;
const MAX_STDERR_BYTES: usize = 256 * 1024;

#[derive(Debug, Clone, Copy, Deserialize, Serialize)]
#[serde(rename_all = "lowercase")]
pub enum RunMode { Run, Compile, Profile, Trace }
impl RunMode {
    fn argv(self) -> &'static str {
        match self { Self::Run => "run", Self::Compile => "compile", Self::Profile => "profile", Self::Trace => "trace" }
    }
}

#[derive(Debug, Deserialize)]
pub struct RunRequest {
    pub job_id: String,
    pub source: String,
    pub mode: RunMode,
    pub timeout_ms: u64,
}

#[derive(Debug, Serialize)]
pub struct RunResponse {
    pub job_id: String,
    pub report: Value,
    pub exit_code: Option<i32>,
    pub wall_ms: f64,
    /// Captured native stderr; not merged into the JSON runner report.
    pub stderr: String,
    /// A successful VM execution may still have failed to persist its history.
    pub history_error: Option<String>,
}

pub fn validate_request(request: &RunRequest) -> Result<(), String> {
    if request.job_id.len() < 8 || request.job_id.len() > 80 ||
        !request.job_id.bytes().all(|b| b.is_ascii_alphanumeric() || b == b'-') {
        return Err("Invalid job_id".into());
    }
    if request.source.len() > MAX_SOURCE_BYTES { return Err("Source exceeds 1 MiB".into()); }
    if !(100..=300_000).contains(&request.timeout_ms) { return Err("Timeout must be 100..300000 ms".into()); }
    Ok(())
}

fn candidate_names(name: &str) -> [String; 2] {
    [format!("{name}{}", std::env::consts::EXE_SUFFIX), format!("binaries/{name}{}", std::env::consts::EXE_SUFFIX)]
}

/// No caller-supplied executable paths. Use only installed sidecars or known
/// developer CMake outputs; canonical paths must remain under a trusted root.
pub fn resolve_native(app: &AppHandle, name: &str) -> Result<PathBuf, String> {
    if name != "plusminus_runner" && name != "plusminus_native_tests" {
        return Err("Unknown native binary".into());
    }
    let mut roots = Vec::new();
    if let Some(folder) = app.state::<StudioState>().rebuilt_native.lock()
        .map_err(|e|e.to_string())?.clone() { roots.push(folder); }
    if let Ok(exe) = std::env::current_exe() {
        if let Some(parent) = exe.parent() { roots.push(parent.to_path_buf()); }
    }
    if let Ok(resources) = app.path().resource_dir() { roots.push(resources); }
    #[cfg(debug_assertions)]
    {
        let repo = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
            .ancestors().nth(3).ok_or("Cannot find development checkout")?;
        roots.extend([
            repo.join("build/studio5"), repo.join("build/studio5/Release"),
            repo.join("build"), repo.join("build/Release"),
            repo.join("ide/build"), repo.join("ide/build/Release"),
            std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("binaries"),
        ]);
    }
    for root in roots {
        let Ok(trusted_root) = root.canonicalize() else { continue; };
        for candidate in candidate_names(name) {
            let path = trusted_root.join(&candidate);
            let Ok(canonical) = path.canonicalize() else { continue; };
            if canonical.starts_with(&trusted_root) && canonical.is_file() { return Ok(canonical); }
        }
    }
    Err(format!("{name} not found; build C++ and stage native sidecars first"))
}

pub(crate) async fn read_capped<R: AsyncRead + Unpin>(mut stream: R, max: usize) -> Result<Vec<u8>, String> {
    let mut bytes = Vec::new();
    let mut chunk = [0u8; 8192];
    loop {
        let amount = stream.read(&mut chunk).await.map_err(|e| e.to_string())?;
        if amount == 0 { return Ok(bytes); }
        if bytes.len().saturating_add(amount) > max {
            return Err(format!("Native output exceeds {max} bytes"));
        }
        bytes.extend_from_slice(&chunk[..amount]);
    }
}

pub fn decode_report(stdout: &[u8], exit_code: Option<i32>) -> Result<Value, String> {
    let value: Value = serde_json::from_slice(stdout)
        .map_err(|e| format!("Invalid C++ JSON response: {e}"))?;
    let object = value.as_object().ok_or("Runner response is not a JSON object")?;
    if !object.get("ok").is_some_and(Value::is_boolean) {
        return Err("Runner response missing boolean ok".into());
    }
    for field in ["output", "result", "variables", "bytecode", "error"] {
        if !object.get(field).is_some_and(Value::is_string) {
            return Err(format!("Runner response missing string {field}"));
        }
    }
    if !object.get("diagnostics").is_some_and(Value::is_array) ||
       !object.get("trace").is_some_and(Value::is_array) ||
       !object.get("metrics").is_some_and(Value::is_object) {
        return Err("Runner response has invalid diagnostics, trace or metrics".into());
    }
    if !object.get("trace_truncated").is_some_and(Value::is_boolean) {
        return Err("Runner response missing boolean trace_truncated".into());
    }
    let diagnostics = object["diagnostics"].as_array().ok_or("Invalid diagnostics")?;
    for row in diagnostics {
        if !row.get("severity").is_some_and(Value::is_string)
            || !row.get("phase").is_some_and(Value::is_string)
            || !row.get("message").is_some_and(Value::is_string)
            || !row.get("line").is_some_and(|v| v.as_u64().is_some())
            || !row.get("column").is_some_and(|v| v.as_u64().is_some()) {
            return Err("Malformed runner diagnostic".into());
        }
    }
    let trace = object["trace"].as_array().ok_or("Invalid trace")?;
    if trace.len() > 5000 { return Err("Runner trace exceeds the 5000 event cap".into()); }
    for row in trace {
        if !row.get("ip").is_some_and(|v| v.as_u64().is_some())
            || !row.get("thread").is_some_and(|v| v.as_u64().is_some())
            || !row.get("stack_depth").is_some_and(|v| v.as_u64().is_some())
            || !row.get("opcode").is_some_and(Value::is_string) {
            return Err("Malformed runner trace event".into());
        }
    }
    let metrics = object["metrics"].as_object().ok_or("Invalid metrics")?;
    for key in ["compile_ms", "execute_ms", "program_instructions", "executed_instructions"] {
        if !metrics.get(key).is_some_and(|v| v.is_null() || v.is_number()) {
            return Err(format!("Malformed runner metric {key}"));
        }
    }
    if !metrics.get("opcode_hits").and_then(Value::as_object)
        .is_some_and(|hits| hits.values().all(|n| n.as_u64().is_some())) {
        return Err("Malformed runner opcode_hits".into());
    }
    // Compile errors return ok=false AND exit 1: preserve the legitimate report.
    // Exit 0 with ok=false or exit nonzero with ok=true is a protocol mismatch.
    let expected = if value["ok"] == true {Some(0)} else {Some(1)};
    if exit_code != expected {
        return Err(format!("Runner response/exit mismatch: expected {expected:?}, got {exit_code:?}"));
    }
    Ok(value)
}

pub async fn execute(
    app: &AppHandle,
    request: RunRequest,
    cancel: CancellationToken,
) -> Result<RunResponse, String> {
    validate_request(&request)?;
    let executable = resolve_native(app, "plusminus_runner")?;
    execute_with_executable(executable,request,cancel).await
}
/// Testable entrypoint preserving the *real* unchanged one-shot C++ process.
pub(crate) async fn execute_with_executable(
    executable: PathBuf,request:RunRequest,cancel:CancellationToken
)->Result<RunResponse,String>{
    validate_request(&request)?;
    let start = Instant::now();
    let mut command=Command::new(executable);
    crate::process_tree::configure(&mut command);
    let mut child = command.arg(request.mode.argv())
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .kill_on_drop(true)
        .spawn().map_err(|e| format!("Runner spawn failed: {e}"))?;
    let mut stdin = child.stdin.take().ok_or("Runner stdin unavailable")?;
    let stdout = child.stdout.take().ok_or("Runner stdout unavailable")?;
    let stderr = child.stderr.take().ok_or("Runner stderr unavailable")?;

    let execution = async {
        stdin.write_all(request.source.as_bytes()).await
            .map_err(|e| format!("Runner stdin failed: {e}"))?;
        drop(stdin); // Mandatory EOF: C++ reads istreambuf_iterator until EOF.
        tokio::try_join!(
            async { child.wait().await.map_err(|e| e.to_string()) },
            read_capped(stdout, MAX_STDOUT_BYTES),
            read_capped(stderr, MAX_STDERR_BYTES)
        )
    };

    let outcome = tokio::select! {
        _ = cancel.cancelled() => Err("Canceled by user".to_string()),
        result = tokio::time::timeout(Duration::from_millis(request.timeout_ms), execution) => {
            result.map_err(|_| "Runner timed out".to_string()).and_then(|r| r)
        }
    };
    if let Err(ref reason) = outcome {
        if let Err(cleanup)=crate::process_tree::terminate(&mut child).await {
            return Err(format!("{reason}; {cleanup}"));
        }
    }
    let (status, stdout, stderr) = outcome?;
    let report = decode_report(&stdout, status.code())?;
    // Preserve stderr even for compilation failures, without changing the
    // authoritative JSON report or incorrectly declaring successful execution a failure.
    Ok(RunResponse {
        job_id: request.job_id,
        report,
        exit_code: status.code(),
        wall_ms: start.elapsed().as_secs_f64() * 1000.0,
        stderr: String::from_utf8_lossy(&stderr).into_owned(),
        history_error: None,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    const EMPTY: &str = r#"{"ok":true,"output":"","result":"0","variables":"","bytecode":"","error":"","diagnostics":[],"trace":[],"trace_truncated":false,"metrics":{"compile_ms":0,"execute_ms":null,"program_instructions":0,"executed_instructions":0,"opcode_hits":{}}}"#;
    fn staged_cpp_runner()->Option<PathBuf>{
        let folder=std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("binaries");
        std::fs::read_dir(folder).ok()?.filter_map(Result::ok)
            .map(|e|e.path()).find(|p|{
                let name=p.file_name().and_then(|n|n.to_str()).unwrap_or("");
                name.starts_with("plusminus_runner-")&&
                  name.ends_with(std::env::consts::EXE_SUFFIX)
            })
    }
    #[tokio::test]
    async fn actual_cpp_runner_all_modes_compile_errors_and_zero(){
        let Some(path)=staged_cpp_runner() else{return;};
        for mode in [RunMode::Run,RunMode::Compile,RunMode::Profile,RunMode::Trace]{
            let response=execute_with_executable(path.clone(),RunRequest{
                job_id:"cpp-smoke-001".into(),source:"print(0);\\n".replace("\\n","\n"),
                mode,timeout_ms:10000,
            },CancellationToken::new()).await.unwrap();
            assert_eq!(response.exit_code,Some(0));
            assert_eq!(response.report["ok"],true);
            if matches!(mode,RunMode::Run){assert!(response.report["output"].as_str().unwrap().contains('0'));}
            if matches!(mode,RunMode::Trace){assert!(response.report["trace"].as_array().unwrap().len()>0);}
        }
        let failure=execute_with_executable(path,RunRequest{
            job_id:"cpp-smoke-err".into(),source:"print(;".into(),
            mode:RunMode::Compile,timeout_ms:10000,
        },CancellationToken::new()).await.unwrap();
        assert_eq!(failure.exit_code,Some(1));
        assert_eq!(failure.report["ok"],false);
    }
    #[tokio::test]
    async fn actual_cpp_timeout_terminates_one_shot_runner(){
        let Some(path)=staged_cpp_runner() else{return;};
        let result=execute_with_executable(path,RunRequest{
            job_id:"cpp-loop-001".into(),source:"while (1) {}".into(),
            mode:RunMode::Run,timeout_ms:300,
        },CancellationToken::new()).await;
        assert!(result.unwrap_err().contains("timed out"));
    }
    #[tokio::test]
    async fn actual_cpp_cancellation_is_reported_and_child_is_stopped() {
        let Some(path)=staged_cpp_runner() else{return;};
        let token=CancellationToken::new();
        let cancel=token.clone();
        let running=tokio::spawn(async move {
            execute_with_executable(path,RunRequest {
                job_id:"cpp-cancel-001".into(),source:"while (1) {}".into(),
                mode:RunMode::Run,timeout_ms:10000,
            },cancel).await
        });
        tokio::time::sleep(Duration::from_millis(100)).await;
        token.cancel();
        let outcome=tokio::time::timeout(Duration::from_secs(3),running)
            .await.expect("Canceled runner did not exit promptly").unwrap();
        assert!(outcome.unwrap_err().contains("Canceled by user"));
    }

    #[test]
    fn empty_stdout_and_zero_result_are_not_lost() {
        let result = decode_report(EMPTY.as_bytes(), Some(0)).unwrap();
        assert_eq!(result["output"], "");
        assert_eq!(result["result"], "0");
    }
    #[test]
    fn nonzero_compile_error_is_not_transport_failure() {
        let data = EMPTY.replace(r#""ok":true"#, r#""ok":false"#);
        assert!(decode_report(data.as_bytes(), Some(1)).is_ok());
    }
    #[test]
    fn cpp_exit_code_two_is_not_a_language_error(){
        let failure=EMPTY.replace(r#""ok":true"#,r#""ok":false"#);
        assert!(decode_report(failure.as_bytes(),Some(2)).is_err());
    }
    #[test]
    fn success_exit_mismatch_is_error() {
        assert!(decode_report(EMPTY.as_bytes(), Some(1)).is_err());
    }
    #[tokio::test]
    async fn bounded_stream_read_rejects_excess_bytes_before_eof(){
        use tokio::io::AsyncWriteExt;
        let (mut writer,reader)=tokio::io::duplex(64);
        let send=tokio::spawn(async move{
            let _=writer.write_all(&vec![b'x';128]).await;
        });
        let rejected=read_capped(reader,100).await;
        assert!(rejected.unwrap_err().contains("exceeds 100 bytes"));
        send.abort();
    }
    #[test]
    fn rejects_malformed_nested_native_reports() {
        let mut payload: Value = serde_json::from_str(EMPTY).unwrap();
        payload["metrics"]["opcode_hits"] = serde_json::json!({"Jmp": "invalid"});
        assert!(decode_report(payload.to_string().as_bytes(), Some(0)).is_err());
        payload["metrics"]["opcode_hits"] = serde_json::json!({});
        payload["trace_truncated"] = Value::Null;
        assert!(decode_report(payload.to_string().as_bytes(), Some(0)).is_err());
        payload["trace_truncated"] = serde_json::json!(false);
        payload["diagnostics"] = serde_json::json!([{"message": "missing fields"}]);
        assert!(decode_report(payload.to_string().as_bytes(), Some(0)).is_err());
        payload["diagnostics"] = serde_json::json!([]);
        payload["trace"] = serde_json::json!([{"ip": "not an index"}]);
        assert!(decode_report(payload.to_string().as_bytes(), Some(0)).is_err());
    }
    #[test]
    fn rejects_multiple_objects_and_invalid_payload() {
        let data = format!("{EMPTY}\n{EMPTY}");
        assert!(decode_report(data.as_bytes(), Some(0)).is_err());
    }
}
