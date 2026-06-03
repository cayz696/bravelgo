"""Clicks with i18n + Gemini Vision fallback."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

from bravelgo.publish.human import pause, pause_long
from bravelgo.publish.session_util import BrowserSessionDead, ensure_session, is_invalid_session_error
from bravelgo.publish.vision import vision_act


@dataclass
class PublishUI:
    page: object
    log: Callable[[str], None]
    gemini_api_key: str = ""
    use_vision: bool = True
    _session_dead: bool = False

    def _guard_session(self) -> bool:
        if self._session_dead:
            return False
        try:
            ensure_session(self.page)
            return True
        except BrowserSessionDead as exc:
            self._session_dead = True
            self.use_vision = False
            self.log(str(exc))
            return False

    def click_button(self, pattern: re.Pattern[str], goal: str, timeout: int = 12_000) -> bool:
        if not self._guard_session():
            return False
        try:
            self.page.get_by_role("button", name=pattern).first.click(timeout=timeout)
            pause(0.5, 1.5)
            return True
        except Exception:
            pass
        try:
            self.page.get_by_role("link", name=pattern).first.click(timeout=timeout)
            pause(0.5, 1.5)
            return True
        except Exception:
            pass
        try:
            self.page.get_by_text(pattern).first.click(timeout=timeout)
            pause(0.5, 1.5)
            return True
        except Exception as exc:
            if is_invalid_session_error(exc):
                self._session_dead = True
                self.use_vision = False
                raise BrowserSessionDead(
                    "Firefox window was closed or crashed — automation stopped."
                ) from exc
            self.log(f"Click fail ({goal}): {str(exc)[:100]}")
        if self.use_vision and self.gemini_api_key and self._guard_session():
            self.log(f"Vision fallback: {goal}")
            if vision_act(self.page, self.gemini_api_key, f"Click button: {goal}", self.log):
                pause_long()
                return True
        return False

    def save(self, overflow: bool = False) -> None:
        from bravelgo.publish import i18n

        if not self._guard_session():
            return
        goal = "Save changes (or Save in overflow ⋮ menu)"
        if overflow:
            if self._save_overflow():
                return
        if self.click_button(i18n.SAVE, goal):
            pause_long()
            return
        if self._save_overflow():
            pause_long()
            return
        if self.use_vision and self.gemini_api_key:
            vision_act(
                self.page,
                self.gemini_api_key,
                "Click Save — may be under three-dots More menu top right",
                self.log,
            )
            pause_long()

    def _save_overflow(self) -> bool:
        from bravelgo.publish import i18n

        try:
            more = self.page.locator(
                'button[aria-label*="More"], button[aria-haspopup="menu"]'
            ).first
            more.click(timeout=8000)
            pause(0.5, 1.0)
            return self.click_button(i18n.SAVE, "Save in dropdown menu", timeout=8000)
        except Exception:
            return False

    def click_radio_text(self, pattern: re.Pattern[str], goal: str) -> None:
        if not self._guard_session():
            return
        if self.click_button(pattern, goal, timeout=10_000):
            return
        try:
            self.page.get_by_role("radio", name=pattern).first.click(timeout=8000)
            pause(0.4, 1.0)
            return
        except Exception:
            pass
        if self._click_radio_by_visible_text(pattern, goal):
            pause(0.4, 1.0)
            return
        if self.use_vision and self.gemini_api_key:
            vision_act(self.page, self.gemini_api_key, f"Select radio: {goal}", self.log)

    def _click_radio_by_visible_text(self, pattern: re.Pattern[str], goal: str) -> bool:
        driver = getattr(self.page, "_driver", None)
        if driver is None:
            return False
        script = r"""
const source = arguments[0];
const re = new RegExp(source, 'i');
const visible = (el) => {
  const r = el.getBoundingClientRect();
  const s = window.getComputedStyle(el);
  return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
};
const nodes = [...document.querySelectorAll('label, span, div, mat-radio-button, [role="radio"]')]
  .filter(visible)
  .map(el => ({el, text: (el.innerText || el.textContent || '').trim()}))
  .filter(x => x.text && re.test(x.text))
  .sort((a, b) => a.text.length - b.text.length);
for (const {el} of nodes) {
  const root = el.closest('label, mat-radio-button, .mdc-form-field, [role="radio"]') || el.parentElement || el;
  const input = root.querySelector && root.querySelector('input[type="radio"]');
  const target = input || root || el;
  target.scrollIntoView({block: 'center', inline: 'nearest'});
  target.click();
  return true;
}
return false;
"""
        try:
            ok = bool(driver.execute_script(script, pattern.pattern))
            if ok:
                self.log(f"Selected radio by visible text: {goal}")
            return ok
        except Exception as exc:
            if is_invalid_session_error(exc):
                self._session_dead = True
                self.use_vision = False
                raise BrowserSessionDead(
                    "Firefox window was closed or crashed — automation stopped."
                ) from exc
            self.log(f"Radio text fallback failed ({goal}): {str(exc)[:100]}")
            return False
