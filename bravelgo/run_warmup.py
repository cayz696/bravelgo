#!/usr/bin/env python3
"""CLI warmup — run as desktop user: python3 bravelgo/run_warmup.py ..."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))

from bravelgo.core.warmup import run_warmup  # noqa: E402
from bravelgo.warmup_geo import pick_sites  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="BravelGo human-like Firefox warmup")
    parser.add_argument("--profile-dir", required=True)
    parser.add_argument("--country", default="FR")
    parser.add_argument("--max-sites", type=int, default=6)
    parser.add_argument("--lang-mode", choices=["geo", "en", "mixed"], default="geo")
    parser.add_argument("--bridge-port", type=int, default=8118)
    parser.add_argument("--minutes", type=int, default=15)
    parser.add_argument("--urls-file")
    parser.add_argument("--no-images", action="store_true")
    parser.add_argument("--no-maps", action="store_true")
    parser.add_argument("--no-background-safe", action="store_true")
    args = parser.parse_args()

    urls = None
    if args.urls_file:
        urls = [
            ln.strip()
            for ln in Path(args.urls_file).read_text(encoding="utf-8").splitlines()
            if ln.strip() and not ln.startswith("#")
        ]
    else:
        urls = pick_sites(args.country, args.max_sites + 2)

    real_user = Path.home().name
    log_path = Path.home() / ".bravelgo-warmup.log"

    def log(msg: str) -> None:
        line = msg if msg.startswith("[") else f"[*] {msg}"
        print(line, flush=True)
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            pass

    log_path.write_text(f"=== Warmup session {args.country} ===\n", encoding="utf-8")

    run_warmup(
        real_user,
        Path(args.profile_dir),
        args.country,
        urls,
        log,
        max_sites=args.max_sites,
        lang_mode=args.lang_mode,
        bridge_port=args.bridge_port,
        session_minutes=args.minutes,
        google_images=not args.no_images,
        google_maps=not args.no_maps,
        background_safe=not args.no_background_safe,
    )


if __name__ == "__main__":
    main()
