"""Persist publish texts so Generate survives 429 and Full publish skips Gemini."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

POLICY_CACHE = Path.home() / ".bravelgo-publish-policy.txt"
LISTING_CACHE = Path.home() / ".bravelgo-publish-listing.json"
CONFIG_F = Path.home() / ".bravelgo.json"


def listing_ready(listing: dict | None) -> bool:
    if not listing:
        return False
    return bool((listing.get("short") or "").strip() or (listing.get("full") or "").strip())


def load_listing_cache() -> dict | None:
    if not LISTING_CACHE.is_file():
        return None
    try:
        data = json.loads(LISTING_CACHE.read_text(encoding="utf-8"))
        return data if listing_ready(data) else None
    except (OSError, json.JSONDecodeError):
        return None


def load_policy_cache() -> str | None:
    if not POLICY_CACHE.is_file():
        return None
    text = POLICY_CACHE.read_text(encoding="utf-8").strip()
    return text or None


def persist_texts(
    cfg: dict,
    *,
    listing: dict | None = None,
    policy: str | None = None,
    log: Callable[[str], None] | None = None,
) -> None:
    pub = cfg.setdefault("publish", {})
    if listing and listing_ready(listing):
        pub["last_listing"] = listing
        try:
            LISTING_CACHE.write_text(
                json.dumps(listing, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            pass
    if policy:
        pub["last_policy_chars"] = len(policy)
        try:
            POLICY_CACHE.write_text(policy, encoding="utf-8")
        except OSError:
            pass
    cfg["publish"] = pub
    try:
        if CONFIG_F.is_file():
            disk = json.loads(CONFIG_F.read_text(encoding="utf-8"))
        else:
            disk = {}
        disk["publish"] = {**disk.get("publish", {}), **pub}
        CONFIG_F.write_text(json.dumps(disk, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as exc:
        if log:
            log(f"WARN: could not save ~/.bravelgo.json: {exc}")
    else:
        if log:
            parts = []
            if listing and listing_ready(listing):
                parts.append("listing")
            if policy:
                parts.append("policy")
            if parts:
                log(f"Saved {' + '.join(parts)} → cache (Full publish can skip Gemini)")
