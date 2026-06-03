"""Playwright-like API on Selenium WebDriver (same flows as before)."""
from __future__ import annotations

import re
import time
from typing import Any, Pattern

from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

_ROLE_TAGS = {
    "button": "button",
    "link": "a",
    "radio": "input[type='radio']",
    "option": "[role='option'], option",
}


def _ms(timeout: int | None) -> float:
    return max(0.5, (timeout or 10_000) / 1000.0)


def _text_matches(el, pattern: Pattern[str] | str | None) -> bool:
    if pattern is None:
        return True
    parts = [
        (el.text or ""),
        (el.get_attribute("aria-label") or ""),
        (el.get_attribute("value") or ""),
        (el.get_attribute("title") or ""),
    ]
    blob = " ".join(parts)
    if isinstance(pattern, re.Pattern):
        return bool(pattern.search(blob))
    return pattern.lower() in blob.lower()


class SeleniumLocator:
    def __init__(self, driver, *, root=None, css: str | None = None, xpath: str | None = None):
        self._driver = driver
        self._root = root
        self._css = css
        self._xpath = xpath

    @property
    def first(self) -> SeleniumLocator:
        return self

    def count(self) -> int:
        return len(self._elements())

    def all(self) -> list[SeleniumLocator]:
        return [SeleniumLocator(self._driver, root=el) for el in self._elements()]

    def locator(self, selector: str) -> SeleniumLocator:
        if selector.startswith("xpath="):
            xp = selector[6:].strip()
            if self._root is not None and xp == "..":
                return SeleniumLocator(
                    self._driver,
                    root=self._root.find_element(By.XPATH, "./.."),
                )
            if self._root is not None:
                rel = xp if xp.startswith(".") else f".//{xp.lstrip('/')}"
                return SeleniumLocator(self._driver, root=self._root, xpath=rel)
            return SeleniumLocator(self._driver, xpath=xp)
        if selector.startswith("text="):
            return SeleniumLocator(self._driver, root=self._root, xpath=_text_selector_xpath(selector[5:]))
        return SeleniumLocator(self._driver, root=self._root, css=selector)

    def filter(self, has_text: Pattern[str] | str | None = None) -> SeleniumLocator:
        return _FilteredLocator(self._driver, self, has_text)

    def click(self, timeout: int = 10_000) -> None:
        el = self._wait_one(timeout)
        try:
            el.click()
        except Exception:
            self._driver.execute_script("arguments[0].click();", el)

    def fill(self, text: str, timeout: int = 10_000) -> None:
        el = self._wait_one(timeout)
        el.clear()
        el.send_keys(text)

    def check(self) -> None:
        el = self._wait_one(10_000)
        if not el.is_selected():
            el.click()

    def input_value(self) -> str:
        el = self._wait_one(5_000)
        return (el.get_attribute("value") or "").strip()

    def set_input_files(self, path: str) -> None:
        el = self._wait_one(15_000)
        el.send_keys(path)

    def scroll_into_view_if_needed(self) -> None:
        el = self._wait_one(8_000)
        self._driver.execute_script(
            "arguments[0].scrollIntoView({block:'center',inline:'nearest'});", el
        )

    def _elements(self) -> list:
        drv = self._driver
        if self._root is not None:
            if self._css:
                return self._root.find_elements(By.CSS_SELECTOR, self._css)
            if self._xpath:
                return self._root.find_elements(By.XPATH, self._xpath)
            return [self._root]
        if self._css:
            return drv.find_elements(By.CSS_SELECTOR, self._css)
        if self._xpath:
            return drv.find_elements(By.XPATH, self._xpath)
        return []

    def _wait_one(self, timeout: int):
        deadline = time.time() + _ms(timeout)
        last: Exception | None = None
        while time.time() < deadline:
            els = self._elements()
            if els:
                return els[0]
            time.sleep(0.25)
            last = TimeoutError("element not found")
        raise last or TimeoutError("element not found")


class _FilteredLocator(SeleniumLocator):
    def __init__(self, driver, parent: SeleniumLocator, has_text):
        super().__init__(driver, root=None)
        self._parent = parent
        self._has_text = has_text

    def locator(self, selector: str) -> SeleniumLocator:
        els = self._elements()
        if els:
            return SeleniumLocator(self._driver, root=els[0]).locator(selector)
        return SeleniumLocator(self._driver).locator(selector)

    def _elements(self) -> list:
        out = []
        for el in self._parent._elements():
            if _text_matches(el, self._has_text):
                out.append(el)
            else:
                for sub in el.find_elements(By.XPATH, ".//*"):
                    if _text_matches(sub, self._has_text):
                        out.append(sub)
                        break
        return out


def _text_selector_xpath(spec: str) -> str:
    m = re.match(r"^/(.+)/([ims]*)$", spec.strip())
    if m:
        body = m.group(1)
        return f"//*[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{body.lower()[:40]}')]"
    return f"//*[contains(text(), {repr(spec)})]"


class SeleniumKeyboard:
    def __init__(self, driver):
        self._driver = driver

    def press(self, combo: str) -> None:
        key = combo.strip()
        mapping = {
            "Control+a": (Keys.CONTROL, "a"),
            "Backspace": (Keys.BACKSPACE,),
            "Escape": (Keys.ESCAPE,),
            "Enter": (Keys.ENTER,),
        }
        chain = ActionChains(self._driver)
        if key in mapping:
            seq = mapping[key]
            if len(seq) == 2:
                chain.key_down(seq[0]).send_keys(seq[1]).key_up(seq[0])
            else:
                chain.send_keys(seq[0])
            chain.perform()
            return
        ActionChains(self._driver).send_keys(key).perform()

    def insert_text(self, text: str) -> None:
        try:
            active = self._driver.switch_to.active_element
            active.send_keys(text)
        except Exception:
            self._driver.find_element(By.TAG_NAME, "body").send_keys(text)


class SeleniumMouse:
    def __init__(self, driver):
        self._driver = driver

    def click(self, x: int, y: int) -> None:
        self._driver.execute_script(
            """
            const el = document.elementFromPoint(arguments[0], arguments[1]);
            if (el) el.click();
            """,
            int(x),
            int(y),
        )


class SeleniumPage:
    """Minimal Playwright-compatible surface for publish flows."""

    def __init__(self, driver):
        self._driver = driver
        self.keyboard = SeleniumKeyboard(driver)
        self.mouse = SeleniumMouse(driver)

    @property
    def url(self) -> str:
        return self._driver.current_url or ""

    @property
    def viewport_size(self) -> dict[str, int]:
        try:
            sz = self._driver.get_window_size()
            return {"width": sz.get("width", 1400), "height": sz.get("height", 900)}
        except Exception:
            return {"width": 1400, "height": 900}

    def goto(self, url: str, wait_until: str | None = None) -> None:
        self._driver.get(url)
        if wait_until in ("networkidle", "load"):
            time.sleep(2.5 if wait_until == "networkidle" else 1.0)

    def locator(self, selector: str) -> SeleniumLocator:
        if selector.startswith("text="):
            return SeleniumLocator(self._driver, xpath=_text_selector_xpath(selector[5:]))
        return SeleniumLocator(self._driver, css=selector)

    def get_by_role(self, role: str, name: Pattern[str] | str | None = None) -> SeleniumLocator:
        return _RoleLocator(self._driver, role, name)

    def get_by_text(self, pattern: Pattern[str] | str, exact: bool = False) -> SeleniumLocator:
        return _TextLocator(self._driver, pattern, exact)

    def wait_for_selector(self, selector: str, timeout: int = 10_000) -> None:
        if selector.startswith("text="):
            xp = _text_selector_xpath(selector[5:])
            WebDriverWait(self._driver, _ms(timeout)).until(
                EC.presence_of_element_located((By.XPATH, xp))
            )
            return
        WebDriverWait(self._driver, _ms(timeout)).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
        )

    def wait_for_load_state(self, state: str, timeout: int = 10_000) -> None:
        if state == "networkidle":
            time.sleep(min(4.0, _ms(timeout) * 0.3))
            return
        WebDriverWait(self._driver, _ms(timeout)).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

    def evaluate(self, script: str) -> Any:
        if script.strip().startswith("() =>"):
            script = script.strip()[5:]
        if script.strip().startswith("function"):
            return self._driver.execute_script(script)
        return self._driver.execute_script(f"return ({script})")

    def screenshot(self, type: str = "png", full_page: bool = False) -> bytes:
        if full_page:
            try:
                w = self._driver.execute_script(
                    "return Math.max(document.body.scrollWidth, document.documentElement.scrollWidth);"
                )
                h = self._driver.execute_script(
                    "return Math.max(document.body.scrollHeight, document.documentElement.scrollHeight);"
                )
                self._driver.set_window_size(min(int(w), 4000), min(int(h), 8000))
            except Exception:
                pass
        return self._driver.get_screenshot_as_png()


class _RoleLocator(SeleniumLocator):
    def __init__(self, driver, role: str, name: Pattern[str] | str | None):
        super().__init__(driver)
        self._role = role
        self._name = name

    def _elements(self) -> list:
        css = _ROLE_TAGS.get(self._role, self._role)
        found = []
        for el in self._driver.find_elements(By.CSS_SELECTOR, css):
            if _text_matches(el, self._name):
                found.append(el)
        if not found and self._role == "link":
            for el in self._driver.find_elements(By.XPATH, "//*[@role='link']"):
                if _text_matches(el, self._name):
                    found.append(el)
        return found


class _TextLocator(SeleniumLocator):
    def __init__(self, driver, pattern: Pattern[str] | str, exact: bool):
        super().__init__(driver)
        self._pattern = pattern
        self._exact = exact

    def _elements(self) -> list:
        out = []
        for el in self._driver.find_elements(By.XPATH, "//*[not(self::script) and not(self::style)]"):
            txt = (el.text or "").strip()
            if not txt:
                continue
            if isinstance(self._pattern, re.Pattern):
                ok = bool(self._pattern.search(txt)) if not self._exact else bool(self._pattern.fullmatch(txt))
            elif self._exact:
                ok = txt.lower() == str(self._pattern).lower()
            else:
                ok = str(self._pattern).lower() in txt.lower()
            if ok:
                out.append(el)
        return out
