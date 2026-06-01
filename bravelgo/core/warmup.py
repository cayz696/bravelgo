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

STEALTH_JS = """
try {
  Object.defineProperty(navigator, 'webdriver', { get: () => undefined, configurable: true });
} catch (e) {}
"""

OVERLAY_LABELS = [
    "Accept all", "Accept", "Tout accepter", "Accepter tout", "Accepter", "J'accepte",
    "Refuser", "Reject all", "Reject", "Fermer", "Close", "Got it", "OK", "Compris",
    "Continuer", "Continue", "No thanks", "Non merci", "Allow", "Autoriser",
    "Save", "Enregistrer", "Agree", "I agree", "Dismiss", "Skip",
]

OVERLAY_SELECTORS = [
    "button[aria-label*='Close']",
    "button[aria-label*='Fermer']",
    "button[aria-label*='lose']",
    "[data-testid='close']",
    "[class*='close']",
    "[class*='dismiss']",
    "button.modal-close",
]


def _stealth(driver, log) -> None:
    try:
        driver.execute_script(STEALTH_JS)
    except Exception as exc:
        log(f"Stealth skip: {exc}")


def _unlock_profile(profile_dir: Path) -> None:
    for name in ("lock", ".parentlock", "parent.lock"):
        try:
            (profile_dir / name).unlink(missing_ok=True)
        except OSError:
            pass


def _system_firefox(log) -> str | None:
    from bravelgo.ff_profile import resolve_firefox_binary

    return resolve_firefox_binary(log)


def _elf_binary(path: str | None) -> bool:
    if not path:
        return False
    try:
        with open(path, "rb") as fh:
            return fh.read(4) == b"\x7fELF"
    except OSError:
        return False


def _firefox_options(profile_dir: Path, bridge_port: int, cp: dict, binary: str | None):
    from selenium.webdriver.firefox.options import Options

    opts = Options()
    if binary and "/snap/" not in binary and _elf_binary(binary):
        opts.binary_location = binary
    # Proxy/locale/webrtc already in profile user.js — duplicating prefs breaks some Firefox builds
    opts.set_preference("dom.webdriver.enabled", False)
    opts.add_argument("-profile")
    opts.add_argument(str(profile_dir))
    opts.add_argument("-no-remote")
    return opts


def _build_driver(profile_dir: Path, firefox_bin: str, gecko: str, bridge_port: int, cp: dict, log):
    from selenium import webdriver
    from selenium.webdriver.firefox.service import Service

    service = Service(executable_path=gecko)
    attempts: list[str | None] = []
    if firefox_bin and _elf_binary(firefox_bin) and "/snap/" not in (firefox_bin or ""):
        attempts.append(firefox_bin)
    attempts.append(None)
    if firefox_bin and "/snap/" in firefox_bin:
        log("WARN: snap Firefox ignored — need deb: Reinstall Firefox")
    seen: set[str | None] = set()
    last_exc: Exception | None = None

    log("Starting Firefox (Selenium)…")
    for binary in attempts:
        if binary in seen:
            continue
        seen.add(binary)
        label = binary or "(system PATH via geckodriver)"
        log(f"Try Firefox binary: {label}")
        try:
            opts = _firefox_options(profile_dir, bridge_port, cp, binary)
            driver = webdriver.Firefox(service=service, options=opts)
            driver.set_page_load_timeout(60)
            driver.implicitly_wait(4)
            log(f"Firefox OK · {label}")
            return driver
        except Exception as exc:
            last_exc = exc
            log(f"Launch failed ({label}): {exc}")

    if last_exc:
        raise last_exc
    raise RuntimeError("Firefox launch failed")


def _geckodriver(log) -> str | None:
    for candidate in ("/usr/local/bin/geckodriver", "/usr/bin/geckodriver"):
        if Path(candidate).is_file():
            log(f"Geckodriver: {candidate}")
            return candidate
    found = shutil.which("geckodriver")
    if found and "/snap/" not in found:
        log(f"Geckodriver: {found}")
        return found
    if found:
        log("WARN: snap geckodriver skipped — use Reinstall Firefox")
    log("ERROR: geckodriver missing — Warmup → Reinstall Firefox")
    return None


def _ensure_selenium(log) -> bool:
    """Warmup runs as desktop user — import check only (deps installed in preflight)."""
    try:
        import selenium  # noqa: F401
        return True
    except ImportError:
        log("ERROR: selenium missing — click Reinstall Firefox or restart warmup")
        return False


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
    skip_google: bool = True,
) -> None:
    driver = None
    steps_done = 0
    try:
        if not _ensure_selenium(log):
            return
        firefox_bin = _system_firefox(log)
        gecko = _geckodriver(log)
        if not gecko:
            return
        if not firefox_bin:
            log("WARN: Firefox path unknown — trying system PATH")

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
        if skip_google:
            log("Google steps OFF — geo sites only (safer before Google login)")

        driver = _build_driver(profile_dir, firefox_bin, gecko, bridge_port, cp, log)
        _human_pause(2, 4)
        _stealth(driver, log)
        log(f"Tab: {driver.current_url[:90]}")
        log("Note: robot icon = Selenium only · gone after quit · use Launch Firefox for Google login")

        query = random.choice(queries)
        if not skip_google and time.time() < deadline:
            gurl = google_url(cc)
            log(f"Step 1/4 Google: {query[:50]}")
            if _get(driver, gurl, log):
                steps_done += 1
                _handle_page(driver, log, cc)
                if _google_search(driver, query, lang_mode != "en", log):
                    _scroll(driver, random.randint(2, 5))
                    _click_search_result(driver, log)

        if not skip_google and google_images and time.time() < deadline:
            img_q = pick_image_query(cc)
            log(f"Step 2/4 Images: {img_q}")
            if _google_images(driver, cc, img_q, log, deadline):
                steps_done += 1

        if not skip_google and google_maps and time.time() < deadline:
            maps_q = pick_maps_query(cc)
            log(f"Step 3/4 Maps: {maps_q}")
            if _google_maps(driver, cc, maps_q, log, deadline):
                steps_done += 1

        log(f"Step 4/4 Sites ({len(selected)}) — new tab per site")
        main_handle = driver.current_window_handle
        for url in selected:
            if time.time() >= deadline:
                break
            if "google." in url:
                continue
            log(f"→ {url}")
            if _open_in_new_tab(driver, url, log, cc):
                steps_done += 1
                _handle_page(driver, log, cc)
                _scroll(driver, random.randint(3, 7))
                _human_pause(3, 10)
            _manage_popup_windows(driver, log, main_handle)
            _trim_tabs(driver, log, max_tabs=5)

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
    from selenium.common.exceptions import UnexpectedAlertPresentException

    try:
        driver.get(url)
    except UnexpectedAlertPresentException:
        _dismiss_js_alert(driver, log)
        try:
            driver.get(url)
        except Exception as exc:
            log(f"Load fail {url}: {exc}")
            return False
    except Exception as exc:
        log(f"Load fail {url}: {exc}")
        return False
    _stealth(driver, log)
    _handle_page(driver, log, None)
    log(f"Loaded: {driver.current_url[:90]}")
    return True


def _open_in_new_tab(driver, url: str, log, country: str) -> bool:
    try:
        driver.switch_to.new_window("tab")
        return _get(driver, url, log)
    except Exception as exc:
        log(f"New tab fail: {exc}")
        return False


def _handle_page(driver, log, country: str | None) -> None:
    """JS alerts + cookie/modal overlays after each navigation."""
    _dismiss_js_alert(driver, log)
    if country:
        _dismiss_consent(driver, country, log)
    _dismiss_overlays(driver, log)
    _manage_popup_windows(driver, log)


def _dismiss_js_alert(driver, log) -> None:
    try:
        alert = driver.switch_to.alert
        text = (alert.text or "")[:60]
        alert.accept()
        log(f"JS popup closed: {text}")
        _human_pause(0.3, 0.8)
    except Exception:
        pass
    try:
        driver.switch_to.default_content()
    except Exception:
        pass


def _dismiss_overlays(driver, log) -> None:
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys

    for _ in range(2):
        try:
            body = driver.find_element(By.TAG_NAME, "body")
            body.send_keys(Keys.ESCAPE)
            _human_pause(0.3, 0.6)
        except Exception:
            pass

    for label in OVERLAY_LABELS:
        try:
            btns = driver.find_elements(
                By.XPATH,
                f"//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{label.lower()}')]"
                f" | //a[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{label.lower()}')]",
            )
            for btn in btns[:2]:
                if btn.is_displayed():
                    btn.click()
                    log(f"Overlay: {label}")
                    _human_pause(0.5, 1.2)
                    return
        except Exception:
            continue

    for sel in OVERLAY_SELECTORS:
        try:
            els = driver.find_elements(By.CSS_SELECTOR, sel)
            for el in els[:3]:
                if el.is_displayed():
                    el.click()
                    log(f"Overlay close: {sel}")
                    _human_pause(0.4, 1.0)
                    return
        except Exception:
            continue

    # Common GDPR iframe (Sourcepoint, Didomi, etc.)
    try:
        iframes = driver.find_elements(By.CSS_SELECTOR, "iframe[title*='SP Consent'], iframe[id*='sp_message']")
        for frame in iframes[:1]:
            driver.switch_to.frame(frame)
            for label in ("Accept", "Accepter", "Tout accepter", "Accept all"):
                try:
                    btn = driver.find_element(By.XPATH, f"//button[contains(., '{label}')]")
                    btn.click()
                    log(f"Consent iframe: {label}")
                    break
                except Exception:
                    continue
            driver.switch_to.default_content()
    except Exception:
        try:
            driver.switch_to.default_content()
        except Exception:
            pass


def _manage_popup_windows(driver, log, keep_handle: str | None = None) -> None:
    """Close extra tabs opened by window.open / target=_blank spam."""
    handles = driver.window_handles
    if len(handles) <= 1:
        return
    keep = keep_handle if keep_handle in handles else handles[0]
    for h in list(handles):
        if h == keep:
            continue
        try:
            driver.switch_to.window(h)
            pop_url = driver.current_url[:70]
            _dismiss_js_alert(driver, log)
            _dismiss_overlays(driver, log)
            if random.random() < 0.35:
                _scroll(driver, 1)
                _human_pause(2, 5)
                log(f"Popup tab viewed: {pop_url}")
            else:
                log(f"Popup tab closed: {pop_url}")
            driver.close()
        except Exception as exc:
            log(f"Popup close skip: {exc}")
    try:
        driver.switch_to.window(keep)
    except Exception:
        driver.switch_to.window(driver.window_handles[-1])


def _trim_tabs(driver, log, max_tabs: int = 5) -> None:
    while len(driver.window_handles) > max_tabs:
        old = driver.window_handles[0]
        try:
            driver.switch_to.window(old)
            log("Trim old tab")
            driver.close()
        except Exception:
            break
    try:
        driver.switch_to.window(driver.window_handles[-1])
    except Exception:
        pass


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
    _handle_page(driver, log, country)
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
    _handle_page(driver, log, country)
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
