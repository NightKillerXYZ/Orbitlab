"""Simple run-directory cleanup: delete subdirs older than retention hours."""
from __future__ import annotations
import shutil
import time
from pathlib import Path

def get_run_root(explicit=None) -> Path:
    import tempfile
    base = Path(explicit).expanduser() if explicit else Path(tempfile.gettempdir()) / "orbitlab-runs"
    base.mkdir(parents=True, exist_ok=True)
    return base

def cleanup_old_run_dirs(root, max_age_hours: float = 24.0) -> int:
    """Delete immediate subdirectories of root older than max_age_hours (by mtime). Returns count deleted."""
    try:
        age_s = float(max_age_hours) * 3600.0
    except Exception:
        age_s = 24.0 * 3600.0
    if age_s < 0:
        return 0
    root = Path(root)
    if not root.is_dir():
        return 0
    now = time.time()
    deleted = 0
    for child in root.iterdir():
        try:
            if not child.is_dir() and not child.is_symlink():
                continue
            mtime = child.stat().st_mtime
            if now - mtime > age_s:
                if child.is_symlink():
                    child.unlink()
                else:
                    shutil.rmtree(child, ignore_errors=True)
                deleted += 1
        except Exception:
            continue
    return deleted
