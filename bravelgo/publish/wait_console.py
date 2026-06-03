"""Wait until user is on Play Console before automation."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Callable

from bravelgo.publish.config import CONSOLE_URL

CONTINUE_FLAG = Path.home() / ".bravelgo-publish-go"
DEFAULT_WAIT_MINUTES = 45


def clear_continue_flag() -> None:
    try:
        CONTINUE_FLAG.unlink(missing_ok=True)
    except OSError:
        pass


def touch_continue_flag() -> None:
    CONTINUE_FLAG.write_text("go\n", encoding="utf-8")


def wait_for_console_ready(
    page,
    log: Callable[[str], None],
    *,
    flag_path: Path | None = None,
    timeout_minutes: int = DEFAULT_WAIT_MINUTES,
    open_console_hint: bool = True,
) -> None:
    """
    Blocks until:
    - flag file exists (BravelGo «Continue» button), or
    - current tab URL contains play.google.com/console
    """
    flag = flag_path or CONTINUE_FLAG
    clear_continue_flag()

    if open_console_hint:
        try:
            page.goto(CONSOLE_URL, wait_until="domcontentloaded")
        except Exception:
            pass

    log(
        "⏸ Waiting for you on Play Console…\n"
        "   Open developer home / your app, then in BravelGo click:\n"
        "   «Continue — I'm on Console»\n"
        f"   (auto-continue when URL is play.google.com/console, max {timeout_minutes} min)"
    )

    deadline = time.time() + timeout_minutes * 60
    last_url = ""

    while time.time() < deadline:
        if flag.is_file():
            try:
                flag.unlink()
            except OSError:
                pass
            log("Continue signal received — starting publish steps")
            return

        try:
            url = page.url or ""
            if url != last_url and "play.google.com/console" in url:
                log(f"Console detected: {url[:90]}")
                time.sleep(2)
                return
            last_url = url
        except Exception:
            pass

        time.sleep(2)

    raise TimeoutError(
        f"Play Console not ready within {timeout_minutes} min — "
        "open Console and click Continue in BravelGo"
    )
