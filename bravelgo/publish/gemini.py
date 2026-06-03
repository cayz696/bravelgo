"""Google Gemini API — listing and privacy text generation."""
from __future__ import annotations

import json
import random
import re
import time
import urllib.error
import urllib.request
from datetime import date
from typing import Any

DEFAULT_MODEL = "gemini-2.0-flash"


class GeminiPublishError(Exception):
    pass


def unique_seed() -> str:
    return f"{int(time.time())}-{random.randint(1000, 99999)}"


def fill_prompt(template: str, **kwargs: str) -> str:
    out = template
    for key, val in kwargs.items():
        out = out.replace("{" + key + "}", val or "")
    return out


def _call_gemini(api_key: str, prompt: str, model: str = DEFAULT_MODEL) -> str:
    if not api_key.strip():
        raise GeminiPublishError("Gemini API key is empty")
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={api_key.strip()}"
    )
    body = json.dumps(
        {"contents": [{"parts": [{"text": prompt}]}]},
        ensure_ascii=False,
    ).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")[:400]
        raise GeminiPublishError(f"Gemini HTTP {exc.code}: {err_body}") from exc
    except urllib.error.URLError as exc:
        raise GeminiPublishError(f"Gemini network error: {exc}") from exc

    try:
        parts = data["candidates"][0]["content"]["parts"]
        return "\n".join(p.get("text", "") for p in parts if p.get("text")).strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise GeminiPublishError(f"Unexpected Gemini response: {data!r:.300}") from exc


def generate_listing(
    api_key: str,
    template: str,
    app_name: str,
    account_email: str,
    seed: str | None = None,
) -> dict[str, str]:
    prompt = fill_prompt(
        template,
        APP_NAME=app_name,
        ACCOUNT_EMAIL=account_email,
        UNIQUE_SEED=seed or unique_seed(),
    )
    raw = _call_gemini(api_key, prompt)
    return parse_listing_output(raw, app_name)


def generate_privacy(
    api_key: str,
    template: str,
    app_name: str,
    account_email: str,
    company_name: str = "",
    company_address: str = "",
    seed: str | None = None,
) -> str:
    prompt = fill_prompt(
        template,
        APP_NAME=app_name,
        ACCOUNT_EMAIL=account_email,
        COMPANY_NAME=company_name or "Individual developer",
        COMPANY_ADDRESS=company_address or "Not applicable",
        UNIQUE_SEED=seed or unique_seed(),
        DATE=date.today().isoformat(),
    )
    return _call_gemini(api_key, prompt).strip()


def parse_listing_output(raw: str, app_name: str) -> dict[str, str]:
    short = ""
    full = ""
    title = app_name

    m = re.search(r"Short Description:\s*(.+?)(?=\nFull Description:|\Z)", raw, re.I | re.S)
    if m:
        short = m.group(1).strip().split("\n")[0].strip()
    m = re.search(r"Full Description:\s*(.+)", raw, re.I | re.S)
    if m:
        full = m.group(1).strip()
    m = re.search(r"Title:\s*(.+)", raw, re.I)
    if m:
        title = m.group(1).strip().split("\n")[0].strip()[:30]

    if not short and not full:
        lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
        if len(lines) >= 2:
            short = lines[0][:80]
            full = "\n".join(lines[1:])[:4000]

    if len(short) > 80:
        short = short[:80]
    if len(title) > 30:
        title = title[:30]

    return {"title": title, "short": short, "full": full, "raw": raw}
