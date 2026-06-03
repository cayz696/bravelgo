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
