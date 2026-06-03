"""Always use desktop user HOME (BravelGo often runs as root via sudo)."""
from __future__ import annotations

import os
from pathlib import Path


def user_home(explicit: str | None = None) -> Path:
    if explicit:
        return Path(explicit).expanduser()
    return Path(os.environ.get("HOME", str(Path.home()))).expanduser()


def config_path(home: str | None = None) -> Path:
    return user_home(home) / ".bravelgo.json"


def policy_cache_path(home: str | None = None) -> Path:
    return user_home(home) / ".bravelgo-publish-policy.txt"


def listing_cache_path(home: str | None = None) -> Path:
    return user_home(home) / ".bravelgo-publish-listing.json"


def publish_log_path(home: str | None = None) -> Path:
    return user_home(home) / ".bravelgo-publish.log"


def privacy_url_file(home: str | None = None) -> Path:
    return user_home(home) / ".bravelgo-publish-privacy-url.txt"


def write_privacy_url_file(url: str, home: str | None = None) -> None:
    path = privacy_url_file(home)
    path.write_text((url or "").strip(), encoding="utf-8")


def read_privacy_url_file(home: str | None = None) -> str:
    path = privacy_url_file(home)
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8").strip()
