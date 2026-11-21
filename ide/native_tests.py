"""Portable native C++ test discovery, isolated execution and regression history."""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import psutil
except ImportError:
    psutil = None


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE = Path.home() / ".plusminus" / "studio.db"


def find_native_runner(root: Path = ROOT):
    names = ("plusminus_native_tests.exe", "plusminus_native_tests")
    base = Path(getattr(sys, "_MEIPASS", root)) if getattr(sys, "frozen", False) else root
    directories = [base, base / "ide" / "build", base / "ide" / "build" / "plusminus-root",
                   base / "ide" / "build" / "plusminus-root" / "Release",
                   base / "ide" / "build" / "Release", base / "build",
                   base / "build" / "Release", Path(sys.executable).parent]
    for directory in directories:
        for name in names:
            candidate = directory / name
            if candidate.is_file():
                return candidate
    return None


def discover_native_tests(binary, timeout=12):
    run = subprocess.run([str(binary), "--list"], capture_output=True,
                         text=True, timeout=timeout, check=False,
                         encoding="utf-8", errors="replace")
    if run.returncode:
        raise RuntimeError(f"Native tests cannot be listed: {run.stderr[-1000:]}")
    cases = []
    for line in run.stdout.splitlines():
        if not line.strip():
            continue
        case = json.loads(line)
        if case.get("type") != "test" or not isinstance(case.get("id"), str):
            raise ValueError("Invalid native test manifest")
        cases.append(case)
    if not cases:
        raise RuntimeError("No native test methods were discovered")
    if len(cases) != len({x["id"] for x in cases}):
        raise RuntimeError("Duplicate native test IDs")
    return cases


def _read_git(root):
    def command(*args):
        try:
            out = subprocess.run(["git", "-C", str(root), *args],
                                 capture_output=True, text=True,
                                 timeout=4, check=False)
            return out.stdout.strip() if out.returncode == 0 else ""
        except (OSError, subprocess.TimeoutExpired):
            return ""
    return command("rev-parse", "HEAD") or "unversioned", bool(command("status", "--porcelain", "--", "src", "include", "tests", "CMakeLists.txt"))


def source_fingerprint(root=ROOT):
    digest = hashlib.sha256()
    for parent in ("src", "include", "tests/cpp", "tests/portable"):
        folder = root / parent
        if not folder.exists():
            continue
        for path in sorted(p for p in folder.rglob("*") if p.is_file() and p.suffix in (".cpp", ".hpp", ".h")):
            digest.update(str(path.relative_to(root)).encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()[:16]


def run_native_case(binary, case, cancel=None, timeout=20):
    """One OS process per test: a crash/timeout cannot terminate the GUI."""
    cancel = cancel or threading.Event()
    start = time.perf_counter()
    process = None
    text = ""
    stderr = ""
    status = "ERROR"
    error = ""
    peak_rss = None
    cpu_ms = None
    try:
        if cancel.is_set():
            raise InterruptedError("Canceled")
        process = subprocess.Popen(
            [str(binary), "--run", case["id"]], stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        proc = None
        if psutil:
            try:
                proc = psutil.Process(process.pid)
            except (psutil.Error, OSError):
                pass
        while True:
            if cancel.is_set():
                raise InterruptedError("Canceled")
            if time.perf_counter() - start >= timeout:
                raise subprocess.TimeoutExpired(str(binary), timeout)
            try:
                out, err = process.communicate(timeout=0.04)
                text = out.decode("utf-8", errors="replace")
                stderr = err.decode("utf-8", errors="replace")
                break
            except subprocess.TimeoutExpired:
                if proc is not None:
                    try:
                        peak_rss = max(peak_rss or 0, proc.memory_info().rss / 1048576)
                        clock = proc.cpu_times()
                        cpu_ms = (clock.user + clock.system) * 1000
                    except (OSError, psutil.Error):
                        proc = None
        line = next((item for item in text.splitlines() if '"type":"result"' in item), None)
        if line is None:
            raise ValueError("Native test returned no JSON result")
        result = json.loads(line)
        if result.get("id") != case["id"] or result.get("status") not in ("PASS", "FAIL"):
            raise ValueError("Native test returned a mismatched result")
        status = result["status"]
        error = str(result.get("error", ""))
        if process.returncode != (0 if status == "PASS" else 1):
            status, error = "ERROR", f"Native runner exit code {process.returncode}: {stderr}"
    except subprocess.TimeoutExpired:
        status, error = "TIMEOUT", f"Time limit exceeded ({timeout:g} s)"
    except InterruptedError:
        status, error = "CANCELED", "Execution canceled"
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        status, error = "ERROR", str(exc)
    finally:
        if process and process.poll() is None:
            process.kill()
            process.communicate()
    return {
        "id": case["id"], "group": case["group"], "source": case.get("source", ""),
        "slow": bool(case.get("slow")), "status": status, "error": error[:4000],
        "elapsed_ms": round((time.perf_counter()-start)*1000, 3),
        "peak_rss_mb": round(peak_rss, 3) if peak_rss is not None else None,
        "cpu_ms": round(cpu_ms, 3) if cpu_ms is not None else None,
    }


def run_native_batch(binary, cases, cancel=None, normal_timeout=20, slow_timeout=180):
    results = []
    for case in cases:
        if cancel is not None and cancel.is_set():
            break
        results.append(run_native_case(
            binary, case, cancel, slow_timeout if case.get("slow") else normal_timeout))
    return results


class NativeHistory:
    def __init__(self, path=DEFAULT_DATABASE):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS native_sessions (
                    id INTEGER PRIMARY KEY, timestamp TEXT NOT NULL, label TEXT NOT NULL,
                    git_sha TEXT NOT NULL, source_hash TEXT NOT NULL,
                    dirty INTEGER NOT NULL, platform TEXT NOT NULL, total_ms REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS native_results (
                    session_id INTEGER NOT NULL, test_id TEXT NOT NULL,
                    category TEXT NOT NULL, status TEXT NOT NULL,
                    elapsed_ms REAL NOT NULL, error TEXT NOT NULL, source TEXT NOT NULL,
                    peak_rss_mb REAL, cpu_ms REAL,
                    PRIMARY KEY(session_id, test_id),
                    FOREIGN KEY(session_id) REFERENCES native_sessions(id)
                );
                CREATE TABLE IF NOT EXISTS native_baseline (
                    name TEXT PRIMARY KEY, session_id INTEGER NOT NULL
                );
            """)

    def _connect(self):
        connection = sqlite3.connect(str(self.path), timeout=12)
        connection.execute("PRAGMA busy_timeout=12000")
        return connection

    def save(self, label, results, root=ROOT):
        git_sha, dirty = _read_git(root)
        with self._connect() as db:
            cursor = db.execute(
                """INSERT INTO native_sessions
                   (timestamp,label,git_sha,source_hash,dirty,platform,total_ms)
                   VALUES (?,?,?,?,?,?,?)""",
                (datetime.now(timezone.utc).isoformat(timespec="seconds"),
                 label, git_sha, source_fingerprint(root), int(dirty),
                 sys.platform, sum(r["elapsed_ms"] for r in results)))
            session = int(cursor.lastrowid)
            for r in results:
                db.execute(
                    """INSERT INTO native_results
                       (session_id,test_id,category,status,elapsed_ms,error,source,
                        peak_rss_mb,cpu_ms) VALUES (?,?,?,?,?,?,?,?,?)""",
                    (session, r["id"], r["group"], r["status"], r["elapsed_ms"],
                     r["error"], r["source"], r.get("peak_rss_mb"), r.get("cpu_ms")))
        return session

    def recent(self, limit=50):
        with self._connect() as db:
            rows = db.execute(
                """SELECT id,timestamp,label,git_sha,source_hash,dirty,platform,total_ms
                   FROM native_sessions ORDER BY id DESC LIMIT ?""", (limit,)).fetchall()
        keys = ("id","timestamp","label","git_sha","source_hash","dirty","platform","total_ms")
        return [dict(zip(keys,row)) for row in rows]

    def results(self, session_id):
        with self._connect() as db:
            rows = db.execute(
                """SELECT test_id,category,status,elapsed_ms,error,source,peak_rss_mb,cpu_ms
                   FROM native_results WHERE session_id=?""",
                (session_id,)).fetchall()
        keys = ("id","group","status","elapsed_ms","error","source","peak_rss_mb","cpu_ms")
        return {row[0]:dict(zip(keys,row)) for row in rows}

    def set_baseline(self, session_id):
        with self._connect() as db:
            if not db.execute("SELECT 1 FROM native_sessions WHERE id=?", (session_id,)).fetchone():
                raise ValueError("Unknown session")
            db.execute(
                "INSERT OR REPLACE INTO native_baseline(name,session_id) VALUES('default',?)",
                (session_id,))

    def baseline(self):
        with self._connect() as db:
            result = db.execute(
                "SELECT session_id FROM native_baseline WHERE name='default'").fetchone()
        return result[0] if result else None

    def compare(self, baseline_id, current_id):
        previous, current = self.results(baseline_id), self.results(current_id)
        shared = set(previous) & set(current)
        introduced = sorted(k for k in shared if previous[k]["status"] == "PASS" and current[k]["status"] != "PASS")
        fixed = sorted(k for k in shared if previous[k]["status"] != "PASS" and current[k]["status"] == "PASS")
        remaining = sorted(k for k in shared if previous[k]["status"] != "PASS" and current[k]["status"] != "PASS")
        return {
            "introduced": introduced, "fixed": fixed, "remaining_failures": remaining,
            "added": sorted(set(current)-set(previous)),
            "missing": sorted(set(previous)-set(current)),
            "performance": {k: round(current[k]["elapsed_ms"]-previous[k]["elapsed_ms"],3)
                            for k in shared if previous[k]["status"]=="PASS"
                            and current[k]["status"]=="PASS"},
        }
