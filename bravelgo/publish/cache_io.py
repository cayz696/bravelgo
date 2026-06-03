"""Persist publish texts — always under desktop user HOME, not /root."""
from __future__ import annotations

import json
import os
from typing import Callable

from bravelgo.publish.paths import config_path, listing_cache_path, policy_cache_path


def listing_ready(listing: dict | None) -> bool:
    if not listing:
        return False
    return bool((listing.get("short") or "").strip() or (listing.get("full") or "").strip())


def load_listing_cache(home: str | None = None) -> dict | None:
    path = listing_cache_path(home)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if listing_ready(data) else None
    except (OSError, json.JSONDecodeError):
        return None


def load_policy_cache(home: str | None = None) -> str | None:
    path = policy_cache_path(home)
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8").strip()
    return text or None


def persist_texts(
    cfg: dict,
    *,
    listing: dict | None = None,
    policy: str | None = None,
    log: Callable[[str], None] | None = None,
    user_home: str | None = None,
) -> None:
    home = user_home or os.environ.get("HOME")
    pub = cfg.setdefault("publish", {})
    if listing and listing_ready(listing):
        pub["last_listing"] = listing
        try:
            listing_cache_path(home).write_text(
                json.dumps(listing, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            pass
    if policy:
        pub["last_policy_chars"] = len(policy)
        try:
            policy_cache_path(home).write_text(policy, encoding="utf-8")
        except OSError:
            pass
    cfg["publish"] = pub
    cfg_path = config_path(home)
    try:
        if cfg_path.is_file():
            disk = json.loads(cfg_path.read_text(encoding="utf-8"))
        else:
            disk = {}
        disk["publish"] = {**disk.get("publish", {}), **pub}
        cfg_path.write_text(json.dumps(disk, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as exc:
        if log:
            log(f"WARN: could not save {cfg_path}: {exc}")
    else:
        if log:
            parts = []
            if listing and listing_ready(listing):
                parts.append("listing")
            if policy:
                parts.append("policy")
            if parts:
                log(f"Saved {' + '.join(parts)} → {cfg_path.parent}")
