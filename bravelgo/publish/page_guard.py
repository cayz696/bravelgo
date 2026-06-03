"""Detect Play Console page — avoid running dashboard steps on Create-app form."""
from __future__ import annotations

import re
from typing import Callable


def page_url(page) -> str:
    try:
        return (page.url or "").strip()
    except Exception:
        return ""


def is_status_dashboard_url(url: str) -> bool:
    return "status.play.google.com" in (url or "").lower()


def is_create_app_form_url(url: str) -> bool:
    """True only on the multi-step Create app wizard (name/package), not app-list home."""
    low = (url or "").lower()
    if "play.google.com/console" not in low:
        return False
    return "create-new-ap" in low or "/create/app" in low


def is_app_list_home(page) -> bool:
    """Empty account home: «Create your first app» — not the wizard yet."""
    url = page_url(page).lower()
    if "app-list" in url or url.rstrip("/").endswith("/developers"):
        return True
    try:
        pat = re.compile(r"create your first app|créez votre première|создайте первое", re.I)
        return page.get_by_text(pat).count() > 0
    except Exception:
        return False


def is_create_app_page(page) -> bool:
    """Still on the Create wizard (must submit before dashboard tasks)."""
    return is_create_app_form_url(page_url(page))


def is_app_dashboard_url(url: str) -> bool:
    low = (url or "").lower()
    if "play.google.com/console" not in low:
        return False
    if low.rstrip("/").endswith("/developers"):
        return False
    if "/app/" in low or "/app-list" in low or "app-dashboard" in low:
        return True
    return "/apps/" in low


def ensure_console_tab(page, log: Callable[[str], None]) -> None:
    """
    BravelGo only opens play.google.com/console (or Docs).
    status.play.google.com is Google's outage dashboard — often from profile session restore.
    """
    driver = getattr(page, "_driver", None)
    if driver is None:
        return

    handles = list(driver.window_handles)
    if len(handles) <= 1:
        url = page_url(page)
        if is_status_dashboard_url(url):
            log(
                "WARN: This tab is Google Play *Status* (status.play.google.com) — "
                "BravelGo does not open it. Go to play.google.com/console"
            )
        return

    console_handle = None
    status_count = 0
    for h in handles:
        try:
            driver.switch_to.window(h)
            url = driver.current_url or ""
        except Exception:
            continue
        if is_status_dashboard_url(url):
            status_count += 1
        elif "play.google.com/console" in url.lower():
            console_handle = h

    if status_count:
        log(
            f"Found {status_count} tab(s) on status.play.google.com (Google incident page, "
            "not BravelGo) — close them or use Play Console tab"
        )
    if console_handle:
        try:
            driver.switch_to.window(console_handle)
        except Exception:
            pass
