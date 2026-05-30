"""Human-like Firefox warmup via Playwright — geo sites, Google Images/Maps, background-safe."""
from __future__ import annotations

import random
import time
import traceback
from pathlib import Path
from urllib.parse import quote_plus

from bravelgo.countries import country_profile
from bravelgo.proxy_geo import BRIDGE_PORT
from bravelgo.warmup_geo import (
    consent_labels,
    google_url,
    pick_image_query,
    pick_maps_query,
    pick_queries,
    pick_sites,
)

DEFAULT_WARMUP_URLS = pick_sites("FR", 12)  # backward compat for app.py

BACKGROUND_PREFS = {
    "dom.timeout.enable_budget_timer_throttling": False,
    "dom.timeout.background_throttle_timeout": 0,
    "dom.min_background_timeout_value": 4,
    "dom.timeout.background_throttle_max_budget": -1,
    "dom.ipc.processPriorityManager.backgroundGracePeriodMS": 0,
    "page_throttling.enabled": False,
}

VISIBILITY_INIT_SCRIPT = """
(() => {
  try {
    Object.defineProperty(document, 'visibilityState', { get: () => 'visible', configurable: true });
    Object.defineProperty(document, 'hidden', { get: () => false, configurable: true });
    document.hasFocus = () => true;
  } catch (e) {}
})();
"""

FF_DISMISS_SELECTORS = [
    "button:has-text('Quit')",
    "button:has-text('Not Now')",
    "button:has-text('Pas maintenant')",
    "button:has-text('Continue')",
    "button:has-text('Continuer')",
    "button:has-text('Accept')",
    "button:has-text('OK')",
]


def ensure_playwright(log) -> bool:
    import subprocess
    import sys

    try:
        import playwright  # noqa: F401
    except ImportError:
        log("Installing playwright…")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "playwright", "--break-system-packages", "-q"],
            check=False,
        )
    return True


def _system_firefox(log) -> str | None:
    import os
    import shutil

    for candidate in ("/usr/bin/firefox", "/usr/bin/firefox-esr"):
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            log(f"System Firefox: {candidate}")
            return candidate
    found = shutil.which("firefox")
    if found:
        log(f"System Firefox: {found}")
        return found
    log("ERROR: install firefox — sudo apt install firefox")
    return None


def _unlock_profile(profile_dir: Path) -> None:
    for name in ("lock", ".parentlock", "parent.lock"):
        try:
            (profile_dir / name).unlink(missing_ok=True)
        except OSError:
            pass


def _pick_working_page(browser, log, wait_s: int = 40):
    deadline = time.time() + wait_s
    while time.time() < deadline:
        pages = browser.pages
        if pages:
            page = pages[-1]
            try:
                url = page.url or "about:blank"
                log(f"Tab ready: {url[:90]}")
                return page
            except Exception as exc:
                log(f"Tab not controllable yet: {exc}")
        else:
            log("Waiting for Firefox tab… (close profile dialogs if visible)")
        time.sleep(2)
    log("No tab appeared — opening new one")
    return browser.new_page()


def _clear_blocking_ui(page, log) -> None:
    for _ in range(4):
        try:
            page.keyboard.press("Escape")
            time.sleep(0.4)
        except Exception:
            pass
    for sel in FF_DISMISS_SELECTORS:
        try:
            btn = page.locator(sel)
            if btn.count() > 0:
                btn.first.click(timeout=2000)
                log(f"Dismissed dialog: {sel}")
                _human_pause(0.5, 1.2)
        except Exception:
            continue


def run_warmup(
    real_user: str,
    profile_dir: Path,
    country: str,
    urls: list[str] | None,
    log,
    max_sites: int = 6,
    lang_mode: str = "geo",
    bridge_port: int = BRIDGE_PORT,
    session_minutes: int = 15,
    google_images: bool = True,
    google_maps: bool = True,
    background_safe: bool = True,
) -> None:
    browser = None
    steps_done = 0
    try:
        if not ensure_playwright(log):
            return

        firefox_bin = _system_firefox(log)
        if not firefox_bin:
            return

        from playwright.sync_api import sync_playwright

        cc = country.upper()
        cp = country_profile(cc)
        locale = cp["ff_locale"]
        profile_dir = Path(profile_dir)
        if not profile_dir.is_dir():
            log(f"ERROR: profile missing — {profile_dir}")
            return

        _unlock_profile(profile_dir)
        selected = urls if urls else pick_sites(cc, max_sites + 4)
        random.shuffle(selected)
        selected = selected[:max_sites]
        queries = pick_queries(cc, lang_mode)
        deadline = time.time() + session_minutes * 60

        log(f"Warmup · {cp['name']} · lang={lang_mode} · {len(selected)} sites · ~{session_minutes} min")
        log(f"Profile: {profile_dir}")
        log(f"Proxy: 127.0.0.1:{bridge_port}")
        if background_safe:
            log("Background-safe ON (minimize window OK)")

        prefs = {
            "network.proxy.type": 1,
            "network.proxy.http": "127.0.0.1",
            "network.proxy.http_port": bridge_port,
            "network.proxy.ssl": "127.0.0.1",
            "network.proxy.ssl_port": bridge_port,
            "network.proxy.share_proxy_settings": True,
            "network.proxy.no_proxies_on": "localhost, 127.0.0.1",
            "media.peerconnection.enabled": False,
            "dom.webdriver.enabled": False,
            "intl.accept_languages": cp["lang_full"],
            "marionette.enabled": True,
        }
        if background_safe:
            prefs.update(BACKGROUND_PREFS)

        with sync_playwright() as pw:
            log("Launching Firefox…")
            browser = pw.firefox.launch_persistent_context(
                str(profile_dir),
                headless=False,
                locale=locale,
                viewport=_random_viewport(),
                slow_mo=random.randint(50, 140),
                firefox_user_prefs=prefs,
                executable_path=firefox_bin,
                args=["-no-remote"],
                timeout=90000,
            )
            if background_safe:
                browser.add_init_script(VISIBILITY_INIT_SCRIPT)

            page = _pick_working_page(browser, log)
            _human_pause(2, 4)
            _clear_blocking_ui(page, log)

            query = random.choice(queries)
            if time.time() < deadline:
                gurl = google_url(cc)
                log(f"Step 1/4 Google search [{lang_mode}]: {query[:50]}")
                if _visit(page, gurl, log):
                    steps_done += 1
                    _human_pause(2, 5)
                    _dismiss_consent(page, cc)
                    _clear_blocking_ui(page, log)
                    search_box = page.locator("textarea[name='q'], input[name='q']")
                    if search_box.count():
                        search_box.first.click(timeout=8000)
                        _human_type(search_box.first, query, lang_mode != "en")
                        page.keyboard.press("Enter")
                        _human_pause(3, 8)
                        log(f"Search submitted → {page.url[:80]}")
                        _scroll_page(page, random.randint(2, 5))
                        if random.random() < 0.65:
                            _click_search_result(page, log)
                    else:
                        log("WARN: Google search box not found — cookie/dialog blocking?")

            if google_images and time.time() < deadline:
                img_q = pick_image_query(cc)
                log(f"Step 2/4 Google Images: {img_q}")
                if _google_images_browse(page, cc, img_q, log, deadline):
                    steps_done += 1

            if google_maps and time.time() < deadline:
                maps_q = pick_maps_query(cc)
                log(f"Step 3/4 Google Maps: {maps_q}")
                if _google_maps_photos(page, cc, maps_q, log, deadline):
                    steps_done += 1

            log(f"Step 4/4 Geo sites ({len(selected)})")
            for url in selected:
                if time.time() >= deadline:
                    log("Time limit reached")
                    break
                if "google." in url:
                    continue
                log(f"→ {url}")
                try:
                    if random.random() < 0.25:
                        page = browser.new_page()
                    if _visit(page, url, log):
                        steps_done += 1
                except Exception as exc:
                    log(f"Skip {url}: {exc}")
                    continue

                _human_pause(4, 12)
                _dismiss_consent(page, cc)
                _reading_session(page, random.randint(3, 7))
                if random.random() < 0.3:
                    _click_random_link(page, log)
                _human_pause(3, 10)

            if steps_done == 0:
                log("ERROR: no steps completed — check ~/.bravelgo-warmup.log")
                log("Hints: close Firefox dialogs · Proxy Apply · don't mix Launch+Warmup")
            else:
                log(f"Warmup done · {steps_done} steps OK")
            _human_pause(2, 4)
            browser.close()
            browser = None

    except Exception as exc:
        log(f"FATAL warmup error: {exc}")
        for line in traceback.format_exc().splitlines()[-8:]:
            log(line)
    finally:
        if browser:
            try:
                browser.close()
            except Exception:
                pass


def _google_images_browse(page, country: str, query: str, log, deadline: float) -> bool:
    gbase = google_url(country)
    host = gbase.replace("https://", "").split("/")[0]
    url = f"https://{host}/search?q={quote_plus(query)}&tbm=isch"
    if not _visit(page, url, log):
        return False

    _human_pause(2, 5)
    _dismiss_consent(page, country)
    _scroll_page(page, random.randint(2, 4))

    thumbs = page.locator("img[src*='gstatic'], img[data-src], div.islrc img, img.YQ4gaf")
    count = thumbs.count()
    if count < 2:
        log("WARN: no image thumbnails")
        return False

    views = random.randint(2, min(5, count))
    seen = set()
    opened = 0
    for _ in range(views):
        if time.time() >= deadline:
            break
        idx = random.randint(0, min(count - 1, 12))
        if idx in seen:
            continue
        seen.add(idx)
        try:
            thumbs.nth(idx).scroll_into_view_if_needed(timeout=5000)
            _human_pause(0.5, 1.2)
            thumbs.nth(idx).click(timeout=8000)
            opened += 1
            log(f"Image {opened}/{views}")
            _human_pause(3, 8)
            if random.random() < 0.4:
                page.keyboard.press("ArrowRight")
                _human_pause(2, 5)
            if random.random() < 0.5:
                page.keyboard.press("Escape")
        except Exception as exc:
            log(f"Image click skip: {exc}")
    return opened > 0


def _google_maps_photos(page, country: str, query: str, log, deadline: float) -> bool:
    url = f"https://www.google.com/maps/search/{quote_plus(query)}"
    if not _visit(page, url, log):
        return False

    _human_pause(4, 8)
    _dismiss_consent(page, country)
    _scroll_page(page, random.randint(2, 4))

    listings = page.locator("a.hfpxzc, a[href*='/maps/place/']")
    if listings.count() < 1:
        log("WARN: no Maps listings")
        return False

    try:
        listings.nth(0).click(timeout=12000)
        log("Maps listing opened")
        _human_pause(4, 10)
    except Exception as exc:
        log(f"Maps listing skip: {exc}")
        return False

    for label in ["Photos", "Photo", "Bilder", "Fotos"]:
        try:
            btn = page.locator(f"button:has-text('{label}'), div[role='tab']:has-text('{label}')")
            if btn.count() > 0:
                btn.first.click(timeout=5000)
                log("Maps photos tab")
                break
        except Exception:
            continue

    photos = page.locator("button[aria-label*='Photo'], img[src*='googleusercontent']")
    if photos.count() < 1:
        return True

    for i in range(min(3, photos.count())):
        if time.time() >= deadline:
            break
        try:
            photos.nth(i).click(timeout=6000)
            log(f"Maps photo {i + 1}")
            _human_pause(3, 6)
        except Exception:
            pass
    return True


def _random_viewport() -> dict:
    w = random.choice([1280, 1366, 1440, 1536])
    h = random.choice([720, 768, 864, 900])
    return {"width": w, "height": h}


def _visit(page, url: str, log) -> bool:
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        log(f"Loaded: {page.url[:90]}")
        return True
    except Exception as exc:
        log(f"Load failed {url}: {exc}")
        _clear_blocking_ui(page, log)
        return False


def _human_pause(min_s: float, max_s: float) -> None:
    time.sleep(random.uniform(min_s, max_s))


def _human_type(locator, text: str, allow_typos: bool) -> None:
    for ch in text:
        if allow_typos and random.random() < 0.04 and ch.isalpha():
            wrong = chr(ord(ch) + random.choice([-1, 1]))
            locator.type(wrong, delay=random.randint(40, 120))
            time.sleep(random.uniform(0.15, 0.45))
            locator.page.keyboard.press("Backspace")
            time.sleep(random.uniform(0.1, 0.3))
        locator.type(ch, delay=random.randint(55, 200))
        if random.random() < 0.06:
            time.sleep(random.uniform(0.25, 0.7))


def _mouse_jiggle(page) -> None:
    try:
        vp = page.viewport_size or {"width": 1280, "height": 720}
        for _ in range(random.randint(2, 5)):
            x = random.randint(80, max(100, vp["width"] - 80))
            y = random.randint(60, max(80, vp["height"] - 60))
            page.mouse.move(x, y, steps=random.randint(8, 20))
            time.sleep(random.uniform(0.05, 0.2))
    except Exception:
        pass


def _scroll_page(page, steps: int) -> None:
    _mouse_jiggle(page)
    for _ in range(steps):
        delta = random.randint(180, 650)
        page.mouse.wheel(0, delta)
        time.sleep(random.uniform(0.5, 2.0))
        if random.random() < 0.18:
            page.mouse.wheel(0, -random.randint(60, 220))
            time.sleep(random.uniform(0.4, 1.0))


def _reading_session(page, steps: int) -> None:
    for _ in range(steps):
        _scroll_page(page, 1)
        time.sleep(random.uniform(1.5, 4.5))


def _dismiss_consent(page, country: str) -> None:
    for label in consent_labels(country):
        try:
            btn = page.locator(f"button:has-text('{label}')")
            if btn.count() > 0:
                btn.first.click(timeout=2500)
                _human_pause(0.8, 1.5)
                return
        except Exception:
            continue


def _click_search_result(page, log) -> None:
    results = page.locator("a h3, div.g a")
    count = results.count()
    if count < 1:
        log("WARN: no search results to click")
        return
    idx = random.randint(0, min(3, count - 1))
    try:
        results.nth(idx).click(timeout=10000)
        log("Clicked search result")
        _human_pause(6, 18)
        _reading_session(page, random.randint(2, 5))
    except Exception as exc:
        log(f"Result click skip: {exc}")


def _click_random_link(page, log) -> None:
    links = page.locator("a[href^='http']:visible")
    count = links.count()
    if count < 4:
        return
    idx = random.randint(2, min(count - 1, 10))
    try:
        links.nth(idx).click(timeout=8000)
        log("Internal link click")
        _human_pause(4, 12)
        _reading_session(page, random.randint(1, 3))
        page.go_back(timeout=12000)
    except Exception as exc:
        log(f"Link click skip: {exc}")
