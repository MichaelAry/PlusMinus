//! Native .pmplot access through a selected workspace or OS file picker.
use crate::{extra_files::TextDocument, workspace::WORKSPACE_WRITES, StudioState};
use serde_json::Value;
use sha2::{Digest, Sha256};
use std::{
    collections::HashSet,
    fs::{self, File},
    io::{ErrorKind, Read, Write},
    path::{Component, Path, PathBuf},
    sync::Mutex,
};
use tauri::{AppHandle, Manager, State};
use tauri_plugin_dialog::DialogExt;

const MAX_FILE: usize = 2 * 1024 * 1024;
const MAX_SERIES: usize = 16;
const MAX_POINTS: usize = 10_000;
const MAX_EXPRESSION: usize = 512;

#[derive(Default)]
pub(crate) struct PlotFiles {
    authorized: Mutex<HashSet<PathBuf>>,
}

fn plot_extension(path: &Path) -> bool {
    path.extension()
        .and_then(|ext| ext.to_str())
        .is_some_and(|ext| ext.eq_ignore_ascii_case("pmplot"))
}

fn check_extension(path: &Path) -> Result<(), String> {
    if plot_extension(path) {
        Ok(())
    } else {
        Err("Choose a .pmplot file".into())
    }
}

fn validate(source: &str) -> Result<(), String> {
    fn check(ok: bool, field: &str) -> Result<(), String> {
        ok.then_some(()).ok_or_else(|| format!("Invalid {field}"))
    }
    fn number(value: &Value, field: &str) -> Result<f64, String> {
        value
            .as_f64()
            .filter(|n| n.is_finite())
            .ok_or_else(|| format!("Invalid {field}"))
    }

    if source.len() > MAX_FILE {
        return Err("Plot file exceeds 2 MiB".into());
    }
    let document: Value =
        serde_json::from_str(source).map_err(|err| format!("Invalid plot JSON: {err}"))?;
    check(document["version"].as_u64() == Some(1), "version")?;
    let viewport = &document["viewport"];
    for (min, max) in [("xmin", "xmax"), ("ymin", "ymax")] {
        let low = number(&viewport[min], &format!("viewport.{min}"))?;
        let high = number(&viewport[max], &format!("viewport.{max}"))?;
        check(
            low < high && (high - low).is_finite(),
            &format!("viewport.{min}/{max}"),
        )?;
    }
    let series = document["series"]
        .as_array()
        .filter(|s| s.len() <= MAX_SERIES)
        .ok_or("Invalid series count")?;
    let mut ids = HashSet::new();
    let mut points = 0;
    for (index, entry) in series.iter().enumerate() {
        let field = |name: &str| format!("series {}.{name}", index + 1);
        check(
            entry["id"]
                .as_str()
                .is_some_and(|id| !id.is_empty() && ids.insert(id)),
            &field("id"),
        )?;
        check(entry["label"].is_string(), &field("label"))?;
        check(entry["visible"].is_boolean(), &field("visible"))?;
        check(
            entry["color"].as_str().is_some_and(|color| {
                color.len() == 7
                    && color.starts_with('#')
                    && color.as_bytes()[1..].iter().all(u8::is_ascii_hexdigit)
            }),
            &field("color"),
        )?;
        match entry["kind"].as_str() {
            Some("formula") => {
                check(
                    entry["expression"]
                        .as_str()
                        .is_some_and(|text| text.chars().count() <= MAX_EXPRESSION),
                    &field("expression"),
                )?;
                let params = entry["parameters"]
                    .as_object()
                    .ok_or_else(|| format!("Invalid {}", field("parameters")))?;
                for (name, value) in params {
                    let field = field(&format!("parameters.{name}"));
                    let n = number(value, &field)?;
                    check(
                        matches!(name.as_str(), "a" | "b" | "c")
                            && (-10.0..=10.0).contains(&n)
                            && (n * 100.0 - (n * 100.0).round()).abs() <= 1e-9,
                        &field,
                    )?;
                }
            }
            Some("points") => {
                let rows = entry["points"]
                    .as_array()
                    .ok_or_else(|| format!("Invalid {}", field("points")))?;
                points += rows.len();
                check(points <= MAX_POINTS, &field("points count"))?;
                for (index, row) in rows.iter().enumerate() {
                    let field = field(&format!("points row {}", index + 1));
                    check(row.as_array().is_some_and(|pair| pair.len() == 2), &field)?;
                    number(&row[0], &format!("{field} X"))?;
                    number(&row[1], &format!("{field} Y"))?;
                }
            }
            _ => return Err(format!("Invalid {}", field("kind"))),
        }
    }
    Ok(())
}

fn read_bounded(path: &Path, limit: usize) -> Result<String, String> {
    let mut bytes = Vec::new();
    File::open(path)
        .map_err(|e| e.to_string())?
        .take((limit + 1) as u64)
        .read_to_end(&mut bytes)
        .map_err(|e| e.to_string())?;
    if bytes.len() > limit {
        return Err("File exceeds size limit".into());
    }
    String::from_utf8(bytes).map_err(|_| "File is not UTF-8".into())
}

fn canonical_file(path: &Path) -> Result<PathBuf, String> {
    check_extension(path)?;
    let actual = path.canonicalize().map_err(|e| e.to_string())?;
    check_extension(&actual)?;
    if !actual.is_file() {
        return Err("Plot path is not a file".into());
    }
    Ok(actual)
}

fn workspace_plot(root: &Path, relative: &str) -> Result<PathBuf, String> {
    let relative = Path::new(relative);
    if relative.as_os_str().is_empty()
        || !relative
            .components()
            .all(|part| matches!(part, Component::Normal(_)))
    {
        return Err("Only workspace-relative paths are allowed".into());
    }
    let root = root.canonicalize().map_err(|e| e.to_string())?;
    let path = canonical_file(&root.join(relative))?;
    if !path.starts_with(root) {
        return Err("Plot path escapes workspace".into());
    }
    Ok(path)
}

fn digest(source: &str) -> String {
    format!("{:x}", Sha256::digest(source.as_bytes()))
}

fn read_document(path: &Path) -> Result<TextDocument, String> {
    let source = read_bounded(path, MAX_FILE)?;
    validate(&source)?;
    text_document(path, source)
}

fn text_document(path: &Path, source: String) -> Result<TextDocument, String> {
    let path = path.to_str().ok_or("Plot path is not UTF-8")?.to_owned();
    Ok(TextDocument {
        path,
        digest: digest(&source),
        source,
    })
}

fn atomic_write(path: &Path, source: &str, replace: bool) -> Result<(), String> {
    let parent = path.parent().ok_or("Invalid file location")?;
    let mut temp = tempfile::NamedTempFile::new_in(parent).map_err(|e| e.to_string())?;
    temp.write_all(source.as_bytes())
        .map_err(|e| e.to_string())?;
    if replace {
        let permissions = fs::metadata(path).map_err(|e| e.to_string())?.permissions();
        if permissions.readonly() {
            return Err("File is read-only".into());
        }
        temp.as_file()
            .set_permissions(permissions)
            .map_err(|e| e.to_string())?;
    }
    temp.as_file().sync_all().map_err(|e| e.to_string())?;
    if replace {
        temp.persist(path).map_err(|e| e.error.to_string())?;
    } else {
        temp.persist_noclobber(path)
            .map_err(|e| e.error.to_string())?;
    }
    Ok(())
}

impl PlotFiles {
    fn authorize(&self, path: PathBuf) -> Result<(), String> {
        self.authorized
            .lock()
            .map_err(|e| e.to_string())?
            .insert(path);
        Ok(())
    }

    fn checked(&self, path: &Path) -> Result<PathBuf, String> {
        let grants = self.authorized.lock().map_err(|e| e.to_string())?;
        if !grants.contains(path) || canonical_file(path)? != path {
            return Err("Open or select the plot file before writing".into());
        }
        Ok(path.to_owned())
    }
}

#[tauri::command]
pub(crate) async fn open_plot(
    app: AppHandle,
    state: State<'_, StudioState>,
    relative: Option<String>,
) -> Result<Option<TextDocument>, String> {
    let root = relative
        .as_ref()
        .map(|_| super::workspace_root(&state))
        .transpose()?;
    let opened = tauri::async_runtime::spawn_blocking(move || {
        let path = if let Some((root, relative)) = root.zip(relative) {
            workspace_plot(&root, &relative)?
        } else {
            let Some(file) = app
                .dialog()
                .file()
                .add_filter("Plot files", &["pmplot"])
                .blocking_pick_file()
            else {
                return Ok::<_, String>(None);
            };
            canonical_file(&file.into_path().map_err(|e| e.to_string())?)?
        };
        let document = read_document(&path)?;
        Ok(Some((path, document)))
    })
    .await
    .map_err(|e| e.to_string())??;
    if let Some((path, document)) = opened {
        state.plots.authorize(path)?;
        Ok(Some(document))
    } else {
        Ok(None)
    }
}

#[tauri::command]
pub(crate) async fn save_plot(
    app: AppHandle,
    state: State<'_, StudioState>,
    source: String,
    path: Option<String>,
    expected: Option<String>,
    name: Option<String>,
) -> Result<Option<TextDocument>, String> {
    if path.is_some() != expected.is_some() {
        return Err("Existing plot saves require a file digest".into());
    }
    let previous = path
        .map(|p| state.plots.checked(Path::new(&p)))
        .transpose()?;
    let saved = tauri::async_runtime::spawn_blocking(move || {
        validate(&source)?;
        let (path, replace) = if let Some(path) = previous {
            (path, true)
        } else {
            let Some(file) = app
                .dialog()
                .file()
                .add_filter("Plot files", &["pmplot"])
                .set_file_name(name.as_deref().unwrap_or("untitled.pmplot"))
                .blocking_save_file()
            else {
                return Ok::<_, String>(None);
            };
            let mut path = file.into_path().map_err(|e| e.to_string())?;
            if !plot_extension(&path) {
                let stem = path
                    .file_name()
                    .and_then(|name| name.to_str())
                    .ok_or("Invalid filename")?;
                path.set_file_name(format!("{stem}.pmplot"));
                // The dialog's overwrite confirmation applies to the selected name.
                if path.exists() {
                    return Err("Choose the full .pmplot filename to confirm replacement".into());
                }
            }
            if path.exists() {
                (canonical_file(&path)?, true)
            } else {
                let parent = path
                    .parent()
                    .ok_or("Invalid file location")?
                    .canonicalize()
                    .map_err(|e| e.to_string())?;
                (
                    parent.join(path.file_name().ok_or("Invalid filename")?),
                    false,
                )
            }
        };
        let _write = WORKSPACE_WRITES.lock().map_err(|e| e.to_string())?;
        if replace && canonical_file(&path)? != path {
            return Err("Plot location changed; reopen it before saving".into());
        }
        if let Some(expected) = expected {
            if digest(&read_bounded(&path, MAX_FILE)?) != expected {
                return Err("Plot changed on disk. Reopen before saving.".into());
            }
        }
        let document = text_document(&path, source)?;
        atomic_write(&path, &document.source, replace)?;
        Ok(Some((path, document)))
    })
    .await
    .map_err(|e| e.to_string())??;
    if let Some((path, document)) = saved {
        state.plots.authorize(path)?;
        Ok(Some(document))
    } else {
        Ok(None)
    }
}

fn session_path(app: &AppHandle) -> Result<PathBuf, String> {
    Ok(app
        .path()
        .app_config_dir()
        .map_err(|e| e.to_string())?
        .join("last-plot.json"))
}

#[tauri::command]
pub(crate) async fn remember_plot(
    app: AppHandle,
    state: State<'_, StudioState>,
    path: Option<String>,
) -> Result<(), String> {
    if let Some(path) = &path {
        state.plots.checked(Path::new(path))?;
    }
    let location = session_path(&app)?;
    tauri::async_runtime::spawn_blocking(move || {
        let _write = WORKSPACE_WRITES.lock().map_err(|e| e.to_string())?;
        if path.is_none() {
            return match fs::remove_file(location) {
                Err(error) if error.kind() != ErrorKind::NotFound => Err(error.to_string()),
                _ => Ok(()),
            };
        }
        fs::create_dir_all(location.parent().ok_or("Invalid plot settings location")?)
            .map_err(|error| error.to_string())?;
        let json = serde_json::to_string(&path).map_err(|e| e.to_string())?;
        atomic_write(&location, &json, location.exists())
    })
    .await
    .map_err(|e| e.to_string())?
}

#[tauri::command]
pub(crate) async fn restore_plot(
    app: AppHandle,
    state: State<'_, StudioState>,
) -> Result<Option<TextDocument>, String> {
    let location = session_path(&app)?;
    let restored = tauri::async_runtime::spawn_blocking(move || {
        if !location.is_file() {
            return Ok::<_, String>(None);
        }
        let path: PathBuf =
            serde_json::from_str(&read_bounded(&location, 65_536)?).map_err(|e| e.to_string())?;
        if !path.exists() {
            return Ok(None);
        }
        if canonical_file(&path)? != path {
            return Err("Saved plot location changed; reopen it from the file picker".into());
        }
        let document = read_document(&path)?;
        Ok(Some((path, document)))
    })
    .await
    .map_err(|e| e.to_string())??;
    if let Some((path, document)) = restored {
        state.plots.authorize(path)?;
        Ok(Some(document))
    } else {
        Ok(None)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn reads_shared_example_and_replaces_atomically() {
        let source = include_str!("../../../../docs/plot-examples/waves-and-measurements.pmplot");
        let root = tempfile::tempdir().unwrap();
        let path = root.path().join("example.pmplot");
        validate(source).unwrap();
        atomic_write(&path, source, false).unwrap();
        assert!(atomic_write(&path, "wrong", false).is_err());
        assert_eq!(read_document(&path).unwrap().source, source);
        let updated = source.replace("Adjustable sine", "Adjusted sine");
        atomic_write(&path, &updated, true).unwrap();
        assert_eq!(read_document(&path).unwrap().source, updated);
        assert!(workspace_plot(root.path(), "../example.pmplot").is_err());
        assert!(validate(&updated.replace("#5AB0FF", "#oops00")).is_err());
    }
}
