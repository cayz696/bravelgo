"""Selenium + system Firefox (deb) + BravelGo Mozilla profile — same stack as Warmup."""
from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Callable, Tuple

from bravelgo.publish.selenium_page import SeleniumPage


def kill_firefox(log: Callable[[str], None] | None = None) -> None:
    if log:
        log("Closing other Firefox instances…")
    subprocess.run(
        "killall -9 firefox firefox-esr 2>/dev/null",
        shell=True,
        capture_output=True,
    )
    time.sleep(1.5)


def launch_context(
    profile_dir: str,
    log: Callable[[str], None],
    *,
    headless: bool = False,
    country: str = "FR",
) -> Tuple[object, object, SeleniumPage]:
    """
    Returns (driver, driver, page) for compatibility with older runner code.
    Opens a visible Firefox window on DISPLAY=:0.
    """
    if headless:
        log("WARN: headless not used for publish — need visible desktop")

    from bravelgo.core.warmup import _build_driver, _geckodriver, _system_firefox, _unlock_profile
    from bravelgo.countries import country_profile
    from bravelgo.proxy_geo import BRIDGE_PORT

    kill_firefox(log)
    prof = Path(profile_dir)
    _unlock_profile(prof)

    gecko = _geckodriver(log)
    if not gecko:
        raise RuntimeError("geckodriver missing — Warmup → Reinstall Firefox")

    firefox_bin = _system_firefox(log) or ""
    cp = country_profile((country or "FR").upper()[:2])
    log(f"Firefox profile: {profile_dir}")
    log("Starting Firefox (Selenium) — window should appear on desktop…")

    driver = _build_driver(prof, firefox_bin, gecko, BRIDGE_PORT, cp, log)
    try:
        driver.set_window_size(1400, 900)
    except Exception:
        pass

    page = SeleniumPage(driver)
    time.sleep(1.0)
    log("Firefox ready (same profile as Launch Firefox / warmup)")
    return driver, driver, page


def close_browser(driver, _context, log: Callable[[str], None]) -> None:
    try:
        if driver is not None:
            driver.quit()
    except Exception:
        pass
    log("Browser closed")
