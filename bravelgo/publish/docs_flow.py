"""Google Docs — create policy document and copy public link."""
from __future__ import annotations

import re
from typing import Callable

from bravelgo.publish.config import DOCS_START_URL
from bravelgo.publish.human import pause, pause_long
from bravelgo.publish import i18n
from bravelgo.publish.ui_actions import PublishUI
from bravelgo.publish.vision import vision_act


def run_docs_flow(
    page,
    policy_text: str,
    app_name: str,
    ui: PublishUI,
) -> str | None:
    log = ui.log
    doc_title = f"Privacy Policy for {app_name}"
    log(f"Docs → {DOCS_START_URL}")
    page.goto(DOCS_START_URL, wait_until="domcontentloaded")
    pause_long()
    _wait_docs_home(page, log)

    log("Docs: Blank document")
    if not ui.click_button(i18n.BLANK_DOC, "Blank document"):
        try:
            page.get_by_text(i18n.BLANK_DOC).first.click(timeout=15_000)
        except Exception:
            if ui.use_vision and ui.gemini_api_key:
                vision_act(page, ui.gemini_api_key, "Click Blank document to create new doc", log)
    pause_long()

    log("Docs: paste policy")
    editor = page.locator(".kix-appview-editor").first
    if editor.count() == 0:
        editor = page.locator("[contenteditable='true']").first
    editor.click()
    pause(0.5, 1.0)
    page.keyboard.press("Control+a")
    page.keyboard.press("Backspace")
    text = policy_text.strip()
    for i in range(0, len(text), 8000):
        page.keyboard.insert_text(text[i : i + 8000])
        pause(0.2, 0.5)

    pause_long()
    log("Docs: Share")
    if not ui.click_button(i18n.SHARE, "Share button top right"):
        if ui.use_vision and ui.gemini_api_key:
            vision_act(page, ui.gemini_api_key, "Click Share button", log)
    pause(1.0, 2.0)

    _name_before_sharing(page, doc_title, ui)
    url = _share_and_copy_link(page, ui)
    if url:
        log(f"Docs: privacy URL → {url[:80]}…")
    return url


def _wait_docs_home(page, log: Callable[[str], None]) -> None:
    try:
        page.wait_for_selector("text=Start a new document", timeout=25_000)
    except Exception:
        try:
            page.wait_for_load_state("networkidle", timeout=20_000)
        except Exception:
            log("Docs: home load partial (continuing)")


def _name_before_sharing(page, title: str, ui: PublishUI) -> None:
    try:
        dialog = page.locator("[role='dialog']").filter(has_text=re.compile("sharing", re.I))
        if dialog.count() == 0:
            return
        ui.log("Docs: name before sharing")
        dialog.locator("input").first.fill(title)
        pause(0.5, 1.0)
        ui.click_button(i18n.SAVE, "Save document name before sharing")
        pause_long()
    except Exception:
        pass


def _share_and_copy_link(page, ui: PublishUI) -> str | None:
    log = ui.log
    pause(1.0, 2.0)
    for label in (
        "Anyone with the link",
        "Anyone with link",
        "Все, у кого есть ссылка",
        "Всі, у кого є посилання",
    ):
        try:
            page.get_by_text(re.compile(re.escape(label), re.I)).first.click(timeout=3000)
            pause(0.8, 1.5)
            break
        except Exception:
            continue
    for label in ("Viewer", "Читатель", "Читач", "Просмотр", "Переглядач"):
        try:
            page.get_by_text(re.compile(f"^{label}$", re.I)).first.click(timeout=2000)
            break
        except Exception:
            continue

    if not ui.click_button(i18n.COPY_LINK, "Copy link"):
        if ui.use_vision and ui.gemini_api_key:
            vision_act(page, ui.gemini_api_key, "Click Copy link in share dialog", log)
    pause(1.0, 2.0)

    try:
        url = page.evaluate("() => navigator.clipboard.readText()")
        if url and "docs.google.com" in url:
            return url.strip()
    except Exception:
        pass

    try:
        for inp in page.locator("input").all():
            val = inp.input_value() or ""
            if "docs.google.com" in val:
                return val.strip()
    except Exception:
        pass

    log("WARN: Docs URL not read — check clipboard manually")
    return None
