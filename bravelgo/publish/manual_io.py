"""Manual store listing + privacy URL (no Gemini)."""
from __future__ import annotations

from typing import Callable

from bravelgo.publish.cache_io import listing_ready, load_policy_cache, persist_texts


def listing_from_pub(pub: dict, app_name: str = "") -> dict[str, str]:
    raw = pub.get("last_listing") if isinstance(pub.get("last_listing"), dict) else {}
    title = (raw.get("title") or app_name or "").strip()[:30]
    return {
        "title": title,
        "short": (raw.get("short") or "").strip()[:80],
        "full": (raw.get("full") or "").strip()[:4000],
        "raw": raw.get("raw", ""),
    }


def policy_from_pub(pub: dict, home: str | None = None) -> str:
    text = (pub.get("manual_policy_text") or "").strip()
    if text:
        return text
    return load_policy_cache(home) or ""


def privacy_url_from_pub(pub: dict) -> str:
    return (pub.get("last_privacy_url") or "").strip()


def should_skip_docs(pub: dict, skip_docs_flag: bool = False) -> bool:
    """Privacy URL in BravelGo = do not create a new doc in Google Docs."""
    return bool(skip_docs_flag) or bool(pub.get("skip_docs_flow")) or bool(privacy_url_from_pub(pub))


def save_manual_to_cache(
    cfg: dict,
    pub: dict,
    log: Callable[[str], None] | None = None,
    *,
    user_home: str | None = None,
) -> None:
    listing = listing_from_pub(pub, pub.get("app_name", ""))
    policy = policy_from_pub(pub, user_home)
    persist_texts(
        cfg,
        listing=listing if listing_ready(listing) else None,
        policy=policy or None,
        log=log,
        user_home=user_home,
    )


def validate_for_browser_step(pub: dict, step: str) -> None:
    app = (pub.get("app_name") or "").strip()
    listing = listing_from_pub(pub, app)
    if not listing_ready(listing):
        raise ValueError(
            "Store listing incomplete — fill Title, Short (80), Full description, then «Save manual texts»"
        )

    url = privacy_url_from_pub(pub)
    skip_docs = should_skip_docs(pub)

    if step in ("all", "console") and not url:
        raise ValueError(
            "Privacy policy URL is empty — paste your link in «Privacy policy URL» and Save manual texts"
        )

    if step in ("all", "docs") and not skip_docs:
        if not policy_from_pub(pub):
            raise ValueError(
                "Privacy text empty — paste policy in the form, or check «Skip Google Docs» if you have the URL"
            )
