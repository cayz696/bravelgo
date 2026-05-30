"""Human-like Firefox warmup via Selenium + system Firefox (same profile as Launch)."""
from __future__ import annotations

import random
import shutil
import subprocess
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

DEFAULT_WARMUP_URLS = pick_sites("FR", 12)


def _unlock_profile(profile_dir: Path) -> None:
    for name in ("lock", ".parentlock", "parent.lock"):
        try:
            (profile_dir / name).unlink(missing_ok=True)
        except OSError:
            pass


def _system_firefox(log) -> str | None:
    for candidate in ("/usr/bin/firefox", "/usr/bin/firefox-esr"):
        if Path(candidate).is_file():
            log(f"System Firefox: {candidate}")
            return candidate
    found = shutil.which("firefox")
    if found:
        log(f"System Firefox: {found}")
        return found
    log("ERROR: sudo apt install firefox")
    return None


def _geckodriver(log) -> str | None:
    for candidate in ("/usr/bin/geckodriver", "/usr/local/bin/geckodriver"):
        if Path(candidate).is_file():
            log(f"Geckodriver: {candidate}")
            return candidate
    found = shutil.which("geckodriver")
    if found:
        log(f"Geckodriver: {found}")
        return found
    log("ERROR: sudo apt install firefox-geckodriver")
    return None


def _ensure_selenium(log) -> bool:
    try:
        import selenium  # noqa: F401
        return True
    except ImportError:
        log("Installing selenium…")
        subprocess.run(
            ["pip3", "install", "selenium", "--break-system-packages", "-q"],
            check=False,
        )
        try:
            import selenium  # noqa: F401
            return True
        except ImportError:
            log("ERROR: pip3 install selenium --break-system-packages")
            return False


def _build_driver(profile_dir: Path, firefox_bin: str, gecko: str, bridge_port: int, cp: dict, log):
    from selenium import webdriver
    from selenium.webdriver.firefox.options import Options
    from selenium.webdriver.firefox.service import Service

    opts = Options()
    opts.binary_location = firefox_bin
    opts.set_preference("browser.shell.checkDefaultBrowser", False)
    opts.set_preference("browser.startup.page", 0)
    opts.set_preference("network.proxy.type", 1)
    opts.set_preference("network.proxy.http", "127.0.0.1")
    opts.set_preference("network.proxy.http_port", bridge_port)
    opts.set_preference("network.proxy.ssl", "127.0.0.1")
    opts.set_preference("network.proxy.ssl_port", bridge_port)
    opts.set_preference("network.proxy.share_proxy_settings", True)
    opts.set_preference("network.proxy.no_proxies_on", "localhost, 127.0.0.1")
    opts.set_preference("media.peerconnection.enabled", False)
    opts.set_preference("intl.accept_languages", cp["lang_full"])
    opts.set_preference("dom.min_background_timeout_value", 4)
    opts.set_preference("dom.timeout.enable_budget_timer_throttling", False)

    opts.add_argument("-profile")
    opts.add_argument(str(profile_dir))
    opts.add_argument("-no-remote")

    service = Service(executable_path=gecko)
    log("Starting Firefox (Selenium)…")
    driver = webdriver.Firefox(service=service, options=opts)
    driver.set_page_load_timeout(60)
    driver.implicitly_wait(4)
    return driver


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
    driver = None
    steps_done = 0
    try:
        if not _ensure_selenium(log):
            return
        firefox_bin = _system_firefox(log)
        gecko = _geckodriver(log)
        if not firefox_bin or not gecko:
            return

        profile_dir = Path(profile_dir)
        if not profile_dir.is_dir():
            log(f"ERROR: profile missing — {profile_dir}")
            return
        _unlock_profile(profile_dir)

        cc = country.upper()
        cp = country_profile(cc)
        selected = urls if urls else pick_sites(cc, max_sites + 4)
        random.shuffle(selected)
        selected = selected[:max_sites]
        queries = pick_queries(cc, lang_mode)
        deadline = time.time() + session_minutes * 60

        log(f"Warmup · {cp['name']} · lang={lang_mode} · {len(selected)} sites · ~{session_minutes} min")
        log(f"Profile: {profile_dir}")
        log(f"Proxy: 127.0.0.1:{bridge_port}")

        driver = _build_driver(profile_dir, firefox_bin, gecko, bridge_port, cp, log)
        _human_pause(2, 4)
        log(f"Tab: {driver.current_url[:90]}")

        query = random.choice(queries)
        if time.time() < deadline:
            gurl = google_url(cc)
            log(f"Step 1/4 Google: {query[:50]}")
            if _get(driver, gurl, log):
                steps_done += 1
                _dismiss_consent(driver, cc, log)
                if _google_search(driver, query, lang_mode != "en", log):
                    _scroll(driver, random.randint(2, 5))
                    _click_search_result(driver, log)

        if google_images and time.time() < deadline:
            img_q = pick_image_query(cc)
            log(f"Step 2/4 Images: {img_q}")
            if _google_images(driver, cc, img_q, log, deadline):
                steps_done += 1

        if google_maps and time.time() < deadline:
            maps_q = pick_maps_query(cc)
            log(f"Step 3/4 Maps: {maps_q}")
            if _google_maps(driver, cc, maps_q, log, deadline):
                steps_done += 1

        log(f"Step 4/4 Sites ({len(selected)})")
        for url in selected:
            if time.time() >= deadline:
                break
            if "google." in url:
                continue
            log(f"→ {url}")
            if _get(driver, url, log):
                steps_done += 1
                _dismiss_consent(driver, cc, log)
                _scroll(driver, random.randint(3, 7))
                _human_pause(3, 10)

        if steps_done == 0:
            log("ERROR: 0 steps — check proxy bridge · close Firefox dialogs")
        else:
            log(f"Done · {steps_done} steps OK")
    except Exception as exc:
        log(f"FATAL: {exc}")
        for line in traceback.format_exc().splitlines()[-6:]:
            log(line)
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass


def _get(driver, url: str, log) -> bool:
    try:
        driver.get(url)
        log(f"Loaded: {driver.current_url[:90]}")
        return True
    except Exception as exc:
        log(f"Load fail {url}: {exc}")
        return False


def _google_search(driver, query: str, typos: bool, log) -> bool:
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys

    try:
        box = driver.find_element(By.CSS_SELECTOR, "textarea[name='q'], input[name='q']")
        box.click()
        _human_type(box, query, typos)
        box.send_keys(Keys.RETURN)
        _human_pause(3, 7)
        log(f"Search OK → {driver.current_url[:80]}")
        return True
    except Exception as exc:
        log(f"Search box fail: {exc}")
        return False


def _google_images(driver, country: str, query: str, log, deadline: float) -> bool:
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys

    host = google_url(country).replace("https://", "").split("/")[0]
    url = f"https://{host}/search?q={quote_plus(query)}&tbm=isch"
    if not _get(driver, url, log):
        return False
    _dismiss_consent(driver, country, log)
    _scroll(driver, random.randint(2, 4))
    try:
        imgs = driver.find_elements(By.CSS_SELECTOR, "img[src*='gstatic'], img[data-src]")
        if len(imgs) < 2:
            log("WARN: no thumbnails")
            return False
        for i in range(min(3, len(imgs))):
            if time.time() >= deadline:
                break
            idx = random.randint(0, min(len(imgs) - 1, 10))
            try:
                imgs[idx].click()
                log(f"Image {i + 1}")
                _human_pause(3, 6)
                driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
            except Exception:
                pass
        return True
    except Exception as exc:
        log(f"Images fail: {exc}")
        return False


def _google_maps(driver, country: str, query: str, log, deadline: float) -> bool:
    from selenium.webdriver.common.by import By

    url = f"https://www.google.com/maps/search/{quote_plus(query)}"
    if not _get(driver, url, log):
        return False
    _human_pause(4, 8)
    _dismiss_consent(driver, country, log)
    _scroll(driver, 2)
    try:
        links = driver.find_elements(By.CSS_SELECTOR, "a.hfpxzc, a[href*='/maps/place/']")
        if not links:
            log("WARN: no listings")
            return False
        links[0].click()
        log("Maps listing")
        _human_pause(5, 10)
        return True
    except Exception as exc:
        log(f"Maps fail: {exc}")
        return False


def _dismiss_consent(driver, country: str, log) -> None:
    from selenium.webdriver.common.by import By

    for label in consent_labels(country):
        try:
            btns = driver.find_elements(By.XPATH, f"//button[contains(., '{label}')]")
            if btns:
                btns[0].click()
                log(f"Consent: {label}")
                _human_pause(0.8, 1.5)
                return
        except Exception:
            continue


def _click_search_result(driver, log) -> None:
    from selenium.webdriver.common.by import By

    try:
        results = driver.find_elements(By.CSS_SELECTOR, "a h3")
        if not results:
            return
        results[min(random.randint(0, 2), len(results) - 1)].click()
        log("Clicked result")
        _human_pause(5, 12)
        _scroll(driver, random.randint(2, 4))
    except Exception as exc:
        log(f"Result click: {exc}")


def _human_pause(a: float, b: float) -> None:
    time.sleep(random.uniform(a, b))


def _human_type(el, text: str, typos: bool) -> None:
    for ch in text:
        el.send_keys(ch)
        time.sleep(random.uniform(0.06, 0.18))


def _scroll(driver, steps: int) -> None:
    for _ in range(steps):
        delta = random.randint(200, 600)
        driver.execute_script(f"window.scrollBy(0, {delta});")
        time.sleep(random.uniform(0.6, 1.8))
