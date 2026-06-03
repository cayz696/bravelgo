"""Orchestrate publish pipeline: generate → wait → docs → console."""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from bravelgo.publish.browser import close_browser, launch_context
from bravelgo.publish.config import CONSOLE_URL, DOCS_START_URL, merge_publish_config
from bravelgo.publish.console_flow import run_console_setup, run_create_application
from bravelgo.publish.docs_flow import run_docs_flow
from bravelgo.publish.gemini import GeminiPublishError, generate_listing, generate_privacy, unique_seed
from bravelgo.publish.local_texts import try_load_local_texts
from bravelgo.publish.profile_resolve import resolve_profile_dir
from bravelgo.publish.ui_actions import PublishUI
from bravelgo.publish.wait_console import wait_for_console_ready

POLICY_CACHE = Path.home() / ".bravelgo-publish-policy.txt"


def _listing_ready(listing: dict | None) -> bool:
    if not listing:
        return False
    return bool((listing.get("short") or "").strip() or (listing.get("full") or "").strip())


def _load_cached_texts(pub: dict, package: str, app_name: str, log: Callable[[str], None]) -> tuple[dict | None, str | None]:
    listing: dict | None = dict(pub.get("last_listing") or {}) if _listing_ready(pub.get("last_listing")) else None
    policy: str | None = None
    if POLICY_CACHE.is_file():
        policy = POLICY_CACHE.read_text(encoding="utf-8").strip() or None
    texts_dir = pub.get("texts_dir", "")
    local_listing, local_policy = try_load_local_texts(package, app_name, texts_dir, log)
    if local_listing:
        listing = local_listing
    if local_policy:
        policy = local_policy
    return listing, policy


def _generate_texts(pub: dict, cfg: dict, package: str, app_name: str, email: str, api_key: str, log: Callable[[str], None]) -> tuple[dict, str]:
    seed = unique_seed()
    texts_dir = pub.get("texts_dir", "")
    local_listing, local_policy = try_load_local_texts(package, app_name, texts_dir, log)
    use_local_only = pub.get("use_local_texts_only", False)

    listing = local_listing
    policy = local_policy

    if not use_local_only and (listing is None or policy is None):
        if not api_key:
            if listing is None or policy is None:
                raise ValueError(
                    "Gemini API key missing — add key or fill texts folder "
                    "(title/short/full/policy.txt)"
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
        except GeminiPublishError:
            local_listing, local_policy = try_load_local_texts(package, app_name, texts_dir, log)
            if local_listing:
                listing = listing or local_listing
            if local_policy:
                policy = policy or local_policy
            if listing and policy:
                log("Gemini failed — using texts from folder")
            else:
                raise

    if not listing or not policy:
        raise ValueError(
            "Missing listing or policy — run Gemini or add files to "
            f"~/bravelgo-publish-texts/{package.replace('.', '_')}/"
        )

    pub["last_listing"] = listing
    POLICY_CACHE.write_text(policy, encoding="utf-8")
    cfg["publish"] = pub
    log(f"Policy cached → {POLICY_CACHE}")
    return listing, policy


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

    listing, policy = _load_cached_texts(pub, package, app_name, log)
    if step in ("all", "docs", "console"):
        if not listing or not policy:
            log("No cached texts — running Gemini before browser…")
            listing, policy = _generate_texts(pub, cfg, package, app_name, email, api_key, log)
        else:
            log("Using cached listing + policy (skipping Gemini)")
        result["listing"] = listing or {}
        result["policy_text"] = policy or ""

    policy_text = result.get("policy_text") or ""
    if not policy_text and POLICY_CACHE.is_file():
        policy_text = POLICY_CACHE.read_text(encoding="utf-8")

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
            if not policy_text:
                raise ValueError("No policy text — run Generate first")
            url = run_docs_flow(page, policy_text, app_name, ui)
            if url:
                result["privacy_url"] = url
                pub["last_privacy_url"] = url
                cfg["publish"] = pub

        if step in ("all", "console"):
            privacy_url = result.get("privacy_url") or pub.get("last_privacy_url", "")
            if not privacy_url:
                raise ValueError("No privacy URL — run Docs step first")
            listing = result.get("listing") or pub.get("last_listing", {})
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
