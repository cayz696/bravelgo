"""Playwright + system Firefox (deb) + BravelGo Mozilla profile."""
from __future__ import annotations

import os
import subprocess
import time
from typing import Callable

from bravelgo.ff_profile import resolve_firefox_binary
from bravelgo.publish.human import pause


def kill_firefox(log: Callable[[str], None] | None = None) -> None:
    if log:
        log("Closing Firefox for Playwright profile lock…")
    subprocess.run(
        "killall -9 firefox firefox-esr 2>/dev/null",
        shell=True,
        capture_output=True,
    )
    time.sleep(2)


def unlock_profile(profile_dir: str) -> None:
    for name in ("lock", ".parentlock", "parent.lock"):
        try:
            os.remove(os.path.join(profile_dir, name))
        except OSError:
            pass


def launch_context(
    profile_dir: str,
    log: Callable[[str], None],
    *,
    headless: bool = False,
):
    """
    Launch Firefox via Playwright persistent context using:
    - Mozilla profile dir (cookies, 2FA session)
    - System deb Firefox binary (/usr/lib/firefox/firefox), not snap
    """
    from playwright.sync_api import sync_playwright

    kill_firefox(log)
    unlock_profile(profile_dir)

    firefox_bin = resolve_firefox_binary(log)
    if not firefox_bin:
        raise RuntimeError("System Firefox not found — Warmup → Reinstall Firefox")

    log(f"Firefox binary: {firefox_bin}")
    log(f"Firefox profile: {profile_dir}")

    pw = sync_playwright().start()
    launch_kw: dict = {
        "user_data_dir": profile_dir,
        "headless": headless,
        "viewport": {"width": 1400, "height": 900},
        "locale": "en-US",
        "args": ["-no-remote"],
        "firefox_user_prefs": {
            "dom.webdriver.enabled": False,
        },
    }
    if firefox_bin and "/snap/" not in firefox_bin:
        launch_kw["executable_path"] = firefox_bin

    try:
        context = pw.firefox.launch_persistent_context(**launch_kw)
    except TypeError:
        launch_kw.pop("executable_path", None)
        log("WARN: executable_path unsupported — using Playwright Firefox")
        context = pw.firefox.launch_persistent_context(**launch_kw)
    except Exception as exc:
        pw.stop()
        raise RuntimeError(f"Firefox launch failed: {exc}") from exc

    page = context.pages[0] if context.pages else context.new_page()
    page.set_default_timeout(45_000)
    page.set_default_navigation_timeout(60_000)
    pause(1.0, 2.0)
    log("Firefox ready (same profile as Launch Firefox / warmup)")
    return pw, context, page


def close_browser(pw, context, log: Callable[[str], None]) -> None:
    try:
        context.close()
    except Exception:
        pass
    try:
        pw.stop()
    except Exception:
        pass
    log("Browser closed")
