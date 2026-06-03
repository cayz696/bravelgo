"""Single publish worker — one process at a time, no pkill suicide."""
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
        clear_stale_publish_lock(force=True)
    return False


def clear_stale_publish_lock(log=None, *, force: bool = False) -> bool:
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
    elif pid and log:
        log(f"Cleared stale lock (pid {pid} gone)")

    try:
        if LOCK_F.is_file() and (force or not pid or not _pid_alive(pid)):
            LOCK_F.unlink(missing_ok=True)
            cleared = True
    except OSError:
        pass

    return cleared


def try_acquire_lock() -> tuple[object | None, str]:
    import fcntl

    clear_stale_publish_lock(force=True)

    LOCK_F.parent.mkdir(parents=True, exist_ok=True)
    fh = open(LOCK_F, "w", encoding="utf-8")
    try:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        fh.close()
        pid = read_lock_pid()
        if pid and _pid_alive(pid):
            return None, f"Publish already running (pid {pid}) — Tail log or wait"
        clear_stale_publish_lock(force=True)
        fh = open(LOCK_F, "w", encoding="utf-8")
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            fh.close()
            return None, "Publish lock busy — try again in 5 seconds"

    fh.write(f"pid={os.getpid()}\nstep=worker\n")
    fh.flush()
    return fh, ""


def stop_publish_workers(log=None) -> None:
    """Stop only the previous lock-holder — never pkill (that killed the new worker)."""
    me = os.getpid()
    pid = read_lock_pid()
    if pid and pid != me and _pid_alive(pid):
        try:
            os.kill(pid, 15)
            time.sleep(0.5)
            if _pid_alive(pid):
                os.kill(pid, 9)
        except OSError:
            pass
        if log:
            log(f"Stopped old publish worker pid {pid}")
    clear_stale_publish_lock(force=True)
    time.sleep(0.2)


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
