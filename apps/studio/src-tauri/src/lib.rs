mod process;
mod workspace;
mod native_tests;
mod history;
mod extra_files;
mod git_view;
mod language;

use std::{collections::HashMap, path::PathBuf, sync::{Mutex,atomic::{AtomicBool,Ordering}}};
use serde_json::Value;
use tauri::{AppHandle, State};
use tauri_plugin_dialog::DialogExt;
use tokio_util::sync::CancellationToken;

#[derive(Default)]
pub(crate) struct StudioState {
    pub(crate) active_jobs: Mutex<HashMap<String, CancellationToken>>,
    pub(crate) root: Mutex<Option<PathBuf>>,
    pub(crate) source_stale: AtomicBool,
    pub(crate) rebuilt_native: Mutex<Option<PathBuf>>,
}

#[tauri::command]
async fn run_source(app: AppHandle, state: State<'_, StudioState>, request: process::RunRequest)
    -> Result<process::RunResponse, String> {
    process::validate_request(&request)?;
    if state.source_stale.load(Ordering::SeqCst){return Err("C++ source modified; rebuild the native engine before running".into());}
    let token = CancellationToken::new();
    {
        let mut jobs = state.active_jobs.lock().map_err(|e| e.to_string())?;
        if jobs.contains_key(&request.job_id) { return Err("Duplicate job_id".into()); }
        jobs.insert(request.job_id.clone(), token.clone());
    }
    let id = request.job_id.clone();
    let category = format!("{:?}",request.mode);
    let source = request.source.clone();
    let result = process::execute(&app, request, token).await;
    if let Ok(ref report)=result {
        let ok=report.report["ok"].as_bool().unwrap_or(false);
        let ms=report.wall_ms;
        let details=report.report.clone();
        let _=tauri::async_runtime::spawn_blocking(move ||
            history::save_run(&category,"Source execution",&source,ok,ms,&details)
        ).await;
    }
    state.active_jobs.lock().map_err(|e| e.to_string())?.remove(&id);
    result
}

#[tauri::command]
fn cancel_run(state: State<'_, StudioState>, job_id: String) -> Result<bool, String> {
    let jobs = state.active_jobs.lock().map_err(|e| e.to_string())?;
    if let Some(job) = jobs.get(&job_id) { job.cancel(); Ok(true) } else { Ok(false) }
}

#[tauri::command]
async fn choose_workspace(app: AppHandle, state: State<'_, StudioState>) -> Result<String, String> {
    let folder = tauri::async_runtime::spawn_blocking(move || {
        app.dialog().file().blocking_pick_folder()
    }).await.map_err(|e| e.to_string())?
      .ok_or("Folder selection canceled")?
      .into_path().map_err(|e| e.to_string())?
      .canonicalize().map_err(|e| e.to_string())?;
    if !folder.is_dir() { return Err("Workspace is not a directory".into()); }
    let display = folder.to_string_lossy().into_owned();
    *state.root.lock().map_err(|e| e.to_string())? = Some(folder);
    *state.rebuilt_native.lock().map_err(|e|e.to_string())? = None;
    state.source_stale.store(false,Ordering::SeqCst);
    Ok(display)
}

fn workspace_root(state: &State<'_, StudioState>) -> Result<PathBuf, String> {
    state.root.lock().map_err(|e| e.to_string())?
        .clone().ok_or("Choose a workspace folder first".into())
}

#[tauri::command]
async fn list_workspace(state: State<'_, StudioState>) -> Result<Vec<workspace::Entry>, String> {
    let root = workspace_root(&state)?;
    tauri::async_runtime::spawn_blocking(move || workspace::list(&root))
        .await.map_err(|e| e.to_string())?
}

#[tauri::command]
async fn open_source(state: State<'_, StudioState>, path: String) -> Result<workspace::Document, String> {
    let root = workspace_root(&state)?;
    tauri::async_runtime::spawn_blocking(move || workspace::read(&root, &path))
        .await.map_err(|e| e.to_string())?
}

#[tauri::command]
async fn save_source(state: State<'_, StudioState>, path: String, source: String, expected: String)
    -> Result<workspace::Document, String> {
    let root = workspace_root(&state)?;
    tauri::async_runtime::spawn_blocking(move || workspace::save(&root, &path, &source, &expected))
        .await.map_err(|e| e.to_string())?
}

#[tauri::command]
async fn create_source(state: State<'_, StudioState>, path: String)
    -> Result<workspace::Document, String> {
    let root = workspace_root(&state)?;
    tauri::async_runtime::spawn_blocking(move || workspace::create(&root, &path))
        .await.map_err(|e| e.to_string())?
}

#[tauri::command]
fn engine_status(app: AppHandle) -> Result<String, String> {
    process::resolve_native(&app, "plusminus_runner").map(|_| "Runner ready".into())
}

#[tauri::command]
fn native_test_status(app: AppHandle) -> Result<String, String> {
    process::resolve_native(&app, "plusminus_native_tests").map(|_| "Native test binary found".into())
}


#[tauri::command]
async fn history_overview() -> Result<Value,String>{
    tauri::async_runtime::spawn_blocking(history::overview).await.map_err(|e|e.to_string())?
}
#[tauri::command]
async fn recent_runs(limit:i64)->Result<Value,String>{
    tauri::async_runtime::spawn_blocking(move||history::recent_runs(limit))
       .await.map_err(|e|e.to_string())?
}
#[tauri::command]
async fn native_sessions(limit:i64)->Result<Value,String>{
    tauri::async_runtime::spawn_blocking(move||history::sessions(limit))
       .await.map_err(|e|e.to_string())?
}
#[tauri::command]
async fn session_results(session_id:i64)->Result<Value,String>{
    tauri::async_runtime::spawn_blocking(move||history::native_results(session_id))
       .await.map_err(|e|e.to_string())?
}
#[tauri::command]
async fn set_native_baseline(session_id:i64)->Result<(),String>{
    tauri::async_runtime::spawn_blocking(move||history::baseline(session_id))
       .await.map_err(|e|e.to_string())?
}
#[tauri::command]
async fn compare_native_sessions(base_id:i64,current_id:i64)->Result<Value,String>{
    tauri::async_runtime::spawn_blocking(move||history::compare(base_id,current_id))
       .await.map_err(|e|e.to_string())?
}
#[tauri::command]
async fn open_workspace_document(state:State<'_,StudioState>,path:String)->Result<extra_files::TextDocument,String>{
    let root=workspace_root(&state)?;
    tauri::async_runtime::spawn_blocking(move||extra_files::open(&root,&path))
       .await.map_err(|e|e.to_string())?
}
#[tauri::command]
async fn save_workspace_document(state:State<'_,StudioState>,path:String,source:String,expected:String)
    ->Result<extra_files::TextDocument,String>{
    let root=workspace_root(&state)?;
    let cpp=extra_files::is_cpp_file(&path);
    let saved=tauri::async_runtime::spawn_blocking(move||extra_files::save(&root,&path,&source,&expected))
        .await.map_err(|e|e.to_string())??;
    if cpp {state.source_stale.store(true,Ordering::SeqCst);}
    Ok(saved)
}
#[tauri::command]
async fn create_notebook(state:State<'_,StudioState>,path:String,source:String)
    ->Result<extra_files::TextDocument,String>{
    let root=workspace_root(&state)?;
    tauri::async_runtime::spawn_blocking(move||extra_files::create(&root,&path,&source))
        .await.map_err(|e|e.to_string())?
}
#[tauri::command]
async fn git_summary(state:State<'_,StudioState>)->Result<git_view::GitSummary,String>{
    let root=workspace_root(&state)?;
    Ok(git_view::summary(&root).await)
}
#[tauri::command]
async fn language_targets(state:State<'_,StudioState>,keyword:String)
    ->Result<Vec<language::Target>,String>{
    let root=workspace_root(&state)?;
    tauri::async_runtime::spawn_blocking(move||language::targets(&root,&keyword))
      .await.map_err(|e|e.to_string())?
}
#[tauri::command]
async fn rebuild_native(app:AppHandle,state:State<'_,StudioState>)->Result<String,String>{
    let root=workspace_root(&state)?;
    let log=language::rebuild(&root).await?;
    let build=root.join("build/studio5");
    let ext=std::env::consts::EXE_SUFFIX;
    let binary=build.join(format!("plusminus_runner{ext}"));
    let native=build.join(format!("plusminus_native_tests{ext}"));
    let folder=if binary.is_file()&&native.is_file(){build}else{
        let release=build.join("Release");
        if !release.join(format!("plusminus_runner{ext}")).is_file() ||
           !release.join(format!("plusminus_native_tests{ext}")).is_file(){
            return Err("CMake succeeded but expected runner and test binary were not found".into());
        }
        release
    };
    let canonical=folder.canonicalize().map_err(|e|e.to_string())?;
    if !canonical.starts_with(&root){return Err("Unexpected build output location".into());}
    *state.rebuilt_native.lock().map_err(|e|e.to_string())?=Some(canonical);
    state.source_stale.store(false,Ordering::SeqCst);
    let _=app;
    Ok(log)
}
#[tauri::command]
fn native_source_stale(state:State<'_,StudioState>)->bool{
    state.source_stale.load(Ordering::SeqCst)
}

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .manage(StudioState::default())
        .invoke_handler(tauri::generate_handler![
            run_source, cancel_run, choose_workspace, list_workspace,
            open_source, save_source, create_source, engine_status,
            native_test_status,
            native_tests::list_native_tests, native_tests::start_native_suite,
            history_overview, recent_runs, native_sessions, session_results,
            set_native_baseline, compare_native_sessions,
            open_workspace_document, save_workspace_document, create_notebook,
            git_summary, language_targets, rebuild_native, native_source_stale
        ])
        .run(tauri::generate_context!())
        .expect("Failed to start PlusMinus Studio 5");
}
