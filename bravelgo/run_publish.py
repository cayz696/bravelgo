#!/usr/bin/env python3
"""CLI publish — run as desktop user: python3 bravelgo/run_publish.py ..."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))

from bravelgo.publish.config import merge_publish_config  # noqa: E402
from bravelgo.publish.lock_util import release_lock, try_acquire_lock  # noqa: E402
from bravelgo.publish.paths import config_path, publish_log_path  # noqa: E402
from bravelgo.publish.runner import run_publish  # noqa: E402

LOG_F = publish_log_path()


def _home_from_args(args) -> str:
    return (getattr(args, "user_home", None) or os.environ.get("HOME") or str(Path.home())).strip()


def load_cfg(home: str) -> dict:
    path = config_path(home)
    if path.is_file():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_cfg(cfg: dict, home: str) -> None:
    path = config_path(home)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def main() -> None:
    parser = argparse.ArgumentParser(description="BravelGo Play publish automation")
    parser.add_argument("--profile-dir", default="", help="Auto-detect BravelGo Firefox profile if empty")
    parser.add_argument(
        "--step",
        choices=["all", "generate", "docs", "console"],
        default="all",
    )
    parser.add_argument("--skip-create", action="store_true")
    parser.add_argument("--no-wait-console", action="store_true")
    parser.add_argument("--no-vision", action="store_true")
    parser.add_argument("--skip-docs", action="store_true")
    parser.add_argument("--privacy-url", default="", help="Privacy URL from BravelGo form (required)")
    parser.add_argument("--user-home", default="", help="Desktop user home, e.g. /home/ahmed")
    args = parser.parse_args()

    home = _home_from_args(args)
    os.environ["HOME"] = home
    global LOG_F
    LOG_F = publish_log_path(home)

    from bravelgo.publish.lock_util import stop_publish_workers

    stop_publish_workers()

    lock, err = try_acquire_lock()
    if lock is None:
        print(f"[*] FATAL: {err}", flush=True)
        sys.exit(2)

    cfg = load_cfg(home)
    pub = merge_publish_config(cfg)
    if args.privacy_url.strip():
        pub["last_privacy_url"] = args.privacy_url.strip()
        cfg["publish"] = pub
    if args.skip_create:
        pub["app_already_exists"] = True
        cfg["publish"] = pub

    seen: set[str] = set()

    def log(msg: str) -> None:
        msg = (msg or "").strip()
        if msg.startswith("[*]"):
            msg = msg[3:].strip()
        if msg in seen:
            return
        seen.add(msg)
        line = f"[*] {msg}"
        print(line, flush=True)
        try:
            with open(LOG_F, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            pass

    LOG_F.write_text(f"=== Publish {args.step} · pid={os.getpid()} · home={home} ===\n", encoding="utf-8")
    log(f"Worker started · step={args.step} · pid={os.getpid()}")
    if pub.get("last_privacy_url"):
        log(f"Privacy URL: {pub['last_privacy_url'][:90]}…")
    else:
        log("WARN: Privacy URL empty in worker — paste in BravelGo and Save manual texts")

    try:
        result = run_publish(
            args.profile_dir or None,
            cfg,
            log,
            user_home=home,
            step=args.step,
            skip_create=args.skip_create or pub.get("app_already_exists", False),
            wait_console=not args.no_wait_console,
            use_vision=not args.no_vision,
            skip_docs=bool(args.skip_docs) or bool(pub.get("skip_docs_flow")) or bool(pub.get("last_privacy_url")),
        )
        save_cfg(cfg, home)
        if result.get("privacy_url"):
            log(f"Privacy URL: {result['privacy_url']}")
        log("Done")
    except Exception as exc:
        import traceback

        log(f"FATAL: {exc}")
        for ln in traceback.format_exc().splitlines()[-8:]:
            if ln.strip():
                log(ln)
        sys.exit(1)
    finally:
        release_lock(lock)


if __name__ == "__main__":
    main()
