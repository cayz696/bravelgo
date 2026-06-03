"""Google Play Console UI automation (no Play API) + Vision fallback."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Callable

from bravelgo.publish.config import CONSOLE_URL
from bravelgo.publish.human import pause, pause_long
from bravelgo.publish import i18n
from bravelgo.publish.page_guard import is_create_app_page, page_url
from bravelgo.publish.ui_actions import PublishUI


def run_create_application(
    page,
    app_name: str,
    package_name: str,
    ui: PublishUI,
) -> bool:
    log = ui.log
    log("Console: Create application")
    try:
        ui.click_button(i18n.CREATE_APP, "Create application link")
    except Exception:
        page.goto(CONSOLE_URL, wait_until="domcontentloaded")
        pause_long()
        ui.click_button(i18n.CREATE_APP, "Create application")
    pause_long()
    _wait_stable(page)

    _fill_create_app_input(
        page,
        'input[aria-label*="Application name"], input[maxlength="30"]',
        0,
        app_name[:30],
        "app name",
        log,
    )
    pause(0.8, 1.4)
    _fill_create_app_input(
        page,
        'input[aria-label*="Package"], input[maxlength="150"]',
        1,
        package_name,
        "package name",
        log,
    )
    pause(1.0, 1.8)
    ui.click_button(i18n.CHECK_AVAIL, "Check package availability")
    pause(1.5, 3.0)
    try:
        page.wait_for_selector("text=/package name is available/i", timeout=15_000)
        log("Package available")
    except Exception as exc:
        log(f"WARN: package check: {exc}")

    _select_default_language_en_us(page, ui)
    ui.click_radio_text(i18n.GAME, "Application or game: Game")
    ui.click_radio_text(i18n.FREE, "Free or paid: For free")
    _check_all_declaration_boxes(page, log)

    ui.click_button(i18n.CREATE_APPLICATION_BTN, "Create application button")
    pause_long()
    log("Create application submitted")
    return True


def _fill_create_app_input(page, selector: str, fallback_index: int, text: str, label: str, log) -> None:
    """
    Play Console Material inputs often lack stable aria-labels.
    Prefer the semantic selector, then fall back to visible text inputs by order.
    """
    try:
        page.locator(selector).first.fill(text, timeout=8000)
        log(f"Create app: filled {label}")
        return
    except Exception as exc:
        log(f"Create app: selector fill failed for {label}: {exc}")

    driver = getattr(page, "_driver", None)
    if driver is None:
        raise TimeoutError(f"Create app field not found: {label}")

    from selenium.webdriver.common.by import By

    candidates = driver.find_elements(
        By.CSS_SELECTOR,
        "input:not([type='hidden']):not([type='radio']):not([type='checkbox']), textarea",
    )
    visible = []
    for el in candidates:
        try:
            if el.is_displayed() and el.is_enabled():
                visible.append(el)
        except Exception:
            continue

    want_max = "30" if label == "app name" else "150" if label == "package name" else None
    if want_max:
        for el in visible:
            try:
                if (el.get_attribute("maxlength") or "") == want_max:
                    el.click()
                    pause(0.3, 0.7)
                    try:
                        el.clear()
                    except Exception:
                        pass
                    el.send_keys(text)
                    log(f"Create app: filled {label} (maxlength={want_max})")
                    return
            except Exception:
                continue

    if fallback_index >= len(visible):
        raise TimeoutError(
            f"Create app field not found: {label}; visible inputs={len(visible)}"
        )

    el = visible[fallback_index]
    el.click()
    pause(0.3, 0.7)
    try:
        el.clear()
    except Exception:
        pass
    el.send_keys(text)
    log(f"Create app: filled {label} (visible input #{fallback_index + 1})")


def run_console_setup(
    page,
    *,
    account_email: str,
    package_name: str,
    privacy_url: str,
    listing: dict[str, str],
    graphics_dir: str,
    ui: PublishUI,
) -> bool:
    log = ui.log

    if is_create_app_page(page):
        log(f"Stopped: still on Create app form ({page_url(page)[:80]})")
        raise RuntimeError(
            "Playbook order: finish «Create application» first (submit the form), "
            "then open the app dashboard and click Continue again. "
            "Privacy URL is filled only under «Set privacy policy» task — not on Create app."
        )

    def _step(name: str, fn) -> None:
        try:
            fn()
        except Exception as exc:
            log(f"Task skipped ({name}): {str(exc)[:120]}")
        try:
            _return_dashboard(page, ui)
        except Exception:
            pass

    _step("open app dashboard", lambda: _open_app_dashboard(page, package_name, ui))
    _step("expand setup tasks", lambda: _expand_setup_tasks(page, ui))
    _step("privacy policy", lambda: _task_privacy_policy(page, privacy_url, ui))

    def _app_access():
        _open_task(page, i18n.APP_ACCESS, ui)
        ui.click_radio_text(i18n.YES_ALL_FUNCTIONALITY, "All functionality available without restrictions")
        ui.save()

    def _ads():
        _open_task(page, i18n.ADS, ui)
        ui.click_radio_text(i18n.NO_ADS, "No ads")
        ui.save()

    _step("app access", _app_access)
    _step("ads", _ads)
    _step("content ratings", lambda: _content_ratings(page, account_email, ui))
    _step("target audience", lambda: _target_audience(page, ui))
    _step("data safety / compliance", lambda: _data_safety_and_compliance(page, ui))
    _step("store settings", lambda: _store_settings(page, account_email, ui))

    try:
        _default_store_listing(page, listing, graphics_dir, ui)
    except Exception as exc:
        log(f"Task skipped (store listing): {str(exc)[:120]}")

    log("Console setup pass complete — REVIEW each section manually before production")
    return True


def _wait_stable(page) -> None:
    try:
        page.wait_for_load_state("networkidle", timeout=25_000)
    except Exception:
        pass
    pause(1.0, 2.0)


def _open_app_dashboard(page, package_name: str, ui: PublishUI) -> None:
    if is_create_app_page(page):
        ui.log("Skip dashboard search — still on Create app page")
        return
    try:
        search = page.locator('input[placeholder*="Search"], input[aria-label*="Search"]').first
        search.fill(package_name)
        pause(1.5, 2.5)
        page.get_by_text(package_name, exact=False).first.click(timeout=15_000)
        pause_long()
    except Exception as exc:
        ui.log(f"WARN: open app by search ({exc}) — use Console search if needed")
    _return_dashboard(page, ui)


def _return_dashboard(page, ui: PublishUI) -> None:
    ui.click_button(i18n.DASHBOARD, "Dashboard breadcrumb/link")


def _expand_setup_tasks(page, ui: PublishUI) -> None:
    try:
        page.get_by_text(re.compile("Set up your app", re.I)).first.scroll_into_view_if_needed()
        ui.click_button(i18n.VIEW_TASKS, "View tasks under Set up your app")
    except Exception as exc:
        ui.log(f"View tasks: {exc}")


def _open_task(page, pattern: re.Pattern[str], ui: PublishUI) -> None:
    try:
        page.get_by_role("link", name=pattern).first.click(timeout=20_000)
    except Exception:
        ui.click_button(pattern, f"Open task link {pattern.pattern[:40]}")
    pause_long()
    _wait_stable(page)


def _task_privacy_policy(page, url: str, ui: PublishUI) -> None:
    if is_create_app_page(page):
        raise RuntimeError("Privacy policy task cannot run on Create app form")
    _open_task(page, i18n.PRIVACY_POLICY_TASK, ui)
    _fill_privacy_url_field(page, url, ui.log)
    pause(0.5, 1.0)
    ui.save()


def _fill_privacy_url_field(page, url: str, log: Callable[[str], None]) -> None:
    """Only privacy/URL fields — never input.first (that hits Application name on wrong page)."""
    driver = getattr(page, "_driver", None)
    if driver is not None:
        try:
            ok = driver.execute_script(
                """
                const url = arguments[0];
                for (const inp of document.querySelectorAll('input[type="url"], input')) {
                  if (inp.disabled || inp.type === 'checkbox' || inp.type === 'radio') continue;
                  const r = inp.getBoundingClientRect();
                  if (r.width < 2 || r.height < 2) continue;
                  const label = (
                    (inp.labels && inp.labels[0] && inp.labels[0].innerText) ||
                    inp.getAttribute('aria-label') || ''
                  ).toLowerCase();
                  if (inp.type === 'url' || /privacy|politique|политик|confidential|confiden/.test(label)) {
                    inp.focus();
                    inp.value = url;
                    inp.dispatchEvent(new Event('input', {bubbles: true}));
                    inp.dispatchEvent(new Event('change', {bubbles: true}));
                    return true;
                  }
                }
                return false;
                """,
                url,
            )
            if ok:
                log("Privacy URL filled (privacy field)")
                return
        except Exception as exc:
            log(f"Privacy URL JS fill: {exc}")
    try:
        page.locator('input[type="url"]').first.fill(url, timeout=15_000)
        log("Privacy URL filled (type=url)")
        return
    except Exception as exc:
        log(f"Privacy URL input[type=url]: {exc}")
    raise RuntimeError(
        "Privacy URL field not found — open task «Set privacy policy» on app dashboard first"
    )


def _content_ratings(page, email: str, ui: PublishUI) -> None:
    _open_task(page, i18n.CONTENT_RATINGS, ui)
    ui.click_button(i18n.START_QUESTIONNAIRE, "Start questionnaire")
    pause_long()
    try:
        page.locator('input[type="email"]').first.fill(email)
    except Exception:
        pass
    ui.click_radio_text(i18n.GAME, "Category game")
    try:
        page.locator('input[type="checkbox"]').first.check()
    except Exception:
        pass
    ui.click_button(i18n.NEXT, "Next")
    for _ in range(12):
        ui.click_radio_text(i18n.NO, "Questionnaire answer No")
    ui.save()
    ui.click_button(i18n.NEXT, "Next")
    ui.save()


def _target_audience(page, ui: PublishUI) -> None:
    _open_task(page, i18n.TARGET_AUDIENCE, ui)
    for pat in (i18n.AGE_16_17, i18n.AGE_18_OVER):
        try:
            row = page.get_by_text(pat).first
            row.scroll_into_view_if_needed()
            box = row.locator("xpath=ancestor::*[.//input[@type='checkbox']]//input[@type='checkbox']").first
            if not box.is_checked():
                box.check()
            pause(0.4, 0.9)
        except Exception as exc:
            ui.log(f"Target age: {exc}")
            ui.click_radio_text(pat, f"Target age {pat.pattern}")
    ui.click_button(i18n.NEXT, "Next")
    ui.save()


def _data_safety_and_compliance(page, ui: PublishUI) -> None:
    _open_task(page, i18n.DATA_SAFETY, ui)
    ui.click_button(i18n.NEXT, "Next")
    ui.click_radio_text(i18n.NO_DATA_COLLECT, "Does not collect user data")
    ui.click_button(i18n.NEXT, "Next")
    ui.save(overflow=True)
    _return_dashboard(page, ui)

    _open_task(page, i18n.GOVERNMENT, ui)
    ui.click_radio_text(i18n.NO, "Government app No")
    ui.save(overflow=True)
    _return_dashboard(page, ui)

    _open_task(page, i18n.FINANCIAL, ui)
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    pause(1.0, 2.0)
    ui.click_radio_text(i18n.NO_FINANCIAL, "No financial features")
    ui.click_button(i18n.NEXT, "Next")
    ui.save(overflow=True)
    _return_dashboard(page, ui)

    _open_task(page, i18n.HEALTH, ui)
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    pause(1.0, 2.0)
    ui.click_radio_text(i18n.NO_HEALTH, "No health features")
    ui.click_button(i18n.NEXT, "Next")
    ui.save(overflow=True)
    _return_dashboard(page, ui)


def _store_settings(page, email: str, ui: PublishUI) -> None:
    _open_task(page, i18n.STORE_SETTINGS, ui)
    try:
        section = page.locator("text=/App category/i").locator("xpath=..")
        section.get_by_role("button", name=i18n.EDIT).first.click()
        pause_long()
        page.get_by_role("option", name=i18n.ARCADE).click(timeout=10_000)
        ui.save()
        page.keyboard.press("Escape")
    except Exception as exc:
        ui.log(f"Category: {exc}")
        ui.click_button(i18n.ARCADE, "Category Arcade")

    try:
        section = page.locator("text=/contact details/i").locator("xpath=..")
        section.get_by_role("button", name=i18n.EDIT).first.click()
        pause_long()
        page.locator('input[type="email"]').first.fill(email)
        ui.save()
        page.keyboard.press("Escape")
    except Exception as exc:
        ui.log(f"Contact email: {exc}")


def _default_store_listing(page, listing: dict[str, str], graphics_dir: str, ui: PublishUI) -> None:
    _open_task(page, i18n.STORE_LISTING, ui)
    title = listing.get("title", "")
    short = listing.get("short", "")
    full = listing.get("full", "")

    try:
        t = page.locator('input[maxlength="30"]').first
        t.fill("")
        t.fill(title[:30])
    except Exception:
        pass
    try:
        page.locator('input[maxlength="80"]').first.fill(short[:80])
    except Exception:
        pass
    try:
        page.locator('textarea[maxlength="4000"], textarea').first.fill(full[:4000])
    except Exception:
        pass
    pause_long()

    if graphics_dir:
        _upload_graphics(page, Path(graphics_dir), ui.log)


def _upload_graphics(page, base: Path, log: Callable[[str], None]) -> None:
    for label, path in (
        ("icon", base / "icon-512.png"),
        ("feature", base / "feature-1024x500.png"),
    ):
        if path.is_file():
            try:
                page.locator('input[type="file"]').first.set_input_files(str(path))
                log(f"Uploaded {label}: {path.name}")
                pause_long()
            except Exception as exc:
                log(f"Upload {label}: {exc}")
    phone_dir = base / "phone"
    if phone_dir.is_dir():
        for shot in sorted(phone_dir.glob("*.png")) + sorted(phone_dir.glob("*.jpg")):
            try:
                page.locator('input[type="file"]').last.set_input_files(str(shot))
                log(f"Screenshot: {shot.name}")
                pause(1.5, 3.0)
            except Exception as exc:
                log(f"Screenshot {shot.name}: {exc}")


def _select_default_language_en_us(page, ui: PublishUI) -> None:
    try:
        page.get_by_text(i18n.DEFAULT_LANGUAGE_EN_US).first.click()
        pause(0.5, 1.0)
    except Exception:
        ui.log("Pick English (United States) manually if dropdown differs")


def _check_all_declaration_boxes(page, log: Callable[[str], None]) -> None:
    try:
        driver = getattr(page, "_driver", None)
        if driver is not None:
            checked = driver.execute_script(
                """
                let count = 0;
                for (const cb of document.querySelectorAll('input[type="checkbox"]')) {
                  if (cb.disabled || cb.checked) continue;
                  cb.scrollIntoView({block:'center', inline:'nearest'});
                  cb.click();
                  count++;
                }
                return count;
                """
            )
            log(f"Declaration checkboxes checked: {checked}")
            pause(0.5, 1.0)
            return
        boxes = page.locator('input[type="checkbox"]')
        for i in range(boxes.count()):
            cb = boxes.nth(i)
            if not cb.is_checked():
                cb.check()
                pause(0.2, 0.5)
    except Exception as exc:
        log(f"Declaration checkboxes: {exc}")
