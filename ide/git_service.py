"""Read-only local Git status, logs and diffs for Studio source checkouts."""
from pathlib import Path
import subprocess


def git_command(root, *args, timeout=3):
    try:
        p = subprocess.run(["git", "-C", str(Path(root).resolve()), *args],
                           capture_output=True, text=True, timeout=timeout,
                           encoding="utf-8", errors="replace", check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, str(exc)
    return (p.stdout.rstrip(), "") if p.returncode == 0 else (None, p.stderr.strip())


def repository_summary(root):
    branch, problem = git_command(root, "branch", "--show-current")
    if branch is None:
        return {"available": False, "error":problem or "Not a Git checkout"}
    sha, _ = git_command(root, "rev-parse", "--short", "HEAD")
    changed, _ = git_command(root, "status", "--short")
    stat, _ = git_command(root, "diff", "--stat")
    commits, _ = git_command(root, "log", "-6", "--date=short", "--pretty=format:%h %ad %s")
    return {"available":True,"branch":branch or "(detached)",
            "sha":sha or "unknown","changes":changed or "(clean)",
            "diff":stat or "(no unstaged diff)","commits":commits or "",
            "dirty":bool(changed)}
