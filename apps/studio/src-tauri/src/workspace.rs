//! Filesystem access is restricted to a user-chosen, canonical workspace.
use serde::Serialize;
use sha2::{Digest, Sha256};
use std::{fs, path::{Component, Path, PathBuf}};

const MAX_FILE: u64 = 2 * 1024 * 1024;
const MAX_ENTRIES: usize = 500;

#[derive(Debug, Serialize)]
pub struct Entry { pub path: String, pub name: String, pub directory: bool, pub depth: usize }
#[derive(Debug, Serialize)]
pub struct Document { pub path: String, pub source: String, pub digest: String }

fn digest(bytes: &[u8]) -> String { format!("{:x}", Sha256::digest(bytes)) }

fn resolve(root: &Path, relative: &str, may_create: bool) -> Result<PathBuf, String> {
    let candidate = Path::new(relative);
    if candidate.as_os_str().is_empty() || !candidate.components().all(|c| matches!(c, Component::Normal(_))) {
        return Err("Relative workspace paths only".into());
    }
    if candidate.extension().and_then(|e| e.to_str()) != Some("pm") {
        return Err("Only .pm files can be edited in Stage 1".into());
    }
    let full = root.join(candidate);
    let parent = full.parent().ok_or("Missing file parent")?
        .canonicalize().map_err(|e| e.to_string())?;
    if !parent.starts_with(root) { return Err("Path escapes workspace".into()); }
    if !may_create && !full.is_file() { return Err("Source file not found".into()); }
    if full.exists() {
        let actual = full.canonicalize().map_err(|e| e.to_string())?;
        if !actual.starts_with(root) || !actual.is_file() { return Err("Unsafe file path".into()); }
        return Ok(actual);
    }
    Ok(full)
}

pub fn list(root: &Path) -> Result<Vec<Entry>, String> {
    let mut entries = Vec::new();
    fn visit(root: &Path, dir: &Path, depth: usize, entries: &mut Vec<Entry>) -> Result<(), String> {
        if depth > 4 || entries.len() >= MAX_ENTRIES { return Ok(()); }
        let mut items = fs::read_dir(dir).map_err(|e| e.to_string())?
            .collect::<Result<Vec<_>, _>>().map_err(|e| e.to_string())?;
        items.sort_by_key(|e| e.file_name());
        for item in items {
            if entries.len() >= MAX_ENTRIES { break; }
            let name = item.file_name().to_string_lossy().to_string();
            if name.starts_with('.') || ["node_modules", "build", "target", "dist", ".venv"].contains(&name.as_str()) { continue; }
            let kind = item.file_type().map_err(|e| e.to_string())?;
            if kind.is_symlink() { continue; }
            let is_dir = kind.is_dir();
            if !is_dir && (!kind.is_file() || item.path().extension().and_then(|s| s.to_str()) != Some("pm")) { continue; }
            let relative = item.path().strip_prefix(root).map_err(|e| e.to_string())?;
            entries.push(Entry {
                path: relative.to_string_lossy().replace('\\', "/"),
                name, directory: is_dir, depth
            });
            if is_dir { visit(root, &item.path(), depth + 1, entries)?; }
        }
        Ok(())
    }
    visit(root, root, 0, &mut entries)?;
    Ok(entries)
}

pub fn read(root: &Path, relative: &str) -> Result<Document, String> {
    let path = resolve(root, relative, false)?;
    if fs::metadata(&path).map_err(|e| e.to_string())?.len() > MAX_FILE {
        return Err("File exceeds 2 MiB".into());
    }
    let bytes = fs::read(path).map_err(|e| e.to_string())?;
    let source = String::from_utf8(bytes.clone()).map_err(|_| "Source is not UTF-8")?;
    Ok(Document { path: relative.into(), source, digest: digest(&bytes) })
}

pub fn save(root: &Path, relative: &str, source: &str, expected: &str) -> Result<Document, String> {
    if source.len() as u64 > MAX_FILE { return Err("File exceeds 2 MiB".into()); }
    let path = resolve(root, relative, false)?;
    let old = fs::read(&path).map_err(|e| e.to_string())?;
    if digest(&old) != expected { return Err("File changed on disk. Reopen before saving.".into()); }
    let parent = path.parent().ok_or("Missing parent")?;
    // Use a sibling file and atomic rename in the same filesystem.
    let temporary = parent.join(format!(".pm-save-{}-{}", std::process::id(), std::thread::current().name().unwrap_or("tmp")));
    let result = (|| -> Result<(), String> {
        use std::io::Write;
        let mut file = fs::OpenOptions::new().write(true).create_new(true).open(&temporary)
            .map_err(|e| e.to_string())?;
        file.write_all(source.as_bytes()).map_err(|e| e.to_string())?;
        file.sync_all().map_err(|e| e.to_string())?;
        fs::rename(&temporary, &path).map_err(|e| e.to_string())?;
        Ok(())
    })();
    if result.is_err() { let _ = fs::remove_file(&temporary); }
    result?;
    Ok(Document { path: relative.into(), source: source.into(), digest: digest(source.as_bytes()) })
}

pub fn create(root: &Path, relative: &str) -> Result<Document, String> {
    let path = resolve(root, relative, true)?;
    if path.exists() { return Err("File already exists".into()); }
    fs::OpenOptions::new().write(true).create_new(true).open(&path).map_err(|e| e.to_string())?;
    Ok(Document { path: relative.into(), source: String::new(), digest: digest(b"") })
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn rejects_absolute_traversal_and_non_pm() {
        let root = Path::new("/workspace");
        for p in ["../escape.pm", "/tmp/a.pm", "./a.pm", "readme.txt"] {
            assert!(resolve(root, p, true).is_err());
        }
    }
}
