"""Publish settings stored in ~/.bravelgo.json under key \"publish\"."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

DEFAULT_LISTING_LANG = "en-US"
DOCS_START_URL = "https://docs.google.com/document/u/0/?pli=1"
CONSOLE_URL = "https://play.google.com/console/"


def default_publish_config() -> dict[str, Any]:
    from bravelgo.publish.prompts import DEFAULT_LISTING_PROMPT, DEFAULT_PRIVACY_PROMPT

    return {
        "account_email": "",
        "package_name": "",
        "app_name": "",
        "gemini_api_key": "",
        "gemini_model": "gemini-2.5-flash",
        "listing_prompt": DEFAULT_LISTING_PROMPT,
        "privacy_prompt": DEFAULT_PRIVACY_PROMPT,
        "app_already_exists": False,
        "listing_locale": DEFAULT_LISTING_LANG,
        "graphics_dir": "",
        "texts_dir": "",
        "last_privacy_url": "",
        "last_listing": {},
        "manual_policy_text": "",
        "skip_docs_flow": False,
        "browser": "firefox",
        "use_vision": True,
        "wait_for_console": True,
        "detached": True,
        "use_stub_on_quota": True,
    }


def normalize_gemini_model(model: str) -> str:
    """2.0 models exhaust free quota faster — prefer 2.5-flash."""
    m = (model or "").strip()
    if not m or m.startswith("gemini-2.0"):
        return "gemini-2.5-flash"
    if m not in (
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
    ):
        return "gemini-2.5-flash"
    return m


def merge_publish_config(cfg: dict) -> dict[str, Any]:
    base = default_publish_config()
    raw = cfg.get("publish") if isinstance(cfg.get("publish"), dict) else {}
    base.update(raw)
    base["gemini_model"] = normalize_gemini_model(base.get("gemini_model", ""))
    # Default skip Docs when user has a privacy URL (manual workflow)
    if (base.get("last_privacy_url") or "").strip():
        base["skip_docs_flow"] = True
    elif "skip_docs_flow" not in raw:
        base["skip_docs_flow"] = True
    return base


def save_publish_section(cfg: dict, publish: dict[str, Any]) -> None:
    cfg["publish"] = publish
