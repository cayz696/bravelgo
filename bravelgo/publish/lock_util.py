"""Single publish worker — clear stale locks, avoid false 'already running'."""
from __future__ import annotations

import os
import re
import time
from pathlib import Path

LOCK_F = Path.home() / ".bravelgo-publish.lock"
STALE_SEC = 6 * 3600


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def read_lock_pid() -> int | None:
    if not LOCK_F.is_file():
        return None
    try:
        text = LOCK_F.read_text(encoding="utf-8", errors="ignore")
        m = re.search(r"pid=(\d+)", text)
        return int(m.group(1)) if m else None
    except OSError:
        return None


def lock_age_sec() -> float | None:
    try:
        return time.time() - LOCK_F.stat().st_mtime
    except OSError:
        return None


def is_publish_running() -> bool:
    pid = read_lock_pid()
    if pid and _pid_alive(pid):
        return True
    if LOCK_F.is_file():
        age = lock_age_sec()
        if age is not None and age < 3:
            return True
    return False


def clear_stale_publish_lock(log=None, *, force: bool = False) -> bool:
    """
    Remove lock / stop dead worker. Returns True if something was cleared.
    """
    cleared = False
    pid = read_lock_pid()

    if pid and _pid_alive(pid):
        if force:
            try:
                os.kill(pid, 15)
                time.sleep(0.5)
                if _pid_alive(pid):
                    os.kill(pid, 9)
            except OSError:
                pass
            cleared = True
            if log:
                log(f"Stopped previous publish worker (pid {pid})")
        else:
            return False
    elif pid:
        cleared = True
        if log:
            log(f"Cleared stale publish lock (pid {pid} was gone)")

    try:
        if LOCK_F.is_file():
            age = lock_age_sec()
            if force or not pid or not _pid_alive(pid):
                if force or age is None or age > STALE_SEC or not pid:
                    LOCK_F.unlink(missing_ok=True)
                    cleared = True
    except OSError:
        pass

    return cleared


def try_acquire_lock() -> tuple[object | None, str]:
    """
    Returns (file_handle, error_message).
    file_handle must stay open until publish finishes.
    """
    import fcntl

    clear_stale_publish_lock()

    LOCK_F.parent.mkdir(parents=True, exist_ok=True)
    fh = open(LOCK_F, "w", encoding="utf-8")
    try:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        fh.close()
        pid = read_lock_pid()
        if pid and _pid_alive(pid):
            return None, f"Publish already running (pid {pid}) — wait or Tail log"
        clear_stale_publish_lock(force=True)
        fh = open(LOCK_F, "w", encoding="utf-8")
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            fh.close()
            return None, "Publish lock busy — try again in a few seconds"

    fh.write(f"pid={os.getpid()}\nstep=worker\n")
    fh.flush()
    return fh, ""


def stop_publish_workers(log=None) -> None:
    """Stop any detached run_publish.py so Full publish does not fight with old Generate."""
    import subprocess

    pid = read_lock_pid()
    if pid and _pid_alive(pid):
        try:
            os.kill(pid, 15)
            time.sleep(0.4)
            if _pid_alive(pid):
                os.kill(pid, 9)
        except OSError:
            pass
        if log:
            log(f"Stopped publish worker pid {pid}")
    clear_stale_publish_lock(force=True)
    try:
        subprocess.run(
            ["pkill", "-f", "run_publish.py"],
            capture_output=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        pass
    time.sleep(0.3)


def release_lock(fh) -> None:
    import fcntl

    try:
        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        fh.close()
    except OSError:
        pass
    try:
        LOCK_F.unlink(missing_ok=True)
    except OSError:
        pass
