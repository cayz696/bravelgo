"""Clicks with i18n + Gemini Vision fallback."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

from bravelgo.publish.human import pause, pause_long
from bravelgo.publish.vision import vision_act


@dataclass
class PublishUI:
    page: object
    log: Callable[[str], None]
    gemini_api_key: str = ""
    use_vision: bool = True

    def click_button(self, pattern: re.Pattern[str], goal: str, timeout: int = 12_000) -> bool:
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
            self.log(f"Click fail ({goal}): {exc}")
        if self.use_vision and self.gemini_api_key:
            self.log(f"Vision fallback: {goal}")
            if vision_act(self.page, self.gemini_api_key, f"Click button: {goal}", self.log):
                pause_long()
                return True
        return False

    def save(self, overflow: bool = False) -> None:
        from bravelgo.publish import i18n

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
        if self.click_button(pattern, goal, timeout=10_000):
            return
        try:
            self.page.get_by_role("radio", name=pattern).first.click(timeout=8000)
            pause(0.4, 1.0)
        except Exception:
            if self.use_vision and self.gemini_api_key:
                vision_act(self.page, self.gemini_api_key, f"Select radio: {goal}", self.log)
