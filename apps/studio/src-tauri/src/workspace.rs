//! Filesystem access is restricted to a user-chosen, canonical workspace.
use serde::Serialize;
use sha2::{Digest, Sha256};
use std::{fs, path::{Component, Path, PathBuf}, sync::{LazyLock, Mutex}};

/// Prevent two writes in this app process from passing the same optimistic digest check.
pub(crate) static WORKSPACE_WRITES: LazyLock<Mutex<()>> = LazyLock::new(|| Mutex::new(()));

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
    // Resolve both paths to the same canonical representation (Windows uses
    // the verbatim \\?\ prefix for canonical paths).
    let canonical_root=root.canonicalize().map_err(|e|e.to_string())?;
    let full = canonical_root.join(candidate);
    let parent = full.parent().ok_or("Missing file parent")?
        .canonicalize().map_err(|e| e.to_string())?;
    if !parent.starts_with(&canonical_root) { return Err("Path escapes workspace".into()); }
    if !may_create && !full.is_file() { return Err("Source file not found".into()); }
    if full.exists() {
        let actual = full.canonicalize().map_err(|e| e.to_string())?;
        if !actual.starts_with(&canonical_root) || !actual.is_file() { return Err("Unsafe file path".into()); }
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
            if !is_dir && (!kind.is_file() || !item.path().extension().and_then(|s| s.to_str()).is_some_and(|ext|
                matches!(ext, "pm" | "ipynb" | "cpp" | "hpp" | "h") || ext.eq_ignore_ascii_case("pmplot"))) { continue; }
            let entry_path = item.path();
            let relative = entry_path.strip_prefix(root).map_err(|e| e.to_string())?;
            entries.push(Entry {
                path: relative.to_string_lossy().replace('\\', "/"),
                name, directory: is_dir, depth
            });
            if is_dir { visit(root, &entry_path, depth + 1, entries)?; }
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
    let _write_guard = WORKSPACE_WRITES.lock().map_err(|e|e.to_string())?;
    if source.len() as u64 > MAX_FILE { return Err("File exceeds 2 MiB".into()); }
    let path = resolve(root, relative, false)?;
    let old = fs::read(&path).map_err(|e| e.to_string())?;
    if digest(&old) != expected { return Err("File changed on disk. Reopen before saving.".into()); }
    let parent = path.parent().ok_or("Missing parent")?;
    // Use a sibling file and atomic rename in the same filesystem.
    // Windows cannot rename a new file over an existing destination. Keep the
    // previous bytes recoverable until the replacement is in place.
    let nonce = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH).unwrap_or_default().as_nanos();
    let temporary = parent.join(format!(".pm-save-{}-{nonce}", std::process::id()));
    let old_permissions = fs::metadata(&path).map_err(|e|e.to_string())?.permissions();
    if old_permissions.readonly() { return Err("Source file is read-only".into()); }
    let result = (|| -> Result<(), String> {
        use std::io::Write;
        let mut file = fs::OpenOptions::new().write(true).create_new(true).open(&temporary)
            .map_err(|e| e.to_string())?;
        file.write_all(source.as_bytes()).map_err(|e| e.to_string())?;
        file.set_permissions(old_permissions).map_err(|e| e.to_string())?;
        file.sync_all().map_err(|e| e.to_string())?;
        drop(file);
        #[cfg(windows)]
        {
            let backup = parent.join(format!(".pm-backup-{}-{nonce}",std::process::id()));
            fs::rename(&path,&backup).map_err(|e|e.to_string())?;
            if let Err(error) = fs::rename(&temporary,&path) {
                let restore = fs::rename(&backup,&path);
                return Err(match restore {
                    Ok(()) => error.to_string(),
                    Err(recovery) => format!("Save failed: {error}; original retained at {} (restore: {recovery})",backup.display()),
                });
            }
            let _ = fs::remove_file(&backup);
        }
        #[cfg(not(windows))]
        fs::rename(&temporary, &path).map_err(|e| e.to_string())?;
        Ok(())
    })();
    if result.is_err() { let _ = fs::remove_file(&temporary); }
    result?;
    Ok(Document { path: relative.into(), source: source.into(), digest: digest(source.as_bytes()) })
}

pub fn create(root: &Path, relative: &str) -> Result<Document, String> {
    let _write_guard = WORKSPACE_WRITES.lock().map_err(|e|e.to_string())?;
    let path = resolve(root, relative, true)?;
    if path.exists() { return Err("File already exists".into()); }
    fs::OpenOptions::new().write(true).create_new(true).open(&path).map_err(|e| e.to_string())?;
    Ok(Document { path: relative.into(), source: String::new(), digest: digest(b"") })
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn pm_write_round_trip_preserves_content_and_detects_conflicts() {
        let nonce = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH).unwrap().as_nanos();
        let root = std::env::temp_dir().join(format!("studio5-pm-{}-{nonce}",std::process::id()));
        fs::create_dir(&root).unwrap();
        let first = create(&root,"program.pm").unwrap();
        assert_eq!(first.source,"");
        let next = save(&root,"program.pm","print(0);\n",&first.digest).unwrap();
        assert_eq!(read(&root,"program.pm").unwrap().source,"print(0);\n");
        assert!(save(&root,"program.pm","corrupted","incorrect-digest").is_err());
        assert_eq!(read(&root,"program.pm").unwrap().digest,next.digest);
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn simultaneous_saves_with_same_digest_do_not_overwrite_each_other() {
        use std::sync::{Arc,Barrier};
        let nonce=std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH)
            .unwrap().as_nanos();
        let root=std::env::temp_dir().join(format!("studio5-save-race-{}-{nonce}",std::process::id()));
        fs::create_dir(&root).unwrap();
        let initial=create(&root,"race.pm").unwrap();
        let barrier=Arc::new(Barrier::new(3));
        let results:Vec<_>=std::thread::scope(|scope|{
            let handles:Vec<_>=(0..2).map(|i|{
                let b=Arc::clone(&barrier);
                let root=&root;
                let digest=initial.digest.clone();
                scope.spawn(move || {
                    b.wait();
                    save(root,"race.pm",&format!("print({i});"),&digest)
                })
            }).collect();
            barrier.wait();
            handles.into_iter().map(|h|h.join().unwrap()).collect()
        });
        assert_eq!(results.iter().filter(|r|r.is_ok()).count(),1);
        assert!(results.iter().any(|r|r.as_ref().err().is_some_and(|s|s.contains("changed on disk"))));
        let content=read(&root,"race.pm").unwrap().source;
        assert!(content=="print(0);"||content=="print(1);");
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn rejects_absolute_traversal_and_non_pm() {
        let root = Path::new("/workspace");
        for p in ["../escape.pm", "/tmp/a.pm", "./a.pm", "readme.txt"] {
            assert!(resolve(root, p, true).is_err());
        }
    }
}
