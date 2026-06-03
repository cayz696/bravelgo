"""Load store listing / policy from disk when Gemini quota is exceeded."""
from __future__ import annotations

from pathlib import Path
from typing import Callable

DEFAULT_TEXTS_ROOT = Path.home() / "bravelgo-publish-texts"


def texts_dir_for_package(package_name: str, custom_dir: str = "") -> Path:
    if custom_dir.strip():
        return Path(custom_dir).expanduser()
    safe = package_name.replace(".", "_") if package_name else "app"
    return DEFAULT_TEXTS_ROOT / safe


def try_load_local_texts(
    package_name: str,
    app_name: str,
    custom_dir: str,
    log: Callable[[str], None],
) -> tuple[dict[str, str] | None, str | None]:
    """
    Expects optional files in texts dir:
      title.txt, short.txt, full.txt, policy.txt
    """
    base = texts_dir_for_package(package_name, custom_dir)
    if not base.is_dir():
        return None, None

    title_f = base / "title.txt"
    short_f = base / "short.txt"
    full_f = base / "full.txt"
    policy_f = base / "policy.txt"

    listing = None
    if short_f.is_file() or full_f.is_file():
        title = title_f.read_text(encoding="utf-8").strip() if title_f.is_file() else app_name
        short = short_f.read_text(encoding="utf-8").strip() if short_f.is_file() else ""
        full = full_f.read_text(encoding="utf-8").strip() if full_f.is_file() else ""
        listing = {
            "title": (title or app_name)[:30],
            "short": short[:80],
            "full": full[:4000],
            "raw": "",
        }
        log(f"Loaded listing from {base}")

    policy = None
    if policy_f.is_file():
        policy = policy_f.read_text(encoding="utf-8").strip()
        log(f"Loaded policy from {policy_f}")

    if listing or policy:
        return listing, policy
    return None, None


def ensure_texts_dir(package_name: str, custom_dir: str, log: Callable[[str], None]) -> Path:
    base = texts_dir_for_package(package_name, custom_dir)
    base.mkdir(parents=True, exist_ok=True)
    log(f"Texts folder: {base}")
    for name, hint in (
        ("title.txt", "app title max 30 chars"),
        ("short.txt", "short description max 80"),
        ("full.txt", "full description"),
        ("policy.txt", "privacy policy plain text"),
    ):
        p = base / name
        if not p.is_file():
            p.write_text(f"# {hint}\n", encoding="utf-8")
    return base
