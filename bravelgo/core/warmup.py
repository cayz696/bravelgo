"""Human-like Firefox warmup via Playwright — geo sites, Google Images/Maps, background-safe."""
from __future__ import annotations

import random
import time
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

# Keep timers/scripts running when Firefox or UTM window is minimized.
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
  const vis = () => 'visible';
  const hid = () => false;
  try {
    Object.defineProperty(document, 'visibilityState', { get: vis, configurable: true });
    Object.defineProperty(document, 'hidden', { get: hid, configurable: true });
    document.hasFocus = () => true;
  } catch (e) {}
})();
"""


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
    log("⚠ apt firefox not found — install: sudo apt install firefox")
    return None


def _unlock_profile(profile_dir: Path) -> None:
    for name in ("lock", ".parentlock", "parent.lock"):
        try:
            (profile_dir / name).unlink(missing_ok=True)
        except OSError:
            pass


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
    _unlock_profile(profile_dir)
    selected = urls if urls else pick_sites(cc, max_sites + 4)
    random.shuffle(selected)
    selected = selected[:max_sites]
    queries = pick_queries(cc, lang_mode)
    deadline = time.time() + session_minutes * 60

    log(f"Warmup · {cp['name']} · lang={lang_mode} · {len(selected)} sites · ~{session_minutes} min")
    log(f"Profile: {profile_dir.name} · proxy 127.0.0.1:{bridge_port}")
    if background_safe:
        log("Background-safe ON — works when Firefox/UTM window minimized")

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
    }
    if background_safe:
        prefs.update(BACKGROUND_PREFS)

    with sync_playwright() as pw:
        launch_kw = dict(
            headless=False,
            locale=locale,
            viewport=_random_viewport(),
            slow_mo=random.randint(50, 140),
            firefox_user_prefs=prefs,
            executable_path=firefox_bin,
        )
        browser = pw.firefox.launch_persistent_context(str(profile_dir), **launch_kw)
        if background_safe:
            browser.add_init_script(VISIBILITY_INIT_SCRIPT)

        page = browser.pages[0] if browser.pages else browser.new_page()

        # ── Google text search ────────────────────────────────────────────────
        query = random.choice(queries)
        if time.time() < deadline:
            gurl = google_url(cc)
            log(f"Google [{lang_mode}]: {query[:50]}")
            _visit(page, gurl, log)
            _human_pause(2, 5)
            _dismiss_consent(page, cc)
            _human_pause(1, 3)
            _mouse_jiggle(page)
            search_box = page.locator("textarea[name='q'], input[name='q']")
            if search_box.count():
                search_box.first.click()
                _human_type(search_box.first, query, lang_mode != "en")
                page.keyboard.press("Enter")
                _human_pause(3, 8)
                _scroll_page(page, random.randint(2, 5))
                if random.random() < 0.65:
                    _click_search_result(page, log)

        # ── Google Images (browse thumbnails like reference bot) ──────────────
        if google_images and time.time() < deadline:
            img_q = pick_image_query(cc)
            log(f"Google Images: {img_q}")
            _google_images_browse(page, cc, img_q, log, deadline)

        # ── Google Maps (listings + photos) ───────────────────────────────────
        if google_maps and time.time() < deadline:
            maps_q = pick_maps_query(cc)
            log(f"Google Maps: {maps_q}")
            _google_maps_photos(page, cc, maps_q, log, deadline)

        # ── Geo + dev sites ───────────────────────────────────────────────────
        for url in selected:
            if time.time() >= deadline:
                log("Session time limit reached")
                break
            if "google." in url:
                continue
            log(f"Visit: {url}")
            try:
                if random.random() < 0.25:
                    page = browser.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
            except Exception as exc:
                log(f"Skip {url}: {exc}")
                continue

            _human_pause(4, 12)
            _dismiss_consent(page, cc)
            _reading_session(page, random.randint(3, 7))

            if random.random() < 0.3:
                _click_random_link(page, log)

            _human_pause(3, 10)

        log("Warmup done")
        _human_pause(2, 4)
        browser.close()


def _google_images_browse(page, country: str, query: str, log, deadline: float) -> None:
    gbase = google_url(country)
    host = gbase.replace("https://", "").split("/")[0]
    url = f"https://{host}/search?q={quote_plus(query)}&tbm=isch"
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
    except Exception as exc:
        log(f"Images skip: {exc}")
        return

    _human_pause(2, 5)
    _dismiss_consent(page, country)
    _scroll_page(page, random.randint(2, 4))

    thumbs = page.locator("img[src*='gstatic'], img[data-src], div.islrc img, img.YQ4gaf")
    count = thumbs.count()
    if count < 2:
        log("No image thumbnails found")
        return

    views = random.randint(2, min(5, count))
    seen = set()
    for _ in range(views):
        if time.time() >= deadline:
            break
        idx = random.randint(0, min(count - 1, 12))
        if idx in seen:
            continue
        seen.add(idx)
        try:
            _mouse_jiggle(page)
            thumbs.nth(idx).scroll_into_view_if_needed(timeout=5000)
            _human_pause(0.5, 1.2)
            thumbs.nth(idx).click(timeout=8000)
            log(f"Viewing image {len(seen)}/{views}")
            _human_pause(3, 8)
            _mouse_jiggle(page)
            if random.random() < 0.4:
                page.keyboard.press("ArrowRight")
                _human_pause(2, 5)
            if random.random() < 0.5:
                page.keyboard.press("Escape")
                _human_pause(1, 2)
        except Exception:
            continue


def _google_maps_photos(page, country: str, query: str, log, deadline: float) -> None:
    url = f"https://www.google.com/maps/search/{quote_plus(query)}"
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
    except Exception as exc:
        log(f"Maps skip: {exc}")
        return

    _human_pause(4, 8)
    _dismiss_consent(page, country)
    _scroll_page(page, random.randint(2, 4))

    listings = page.locator("a.hfpxzc, a[href*='/maps/place/']")
    if listings.count() < 1:
        log("No map listings found")
        return

    try:
        idx = random.randint(0, min(2, listings.count() - 1))
        _mouse_jiggle(page)
        listings.nth(idx).click(timeout=12000)
        log("Opened Maps listing")
        _human_pause(4, 10)
        _scroll_page(page, random.randint(1, 3))
    except Exception:
        return

    if time.time() >= deadline:
        return

    photo_labels = ["Photos", "Photo", "Bilder", "Fotos", "Foto", "Zdjęcia", "Immagini"]
    for label in photo_labels:
        try:
            btn = page.locator(f"button:has-text('{label}'), div[role='tab']:has-text('{label}')")
            if btn.count() > 0:
                btn.first.click(timeout=5000)
                log("Maps photos tab")
                _human_pause(2, 5)
                break
        except Exception:
            continue

    photos = page.locator("button[aria-label*='Photo'], img[src*='googleusercontent'], button[data-photo-index]")
    pc = photos.count()
    if pc < 1:
        return

    for _ in range(random.randint(2, min(4, pc))):
        if time.time() >= deadline:
            break
        pi = random.randint(0, min(pc - 1, 8))
        try:
            photos.nth(pi).scroll_into_view_if_needed(timeout=4000)
            _human_pause(0.8, 2)
            photos.nth(pi).click(timeout=6000)
            log("Viewing Maps photo")
            _human_pause(3, 7)
            if random.random() < 0.5:
                page.keyboard.press("Escape")
        except Exception:
            continue


def _random_viewport() -> dict:
    w = random.choice([1280, 1366, 1440, 1536])
    h = random.choice([720, 768, 864, 900])
    return {"width": w, "height": h}


def _visit(page, url: str, log) -> None:
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
    except Exception as exc:
        log(f"Open failed {url}: {exc}")


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
        return
    idx = random.randint(0, min(3, count - 1))
    try:
        _mouse_jiggle(page)
        results.nth(idx).click(timeout=10000)
        log("Clicked search result")
        _human_pause(6, 18)
        _reading_session(page, random.randint(2, 5))
    except Exception:
        pass


def _click_random_link(page, log) -> None:
    links = page.locator("a[href^='http']:visible")
    count = links.count()
    if count < 4:
        return
    idx = random.randint(2, min(count - 1, 10))
    try:
        _mouse_jiggle(page)
        links.nth(idx).click(timeout=8000)
        log("Internal link click")
        _human_pause(4, 12)
        _reading_session(page, random.randint(1, 3))
        page.go_back(timeout=12000)
        _human_pause(2, 5)
    except Exception:
        pass
