//! Stage 2: lossless one-time SQLite backup of Studio 4 and v5 sessions.
//! NEVER open ~/.plusminus/studio.db in writable mode.
use rusqlite::{backup::Backup, params, Connection, OpenFlags};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::{fs, path::{Path, PathBuf}, time::{Duration, SystemTime, UNIX_EPOCH}};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NativeResult {
    pub id: String,
    pub group: String,
    pub source: String,
    pub slow: bool,
    pub status: String,
    pub error: String,
    pub elapsed_ms: f64,
    pub test_ms: Option<f64>,
    pub cpu_ms: Option<f64>,
    pub peak_rss_mb: Option<f64>,
}

fn path_v5() -> Result<PathBuf, String> {
    let home = dirs::home_dir().ok_or("Cannot resolve home directory")?;
    let folder = home.join(".plusminus");
    fs::create_dir_all(&folder).map_err(|e| e.to_string())?;
    Ok(folder.join("studio-v5.db"))
}

fn count_table(db: &Connection, name: &str) -> Result<i64, String> {
    if !["runs","native_sessions","native_results","native_baseline"].contains(&name) {
        return Err("Unknown table".into());
    }
    let count: i64 = db.query_row(
        "SELECT count(*) FROM sqlite_master WHERE type='table' AND name=?1",
        [name], |r| r.get(0)).map_err(|e| e.to_string())?;
    if count == 0 { return Ok(0); }
    // This list is hard-coded to known Studio 4 tables; no SQL identifiers
    // originate from callers.
    let query = match name {
        "runs" => "SELECT count(*) FROM runs",
        "native_sessions" => "SELECT count(*) FROM native_sessions",
        "native_results" => "SELECT count(*) FROM native_results",
        "native_baseline" => "SELECT count(*) FROM native_baseline",
        _ => return Err("Unknown table".into()),
    };
    db.query_row(query, [], |r| r.get(0)).map_err(|e| e.to_string())
}

fn verify(db: &Connection) -> Result<(), String> {
    let check: String = db.query_row("PRAGMA integrity_check", [], |r| r.get(0))
        .map_err(|e| e.to_string())?;
    if check != "ok" { return Err(format!("SQLite integrity_check: {check}")); }
    Ok(())
}

pub fn initialize() -> Result<PathBuf, String> {
    initialize_at(path_v5()?)
}

fn initialize_at(dest: PathBuf) -> Result<PathBuf, String> {
    if !dest.exists() {
        let old = dest.with_file_name("studio.db");
        let temp = dest.with_extension(format!("db.migration-{}.tmp", std::process::id()));
        if temp.exists() { return Err("An unfinished migration backup exists; inspect it before retrying".into()); }
        let source = if old.is_file() {
            Some(Connection::open_with_flags(&old, OpenFlags::SQLITE_OPEN_READ_ONLY)
                .map_err(|e| e.to_string())?)
        } else { None };
        if let Some(ref source) = source { verify(source)?; }
        let mut new_db = Connection::open(&temp).map_err(|e| e.to_string())?;
        let backup_result = (|| -> Result<(), String> {
            if let Some(ref src) = source {
                let backup = Backup::new(src, &mut new_db).map_err(|e| e.to_string())?;
                backup.run_to_completion(128, Duration::from_millis(10), None)
                    .map_err(|e| e.to_string())?;
                drop(backup);
                verify(&new_db)?;
                for table in ["runs", "native_sessions", "native_results", "native_baseline"] {
                    if count_table(src, table)? != count_table(&new_db, table)? {
                        return Err(format!("Data count mismatch during backup: {table}"));
                    }
                }
            }
            Ok(())
        })();
        drop(new_db);
        if let Err(e) = backup_result {
            let _ = fs::remove_file(&temp);
            return Err(e);
        }
        // No existing v5 file is ever overwritten or reset.
        if dest.exists() { let _ = fs::remove_file(&temp); return Err("v5 database already appeared".into()); }
        fs::rename(&temp, &dest).map_err(|e| e.to_string())?;
    }
    let mut db = Connection::open(&dest).map_err(|e| e.to_string())?;
    db.busy_timeout(Duration::from_secs(12)).map_err(|e| e.to_string())?;
    {
        let tx = db.transaction().map_err(|e| e.to_string())?;
        tx.execute_batch(
            "CREATE TABLE IF NOT EXISTS runs (
                 id INTEGER PRIMARY KEY AUTOINCREMENT, created TEXT NOT NULL,
                 category TEXT NOT NULL, label TEXT NOT NULL, ok INTEGER NOT NULL,
                 elapsed_ms REAL NOT NULL, source_hash TEXT NOT NULL, details TEXT NOT NULL
             );
             CREATE TABLE IF NOT EXISTS native_sessions (
                 id INTEGER PRIMARY KEY, timestamp TEXT NOT NULL, label TEXT NOT NULL,
                 git_sha TEXT NOT NULL, source_hash TEXT NOT NULL,
                 dirty INTEGER NOT NULL, platform TEXT NOT NULL, total_ms REAL NOT NULL
             );
             CREATE TABLE IF NOT EXISTS native_results (
                 session_id INTEGER NOT NULL, test_id TEXT NOT NULL,
                 category TEXT NOT NULL, status TEXT NOT NULL,
                 elapsed_ms REAL NOT NULL, error TEXT NOT NULL, source TEXT NOT NULL,
                 peak_rss_mb REAL, cpu_ms REAL, test_ms REAL,
                 PRIMARY KEY(session_id,test_id)
             );
             CREATE TABLE IF NOT EXISTS native_baseline (
                 name TEXT PRIMARY KEY, session_id INTEGER NOT NULL
             );
             CREATE TABLE IF NOT EXISTS studio_v5_jobs (
                 id TEXT PRIMARY KEY, kind TEXT NOT NULL, status TEXT NOT NULL,
                 updated TEXT NOT NULL
             );
             CREATE INDEX IF NOT EXISTS idx_native_results_session ON native_results(session_id);
             CREATE INDEX IF NOT EXISTS idx_runs_category ON runs(category,id);
             PRAGMA user_version = 5;"
        ).map_err(|e| e.to_string())?;
        let has_test_ms: i64 = tx.query_row(
            "SELECT COUNT(*) FROM pragma_table_info('native_results') WHERE name='test_ms'",
            [], |r| r.get(0)).map_err(|e| e.to_string())?;
        if has_test_ms == 0 {
            tx.execute("ALTER TABLE native_results ADD COLUMN test_ms REAL", [])
                .map_err(|e| e.to_string())?;
        }
        tx.commit().map_err(|e| e.to_string())?;
    }
    verify(&db)?;
    Ok(dest)
}

fn now() -> String {
    SystemTime::now().duration_since(UNIX_EPOCH)
        .unwrap_or_default().as_secs().to_string()
}

fn connect() -> Result<Connection, String> {
    let path = initialize()?;
    Connection::open(path).map_err(|e| e.to_string())
}

pub fn overview() -> Result<Value, String> {
    let db = connect()?;
    let mut counts = serde_json::Map::new();
    for table in ["runs", "native_sessions", "native_results", "native_baseline"] {
        counts.insert(table.to_string(), json!(count_table(&db, table)?));
    }
    let baseline: Option<i64> = db.query_row(
        "SELECT session_id FROM native_baseline WHERE name='default'", [], |r| r.get(0)
    ).optional().map_err(|e| e.to_string())?;
    Ok(json!({"counts":counts,"baseline":baseline,"v5_path":path_v5()?.to_string_lossy()}))
}
use rusqlite::OptionalExtension;

pub fn save_run(category: &str, label: &str, source: &str, ok: bool, elapsed_ms: f64, details: &Value)
    -> Result<i64, String> {
    let db = connect()?;
    let source_hash = format!("{:x}", Sha256::digest(source.as_bytes()));
    db.execute("INSERT INTO runs(created,category,label,ok,elapsed_ms,source_hash,details) VALUES (?1,?2,?3,?4,?5,?6,?7)",
      params![now(), category, label, i64::from(ok), elapsed_ms, &source_hash[..12], details.to_string()])
      .map_err(|e| e.to_string())?;
    Ok(db.last_insert_rowid())
}

pub fn recent_runs(limit: i64) -> Result<Value, String> {
    let db = connect()?;
    let mut query = db.prepare(
        "SELECT id,created,category,label,ok,elapsed_ms,source_hash,details FROM runs ORDER BY id DESC LIMIT ?1"
    ).map_err(|e| e.to_string())?;
    let rows = query.query_map([limit.clamp(1,1000)], |r| {
        let details: String = r.get(7)?;
        Ok(json!({
            "id":r.get::<_,i64>(0)?,"created":r.get::<_,String>(1)?,
            "category":r.get::<_,String>(2)?,"label":r.get::<_,String>(3)?,
            "ok":r.get::<_,i64>(4)? != 0,"elapsed_ms":r.get::<_,f64>(5)?,
            "source_hash":r.get::<_,String>(6)?,
            "details":serde_json::from_str::<Value>(&details).unwrap_or(Value::String(details))
        }))
    }).map_err(|e| e.to_string())?;
    rows.collect::<rusqlite::Result<Vec<_>>>().map(|x| json!(x)).map_err(|e| e.to_string())
}

fn git_metadata(root: Option<&Path>) -> (String, bool) {
    let Some(root) = root else { return ("unversioned".into(), false) };
    let call = |args: &[&str]| std::process::Command::new("git")
        .arg("-C").arg(root).args(args).output().ok();
    let sha = call(&["rev-parse","HEAD"]).and_then(|o|
        if o.status.success() { Some(String::from_utf8_lossy(&o.stdout).trim().to_string()) } else {None}
    ).unwrap_or_else(||"unversioned".into());
    let dirty = call(&["status","--porcelain","--","src","include","tests","CMakeLists.txt"])
        .is_some_and(|o|o.status.success() && !o.stdout.is_empty());
    (sha,dirty)
}

fn source_fingerprint(root: Option<&Path>) -> String {
    let Some(root)=root else { return "unavailable".into() };
    let mut digest=Sha256::new();
    // Studio 4 orders files lexically *within each parent*, with these
    // parents kept in declaration order. Reordering them changes baselines.
    for folder in ["src","include","tests/cpp","tests/portable"] {
        let base=root.join(folder);
        if !base.is_dir() { continue; }
        let mut paths:Vec<_> = walkdir::WalkDir::new(base).follow_links(false)
            .into_iter().filter_map(Result::ok).filter(|e|e.file_type().is_file())
            .map(|e|e.into_path())
            .filter(|p|matches!(p.extension().and_then(|x|x.to_str()),Some("cpp"|"hpp"|"h")))
            .collect();
        paths.sort();
        for p in paths {
            if let (Ok(rel), Ok(data))=(p.strip_prefix(root),fs::read(&p)) {
                // Preserve host separators, matching Python Path.__str__.
                digest.update(rel.to_string_lossy().as_bytes());
                digest.update(data);
            }
        }
    }
    format!("{:x}",digest.finalize())[..16].to_string()
}

pub fn save_native_session(label: &str, results: &[NativeResult], root: Option<&Path>) -> Result<i64, String> {
    let (sha,dirty)=git_metadata(root);
    let hash=source_fingerprint(root);
    let mut db=connect()?;
    let tx=db.transaction().map_err(|e| e.to_string())?;
    tx.execute("INSERT INTO native_sessions(timestamp,label,git_sha,source_hash,dirty,platform,total_ms)
                VALUES (?1,?2,?3,?4,?5,?6,?7)",
       params![now(),label,sha,hash,i64::from(dirty),std::env::consts::OS,
          results.iter().map(|r|r.elapsed_ms).sum::<f64>()])
       .map_err(|e|e.to_string())?;
    let sid=tx.last_insert_rowid();
    for r in results {
        tx.execute("INSERT INTO native_results(session_id,test_id,category,status,elapsed_ms,error,source,peak_rss_mb,cpu_ms,test_ms)
                    VALUES (?1,?2,?3,?4,?5,?6,?7,?8,?9,?10)",
            params![sid,r.id,r.group,r.status,r.elapsed_ms,r.error,r.source,r.peak_rss_mb,r.cpu_ms,r.test_ms])
            .map_err(|e|e.to_string())?;
    }
    tx.commit().map_err(|e|e.to_string())?;
    Ok(sid)
}

pub fn sessions(limit: i64) -> Result<Value, String> {
    let db=connect()?;
    let mut q=db.prepare("SELECT id,timestamp,label,git_sha,source_hash,dirty,platform,total_ms
                           FROM native_sessions ORDER BY id DESC LIMIT ?1").map_err(|e|e.to_string())?;
    let rows=q.query_map([limit.clamp(1,200)], |r| Ok(json!({
        "id":r.get::<_,i64>(0)?,"timestamp":r.get::<_,String>(1)?,
        "label":r.get::<_,String>(2)?,"git_sha":r.get::<_,String>(3)?,
        "source_hash":r.get::<_,String>(4)?,"dirty":r.get::<_,i64>(5)? != 0,
        "platform":r.get::<_,String>(6)?,"total_ms":r.get::<_,f64>(7)?
    }))).map_err(|e|e.to_string())?;
    rows.collect::<rusqlite::Result<Vec<_>>>().map(|v|json!(v)).map_err(|e|e.to_string())
}

pub fn native_results(session_id:i64) -> Result<Value,String> {
    let db=connect()?;
    let mut q=db.prepare("SELECT test_id,category,status,elapsed_ms,error,source,peak_rss_mb,cpu_ms,test_ms
                         FROM native_results WHERE session_id=?1").map_err(|e|e.to_string())?;
    let rows=q.query_map([session_id], |r| Ok(json!({
        "id":r.get::<_,String>(0)?,"group":r.get::<_,String>(1)?,
        "status":r.get::<_,String>(2)?,"elapsed_ms":r.get::<_,f64>(3)?,
        "error":r.get::<_,String>(4)?,"source":r.get::<_,String>(5)?,
        "peak_rss_mb":r.get::<_,Option<f64>>(6)?,"cpu_ms":r.get::<_,Option<f64>>(7)?,
        "test_ms":r.get::<_,Option<f64>>(8)?
    }))).map_err(|e|e.to_string())?;
    rows.collect::<rusqlite::Result<Vec<_>>>().map(|v|json!(v)).map_err(|e|e.to_string())
}

pub fn baseline(session_id:i64) -> Result<(),String> {
    let db=connect()?;
    let found:i64=db.query_row("SELECT count(*) FROM native_sessions WHERE id=?1",[session_id],|r|r.get(0))
        .map_err(|e|e.to_string())?;
    if found!=1{return Err("Unknown native test session".into());}
    db.execute("INSERT OR REPLACE INTO native_baseline(name,session_id) VALUES ('default',?1)",[session_id])
      .map_err(|e|e.to_string())?;
    Ok(())
}

pub fn compare(base_id:i64,current_id:i64)->Result<Value,String>{
    let previous=native_results(base_id)?;
    let current=native_results(current_id)?;
    let b=previous.as_array().ok_or("Invalid baseline result array")?;
    let c=current.as_array().ok_or("Invalid current result array")?;
    let mut old=std::collections::HashMap::new();
    for v in b { if let Some(id)=v["id"].as_str(){old.insert(id.to_string(),v);} }
    let mut now=std::collections::HashMap::new();
    for v in c { if let Some(id)=v["id"].as_str(){now.insert(id.to_string(),v);} }
    let mut introduced=Vec::new();let mut fixed=Vec::new();let mut remaining=Vec::new();
    let mut added=Vec::new();let mut missing=Vec::new();let mut timings=serde_json::Map::new();
    for (id,n) in &now {
        if let Some(o)=old.get(id){
            let old_pass=o["status"]=="PASS";let new_pass=n["status"]=="PASS";
            if old_pass && !new_pass{introduced.push(id.clone());}
            if !old_pass && new_pass{fixed.push(id.clone());}
            if !old_pass && !new_pass{remaining.push(id.clone());}
            if old_pass && new_pass {
                let body=o["test_ms"].as_f64().is_some() && n["test_ms"].as_f64().is_some();
                let key=if body{"test_ms"}else{"elapsed_ms"};
                if let (Some(a),Some(z))=(o[key].as_f64(),n[key].as_f64()) {
                    timings.insert(id.clone(),json!({"before_ms":a,"after_ms":z,"delta_ms":z-a,
                        "delta_pct":if a>0.0{Some(100.0*(z-a)/a)}else{None},
                        "metric":if body{"body"}else{"wall"}}));
                }
            }
        } else {added.push(id.clone());}
    }
    for id in old.keys(){if !now.contains_key(id){missing.push(id.clone());}}
    for a in [&mut introduced,&mut fixed,&mut remaining,&mut added,&mut missing]{a.sort();}
    let db=connect()?;
    let get_meta=|id:i64|->Result<Value,String>{
       db.query_row("SELECT id,timestamp,label,git_sha,source_hash,dirty,platform,total_ms FROM native_sessions WHERE id=?1",
         [id],|r|Ok(json!({
            "id":r.get::<_,i64>(0)?,"timestamp":r.get::<_,String>(1)?,
            "label":r.get::<_,String>(2)?,"git_sha":r.get::<_,String>(3)?,
            "source_hash":r.get::<_,String>(4)?,"dirty":r.get::<_,i64>(5)?!=0,
            "platform":r.get::<_,String>(6)?,"total_ms":r.get::<_,f64>(7)?
         }))).map_err(|e|e.to_string())
    };
    let bmeta=get_meta(base_id)?;
    let cmeta=get_meta(current_id)?;
    Ok(json!({"introduced":introduced,"fixed":fixed,"remaining_failures":remaining,
      "added":added,"missing":missing,"performance":timings,"baseline":bmeta,
      "current":cmeta,"comparable_platform":bmeta["platform"]==cmeta["platform"],
      "same_source":bmeta["source_hash"]==cmeta["source_hash"]}))
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test] fn unsupported_table_name_rejected(){
        let db=Connection::open_in_memory().unwrap();
        assert!(count_table(&db,"made_up").is_err());
    }
    #[test] fn real_disk_studio4_migration_is_lossless_and_read_only(){
        let base=std::env::temp_dir().join(format!("studio5-migration-fixture-{}-{}",
            std::process::id(),SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_nanos()));
        std::fs::create_dir_all(&base).unwrap();
        let old=base.join("studio.db");
        {
            let db=Connection::open(&old).unwrap();
            db.execute_batch(
                "CREATE TABLE runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,created TEXT NOT NULL,category TEXT NOT NULL,
                    label TEXT NOT NULL,ok INTEGER NOT NULL,elapsed_ms REAL NOT NULL,
                    source_hash TEXT NOT NULL,details TEXT NOT NULL
                );
                CREATE TABLE native_sessions (
                    id INTEGER PRIMARY KEY,timestamp TEXT NOT NULL,label TEXT NOT NULL,
                    git_sha TEXT NOT NULL,source_hash TEXT NOT NULL,dirty INTEGER NOT NULL,
                    platform TEXT NOT NULL,total_ms REAL NOT NULL
                );
                CREATE TABLE native_results (
                    session_id INTEGER NOT NULL,test_id TEXT NOT NULL,category TEXT NOT NULL,
                    status TEXT NOT NULL,elapsed_ms REAL NOT NULL,error TEXT NOT NULL,
                    source TEXT NOT NULL,peak_rss_mb REAL,cpu_ms REAL,
                    PRIMARY KEY(session_id,test_id)
                );
                CREATE TABLE native_baseline (name TEXT PRIMARY KEY,session_id INTEGER NOT NULL);
                INSERT INTO runs(created,category,label,ok,elapsed_ms,source_hash,details)
                    VALUES('old','Run','historic',1,2.5,'hash','{}');
                INSERT INTO native_sessions VALUES
                    (7,'old','full','sha','hash',0,'linux',12.0);
                INSERT INTO native_results VALUES
                    (7,'Parser.Case','Parser','FAIL',12.0,'historical','tests/portable/parser.cpp',NULL,NULL);
                INSERT INTO native_baseline VALUES('default',7);"
            ).unwrap();
        }
        let old_hash=Sha256::digest(fs::read(&old).unwrap());
        let target=base.join("studio-v5.db");
        initialize_at(target.clone()).unwrap();
        let migrated=Connection::open(&target).unwrap();
        for table in ["runs","native_sessions","native_results","native_baseline"]{
            assert_eq!(count_table(&migrated,table).unwrap(),1,"table {table}");
        }
        assert_eq!(migrated.query_row("SELECT session_id FROM native_baseline WHERE name='default'",
            [],|r|r.get::<_,i64>(0)).unwrap(),7);
        assert_eq!(migrated.query_row("SELECT test_ms FROM native_results LIMIT 1",
            [],|r|r.get::<_,Option<f64>>(0)).unwrap(),None);
        let _=initialize_at(target).unwrap(); // repeated init must not overwrite rows
        assert_eq!(Sha256::digest(fs::read(&old).unwrap()),old_hash);
        drop(migrated);
        fs::remove_dir_all(base).unwrap();
    }

    #[test] fn sqlite_backup_preserves_original_rows(){
        let original=Connection::open_in_memory().unwrap();
        original.execute_batch("CREATE TABLE runs (id INTEGER PRIMARY KEY, label TEXT);
          INSERT INTO runs(label) VALUES ('persist me');").unwrap();
        let mut snapshot=Connection::open_in_memory().unwrap();
        let backup=Backup::new(&original,&mut snapshot).unwrap();
        backup.run_to_completion(32,Duration::from_millis(1),None).unwrap();
        drop(backup);
        assert_eq!(count_table(&original,"runs").unwrap(),1);
        assert_eq!(count_table(&snapshot,"runs").unwrap(),1);
        snapshot.execute("INSERT INTO runs(label) VALUES ('v5 only')",[]).unwrap();
        assert_eq!(count_table(&original,"runs").unwrap(),1);
        assert_eq!(count_table(&snapshot,"runs").unwrap(),2);
    }
}
