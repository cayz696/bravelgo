"""Orchestrate publish pipeline: generate → wait → docs → console."""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from bravelgo.publish.browser import close_browser, launch_context
from bravelgo.publish.cache_io import (
    listing_ready,
    load_listing_cache,
    load_policy_cache,
    persist_texts,
)
from bravelgo.publish.config import CONSOLE_URL, DOCS_START_URL, merge_publish_config
from bravelgo.publish.console_flow import run_console_setup, run_create_application
from bravelgo.publish.docs_flow import run_docs_flow
from bravelgo.publish.gemini import GeminiPublishError, generate_listing, generate_privacy, unique_seed
from bravelgo.publish.local_texts import try_load_local_texts
from bravelgo.publish.stub_texts import stub_listing, stub_policy
from bravelgo.publish.profile_resolve import resolve_profile_dir
from bravelgo.publish.ui_actions import PublishUI
from bravelgo.publish.wait_console import wait_for_console_ready


def _load_cached_texts(pub: dict, package: str, app_name: str, log: Callable[[str], None]) -> tuple[dict | None, str | None]:
    listing: dict | None = None
    if listing_ready(pub.get("last_listing")):
        listing = dict(pub.get("last_listing") or {})
    if not listing:
        listing = load_listing_cache()
        if listing:
            log("Loaded listing from ~/.bravelgo-publish-listing.json")

    policy = load_policy_cache()
    if policy:
        log(f"Loaded policy from cache ({len(policy)} chars)")

    texts_dir = pub.get("texts_dir", "")
    local_listing, local_policy = try_load_local_texts(package, app_name, texts_dir, log)
    if local_listing:
        listing = local_listing
    if local_policy:
        policy = local_policy
    return listing, policy


def _generate_texts(
    pub: dict,
    cfg: dict,
    package: str,
    app_name: str,
    email: str,
    api_key: str,
    log: Callable[[str], None],
) -> tuple[dict, str]:
    seed = unique_seed()
    texts_dir = pub.get("texts_dir", "")
    local_listing, local_policy = try_load_local_texts(package, app_name, texts_dir, log)
    use_local_only = pub.get("use_local_texts_only", False)

    listing = local_listing or load_listing_cache()
    policy = local_policy or load_policy_cache()

    if use_local_only:
        if not listing or not policy:
            raise ValueError("Local texts only — fill texts folder or uncheck the option")
        persist_texts(cfg, listing=listing, policy=policy, log=log)
        return listing, policy

    if not api_key and (listing is None or policy is None):
        raise ValueError(
            "Gemini API key missing — add key or texts in "
            f"~/bravelgo-publish-texts/{package.replace('.', '_')}/"
        )

    try:
        if listing is None:
            log("Gemini: store listing…")
            listing = generate_listing(
                api_key,
                pub.get("listing_prompt", ""),
                app_name,
                email,
                seed=seed,
                log=log,
                model=pub.get("gemini_model", ""),
            )
            log(
                f"Listing OK: short={len(listing.get('short', ''))} "
                f"full={len(listing.get('full', ''))} chars"
            )
            persist_texts(cfg, listing=listing, log=log)

        if policy is None:
            log("Gemini: privacy policy…")
            policy = generate_privacy(
                api_key,
                pub.get("privacy_prompt", ""),
                app_name,
                email,
                seed=seed,
                log=log,
                model=pub.get("gemini_model", ""),
            )
            log(f"Policy OK: {len(policy)} chars")
            persist_texts(cfg, policy=policy, log=log)
    except GeminiPublishError as exc:
        local_listing, local_policy = try_load_local_texts(package, app_name, texts_dir, log)
        listing = listing or local_listing
        policy = policy or local_policy
        if listing and policy:
            log("Gemini failed — using texts from folder")
            persist_texts(cfg, listing=listing, policy=policy, log=log)
            return listing, policy
        if pub.get("use_stub_on_quota", True):
            log("Gemini 429 — saving basic English stub texts (edit later in Play Console)")
            listing = listing or stub_listing(app_name)
            policy = policy or stub_policy(app_name, email)
            persist_texts(cfg, listing=listing, policy=policy, log=log)
            return listing, policy
        if listing:
            persist_texts(cfg, listing=listing, log=log)
        raise ValueError(str(exc)) from exc

    if not listing or not policy:
        raise ValueError(
            "Missing listing or policy — add files to "
            f"~/bravelgo-publish-texts/{package.replace('.', '_')}/"
        )

    persist_texts(cfg, listing=listing, policy=policy, log=log)
    return listing, policy


def _require_cached_texts(
    pub: dict,
    package: str,
    app_name: str,
    log: Callable[[str], None],
) -> tuple[dict, str]:
    listing, policy = _load_cached_texts(pub, package, app_name, log)
    if listing and policy:
        return listing, policy
    raise ValueError(
        "No saved texts for Full publish. "
        "1) Click «Generate texts» and wait for «Done» in Tail log (not 429). "
        "2) Or «Load texts from folder». "
        "Full publish does NOT call Gemini (saves free quota)."
    )


def run_publish(
    profile_dir: str | None,
    cfg: dict,
    log: Callable[[str], None],
    user_home: str | None = None,
    *,
    step: str = "all",
    skip_create: bool = False,
    wait_console: bool = True,
    use_vision: bool = True,
) -> dict:
    """
    step: all | generate | docs | console
    profile_dir: auto-resolved from system if None/empty
    """
    pub = merge_publish_config(cfg)
    email = pub.get("account_email", "").strip()
    package = pub.get("package_name", "").strip()
    app_name = pub.get("app_name", "").strip()
    api_key = pub.get("gemini_api_key", "").strip()
    use_vision = use_vision and bool(pub.get("use_vision", True))
    wait_console = wait_console and bool(pub.get("wait_for_console", True))
    country = (cfg.get("country") or pub.get("country") or "FR").strip()

    if not email or not package or not app_name:
        raise ValueError("Publish: fill account email, package name, and app name")

    home = user_home or str(Path.home())
    prof = (profile_dir or "").strip() or resolve_profile_dir(home, cfg, log)
    if not prof:
        raise ValueError("Firefox profile not found — run Full uniquify or Launch Firefox once")

    result: dict = {"privacy_url": pub.get("last_privacy_url", ""), "listing": pub.get("last_listing", {})}

    if step == "generate":
        log("Generate: browser stays closed (Gemini API only)")
        listing, policy = _generate_texts(pub, cfg, package, app_name, email, api_key, log)
        result["listing"] = listing
        result["policy_text"] = policy
        return result

    listing, policy = _require_cached_texts(pub, package, app_name, log)
    log("Using cached texts — Gemini skipped")
    result["listing"] = listing
    result["policy_text"] = policy

    policy_text = policy or ""

    need_browser = step in ("all", "docs", "console")
    if not need_browser:
        return result

    log("Opening Firefox (Selenium + your profile)…")
    driver, _, page = launch_context(prof, log, country=country)
    ui = PublishUI(page, log, gemini_api_key=api_key, use_vision=use_vision)

    try:
        start_url = DOCS_START_URL if step == "docs" else CONSOLE_URL
        try:
            page.goto(start_url, wait_until="domcontentloaded")
            log(f"Firefox opened — check desktop ({start_url[:50]}…)")
        except Exception as exc:
            log(f"WARN: initial navigation: {exc}")

        if wait_console and step in ("all", "console"):
            wait_for_console_ready(page, log, open_console_hint=False)

        if step in ("all", "docs"):
            url = run_docs_flow(page, policy_text, app_name, ui)
            if url:
                result["privacy_url"] = url
                pub["last_privacy_url"] = url
                cfg["publish"] = pub

        if step in ("all", "console"):
            privacy_url = result.get("privacy_url") or pub.get("last_privacy_url", "")
            if not privacy_url:
                raise ValueError("No privacy URL — run Docs step first")
            if not skip_create and not pub.get("app_already_exists"):
                run_create_application(page, app_name, package, ui)
            run_console_setup(
                page,
                account_email=email,
                package_name=package,
                privacy_url=privacy_url,
                listing=listing,
                graphics_dir=pub.get("graphics_dir", ""),
                ui=ui,
            )
    finally:
        close_browser(driver, None, log)

    return result
