"""Detect dead Selenium session — stop automation instead of spamming errors."""
from __future__ import annotations

from selenium.common.exceptions import InvalidSessionIdException, WebDriverException


class BrowserSessionDead(Exception):
    """Firefox was closed or geckodriver lost connection."""


_SESSION_DEAD_LOGGED = False


def is_invalid_session_error(exc: BaseException) -> bool:
    if isinstance(exc, InvalidSessionIdException):
        return True
    msg = str(exc).lower()
    return (
        "invalidsessionid" in msg
        or "without establishing a connection" in msg
        or "failed to decode response from marionette" in msg
    )


def session_alive(page) -> bool:
    driver = getattr(page, "_driver", None)
    if driver is None:
        return False
    try:
        _ = driver.current_url
        return True
    except (InvalidSessionIdException, WebDriverException):
        return False
    except Exception:
        return False


def ensure_session(page) -> None:
    global _SESSION_DEAD_LOGGED
    if session_alive(page):
        return
    if not _SESSION_DEAD_LOGGED:
        _SESSION_DEAD_LOGGED = True
    raise BrowserSessionDead(
        "Firefox window was closed or crashed — automation stopped. "
        "Re-run Full publish and do not close Firefox until finished."
    )


def wrap_session_error(exc: BaseException) -> BaseException:
    if is_invalid_session_error(exc):
        dead = BrowserSessionDead(
            "Firefox window was closed or crashed — automation stopped."
        )
        dead.__cause__ = exc
        return dead
    return exc


def reset_session_guard() -> None:
    global _SESSION_DEAD_LOGGED
    _SESSION_DEAD_LOGGED = False
