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
from bravelgo.publish.runner import run_publish  # noqa: E402

CONFIG_F = Path.home() / ".bravelgo.json"
LOG_F = Path.home() / ".bravelgo-publish.log"


def load_cfg() -> dict:
    if CONFIG_F.is_file():
        with open(CONFIG_F, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_cfg(cfg: dict) -> None:
    with open(CONFIG_F, "w", encoding="utf-8") as f:
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
    args = parser.parse_args()

    lock, err = try_acquire_lock()
    if lock is None:
        print(f"[*] FATAL: {err}", flush=True)
        try:
            with open(LOG_F, "a", encoding="utf-8") as f:
                f.write(f"[*] FATAL: {err}\n")
        except OSError:
            pass
        sys.exit(2)

    cfg = load_cfg()
    pub = merge_publish_config(cfg)
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

    STEP_NOTE = {
        "generate": "NO Firefox — only Gemini API → saves listing + policy to cache",
        "docs": "Opens Firefox → Google Docs → privacy URL (needs cached texts)",
        "console": "Opens Firefox → Play Console (needs cached texts)",
        "all": "Opens Firefox → wait Console → Docs → Console (NO Gemini)",
    }
    LOG_F.write_text(f"=== Publish {args.step} · pid={os.getpid()} ===\n", encoding="utf-8")
    log(f"Worker started · step={args.step} · pid={os.getpid()}")
    log(STEP_NOTE.get(args.step, args.step))
    log(f"Package: {pub.get('package_name')} · App: {pub.get('app_name')}")

    try:
        result = run_publish(
            args.profile_dir or None,
            cfg,
            log,
            user_home=os.environ.get("HOME", str(Path.home())),
            step=args.step,
            skip_create=args.skip_create or pub.get("app_already_exists", False),
            wait_console=not args.no_wait_console,
            use_vision=not args.no_vision,
        )
        save_cfg(cfg)
        if result.get("privacy_url"):
            log(f"Privacy URL: {result['privacy_url']}")
        log("Done")
    except Exception as exc:
        log(f"FATAL: {exc}")
        sys.exit(1)
    finally:
        release_lock(lock)


if __name__ == "__main__":
    main()
