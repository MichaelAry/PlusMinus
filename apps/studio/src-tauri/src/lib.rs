mod process;
mod workspace;

use std::{collections::HashMap, path::PathBuf, sync::Mutex};
use tauri::{AppHandle, Manager, State};
use tauri_plugin_dialog::DialogExt;
use tokio_util::sync::CancellationToken;

#[derive(Default)]
struct StudioState {
    active_jobs: Mutex<HashMap<String, CancellationToken>>,
    root: Mutex<Option<PathBuf>>,
}

#[tauri::command]
async fn run_source(app: AppHandle, state: State<'_, StudioState>, request: process::RunRequest)
    -> Result<process::RunResponse, String> {
    process::validate_request(&request)?;
    let token = CancellationToken::new();
    {
        let mut jobs = state.active_jobs.lock().map_err(|e| e.to_string())?;
        if jobs.contains_key(&request.job_id) { return Err("Duplicate job_id".into()); }
        jobs.insert(request.job_id.clone(), token.clone());
    }
    let id = request.job_id.clone();
    let result = process::execute(&app, request, token).await;
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

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .manage(StudioState::default())
        .invoke_handler(tauri::generate_handler![
            run_source, cancel_run, choose_workspace, list_workspace,
            open_source, save_source, create_source, engine_status,
            native_test_status
        ])
        .run(tauri::generate_context!())
        .expect("Failed to start PlusMinus Studio 5");
}
