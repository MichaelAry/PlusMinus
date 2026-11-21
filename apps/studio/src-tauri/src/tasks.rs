//! Shared task registry for source executions and isolated C++ test batches.
//! Live progress survives frontend panel unmounts; completed test data are
//! separately committed transactionally to studio-v5.db by history.rs.
use serde::Serialize;
use std::{collections::HashMap,sync::Mutex,time::{SystemTime,UNIX_EPOCH}};
use tokio_util::sync::CancellationToken;

#[derive(Debug, Clone, Serialize)]
pub struct TaskSnapshot {
    pub job_id: String,
    pub kind: String,
    pub status: String,
    pub done: usize,
    pub total: usize,
    pub passed: usize,
    pub failed: usize,
    pub session_id: Option<i64>,
    pub error: Option<String>,
    pub created_at_ms: u128,
}

struct TaskRecord {
    snapshot: TaskSnapshot,
    token: CancellationToken,
}

#[derive(Default)]
pub struct TaskRegistry {
    inner: Mutex<HashMap<String, TaskRecord>>,
}

impl TaskRegistry {
    pub fn register(&self, job_id: &str, kind: &str, total: usize) -> Result<CancellationToken, String> {
        let mut entries = self.inner.lock().map_err(|e| e.to_string())?;
        if entries.contains_key(job_id) { return Err("Duplicate job ID".into()); }
        // Retain the most recent completed tasks, never discard active jobs.
        if entries.len() >= 512 {
            let mut finished: Vec<_> = entries.iter()
                .filter(|(_,r)| matches!(r.snapshot.status.as_str(),"completed"|"canceled"|"error"))
                .map(|(id,r)| (id.clone(),r.snapshot.created_at_ms))
                .collect();
            finished.sort_by_key(|(_,created)| *created);
            for (id,_) in finished.into_iter().take(entries.len().saturating_sub(255)) {
                entries.remove(&id);
            }
        }
        if entries.len() >= 512 { return Err("Too many concurrent tasks".into()); }
        let token = CancellationToken::new();
        let created_at_ms = SystemTime::now().duration_since(UNIX_EPOCH)
            .unwrap_or_default().as_millis();
        let snapshot = TaskSnapshot {
            job_id:job_id.into(),kind:kind.into(),status:"running".into(),done:0,total,
            passed:0,failed:0,session_id:None,error:None,created_at_ms,
        };
        entries.insert(job_id.into(),TaskRecord{snapshot,token:token.clone()});
        Ok(token)
    }

    pub fn advance(&self, job_id: &str, passed: bool) -> Result<(), String> {
        let mut entries = self.inner.lock().map_err(|e| e.to_string())?;
        let record = entries.get_mut(job_id).ok_or("Task not found")?;
        if record.snapshot.done >= record.snapshot.total { return Err("Progress exceeds total".into()); }
        if record.snapshot.status != "running" && record.snapshot.status != "cancel_requested" {
            return Err("Task has already finished".into());
        }
        record.snapshot.done += 1;
        if passed { record.snapshot.passed += 1; } else {record.snapshot.failed += 1;}
        Ok(())
    }

    pub fn complete(&self, job_id: &str, session_id: Option<i64>, canceled: bool, error: Option<String>) {
        if let Ok(mut entries) = self.inner.lock() {
            if let Some(record) = entries.get_mut(job_id) {
                let status = if canceled {"canceled"} else if error.is_some() {"error"} else {"completed"};
                record.snapshot.status = status.to_string();
                record.snapshot.session_id = session_id;
                record.snapshot.error = error;
            }
        }
    }

    pub fn cancel(&self, job_id: &str) -> Result<bool, String> {
        let mut entries = self.inner.lock().map_err(|e| e.to_string())?;
        if let Some(record) = entries.get_mut(job_id) {
            if matches!(record.snapshot.status.as_str(),"running"|"cancel_requested") {
                record.snapshot.status = "cancel_requested".into();
                record.token.cancel();
                return Ok(true);
            }
        }
        Ok(false)
    }

    pub fn snapshot(&self, job_id: &str) -> Result<Option<TaskSnapshot>, String> {
        let entries = self.inner.lock().map_err(|e|e.to_string())?;
        Ok(entries.get(job_id).map(|entry|entry.snapshot.clone()))
    }

    pub fn list(&self) -> Result<Vec<TaskSnapshot>, String> {
        let entries = self.inner.lock().map_err(|e|e.to_string())?;
        let mut rows:Vec<_> = entries.values().map(|r|r.snapshot.clone()).collect();
        rows.sort_by_key(|r|std::cmp::Reverse(r.created_at_ms));
        Ok(rows)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn task_registry_progress_and_cancellation() {
        let registry=TaskRegistry::default();
        let token=registry.register("job-one-01234","native-tests",3).unwrap();
        assert!(!token.is_cancelled());
        assert!(registry.register("job-one-01234","native-tests",3).is_err());
        registry.advance("job-one-01234",true).unwrap();
        registry.advance("job-one-01234",false).unwrap();
        let snapshot=registry.snapshot("job-one-01234").unwrap().unwrap();
        assert_eq!((snapshot.done,snapshot.total,snapshot.passed,snapshot.failed),(2,3,1,1));
        assert_eq!(snapshot.status,"running");
        assert!(registry.cancel("job-one-01234").unwrap());
        assert!(token.is_cancelled());
        registry.complete("job-one-01234",Some(17),true,None);
        let final_state=registry.snapshot("job-one-01234").unwrap().unwrap();
        assert_eq!(final_state.status,"canceled");
        assert_eq!(final_state.session_id,Some(17));
        assert!(!registry.cancel("job-one-01234").unwrap());
    }
    #[test]
    fn registry_rejects_impossible_progress() {
        let registry=TaskRegistry::default();
        registry.register("job-two-01234","source",1).unwrap();
        registry.advance("job-two-01234",true).unwrap();
        assert!(registry.advance("job-two-01234",true).is_err());
    }
}
