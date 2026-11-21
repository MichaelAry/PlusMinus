"""Early, durable crash diagnostics for PlusMinus Studio's Qt process.

Enabled automatically on Windows and optionally elsewhere with
PLUSMINUS_DIAGNOSTICS=1. An access violation cannot be caught in Python;
faulthandler can usually record the last active Python frame.
"""
from __future__ import annotations
import faulthandler
import os
from pathlib import Path
import platform
import sys
import traceback
from datetime import datetime, timezone

_STREAM = None
_ACTIVE = False


def safe_mode_requested(argv=None, environ=None):
    argv = sys.argv if argv is None else argv
    environ = os.environ if environ is None else environ
    return "--safe-mode" in argv or environ.get("PLUSMINUS_SAFE_MODE", "").lower() in ("1", "true", "yes")


def startup_log_path():
    return Path.home() / ".plusminus" / "studio-startup.log"


def mark(message):
    if _STREAM is None:
        return
    try:
        _STREAM.write(f"[{datetime.now(timezone.utc).isoformat(timespec='milliseconds')}] {message}\n")
        _STREAM.flush()
    except OSError:
        pass


def begin():
    global _STREAM, _ACTIVE
    if _ACTIVE:
        return
    _ACTIVE = True
    if sys.platform != "win32" and os.environ.get("PLUSMINUS_DIAGNOSTICS") != "1":
        return
    try:
        path = startup_log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        _STREAM = path.open("a", encoding="utf-8", buffering=1)
        faulthandler.enable(file=_STREAM, all_threads=True)
        mark("=" * 65)
        mark(f"Process started: Python={platform.python_version()} "
             f"platform={platform.platform()} pid={os.getpid()} "
             f"safe_mode={safe_mode_requested()}")
        previous = sys.excepthook

        def log_uncaught(exc_type, exc, tb):
            mark(f"UNCAUGHT {exc_type.__name__}: {exc}")
            try:
                traceback.print_exception(exc_type, exc, tb, file=_STREAM)
                _STREAM.flush()
            finally:
                previous(exc_type, exc, tb)

        sys.excepthook = log_uncaught
    except (OSError, RuntimeError) as exc:
        print(f"[PlusMinus] Crash logging unavailable: {exc}", file=sys.stderr)


def log_exception(exc):
    mark(f"Startup error: {type(exc).__name__}: {exc}")
    if _STREAM is not None:
        traceback.print_exception(type(exc), exc, exc.__traceback__, file=_STREAM)
        _STREAM.flush()
