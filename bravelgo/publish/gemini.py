"""Google Gemini API — listing and privacy (free tier: one model, short 429 wait)."""
from __future__ import annotations

import json
import random
import re
import time
import urllib.error
import urllib.request
from datetime import date

from bravelgo.publish.config import normalize_gemini_model

DEFAULT_MODEL = "gemini-2.5-flash"
PUBLISH_MODEL_CHOICES = (
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
)
# One short wait — long chains waste minutes then still 429
RETRY_WAIT_SEC = (50,)
PAUSE_BETWEEN_CALLS_SEC = 15


class GeminiPublishError(Exception):
    pass


def unique_seed() -> str:
    return f"{int(time.time())}-{random.randint(1000, 99999)}"


def fill_prompt(template: str, **kwargs: str) -> str:
    out = template
    for key, val in kwargs.items():
        out = out.replace("{" + key + "}", val or "")
    return out


def _parse_http_error(exc: urllib.error.HTTPError) -> str:
    try:
        body = json.loads(exc.read().decode("utf-8", errors="replace"))
        return body.get("error", {}).get("message", "")[:500]
    except Exception:
        return exc.read().decode("utf-8", errors="replace")[:500]


def _call_gemini_once(api_key: str, prompt: str, model: str) -> str:
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={api_key.strip()}"
    )
    payload: dict = {"contents": [{"parts": [{"text": prompt}]}]}
    if "2.5" in model and "flash" in model.lower() and "pro" not in model.lower():
        payload["generationConfig"] = {
            "thinkingConfig": {"thinkingBudget": 0},
            "temperature": 0.85,
        }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    parts = data["candidates"][0]["content"]["parts"]
    return "\n".join(p.get("text", "") for p in parts if p.get("text")).strip()


def _call_gemini(api_key: str, prompt: str, model: str = DEFAULT_MODEL, log=None) -> str:
    if not api_key.strip():
        raise GeminiPublishError("Gemini API key is empty")

    m = normalize_gemini_model(model)
    if log:
        log(f"Gemini API · model={m} (one retry on 429)")

    for attempt, wait in enumerate((0,) + RETRY_WAIT_SEC):
        if wait:
            if log:
                log(f"Gemini 429 — wait {wait}s, retry…")
            time.sleep(wait)
        try:
            return _call_gemini_once(api_key, prompt, m)
        except urllib.error.HTTPError as exc:
            msg = _parse_http_error(exc)
            if exc.code == 429 and attempt < len(RETRY_WAIT_SEC):
                continue
            if exc.code == 429:
                raise GeminiPublishError(_quota_help(msg)) from exc
            if exc.code in (503, 500) and attempt < len(RETRY_WAIT_SEC):
                continue
            raise GeminiPublishError(f"Gemini HTTP {exc.code}: {msg}") from exc
        except urllib.error.URLError as exc:
            raise GeminiPublishError(f"Gemini network error: {exc}") from exc
        except (KeyError, IndexError, TypeError) as exc:
            raise GeminiPublishError("Unexpected Gemini response") from exc

    raise GeminiPublishError(_quota_help("quota exceeded"))


def _quota_help(detail: str) -> str:
    return (
        "Gemini 429 (quota). Wait 5–10 min OR «Create stub texts» / texts folder / "
        "uncheck Gemini in settings. Do not spam Generate. "
        f"{detail[:180]}"
    )


def generate_listing(
    api_key: str,
    template: str,
    app_name: str,
    account_email: str,
    seed: str | None = None,
    log=None,
    model: str = "",
) -> dict[str, str]:
    prompt = fill_prompt(
        template,
        APP_NAME=app_name,
        ACCOUNT_EMAIL=account_email,
        UNIQUE_SEED=seed or unique_seed(),
    )
    raw = _call_gemini(api_key, prompt, model=model, log=log)
    return parse_listing_output(raw, app_name)


def generate_privacy(
    api_key: str,
    template: str,
    app_name: str,
    account_email: str,
    company_name: str = "",
    company_address: str = "",
    seed: str | None = None,
    log=None,
    model: str = "",
) -> str:
    if log:
        log(f"Pause {PAUSE_BETWEEN_CALLS_SEC}s between listing and policy…")
    time.sleep(PAUSE_BETWEEN_CALLS_SEC)
    prompt = fill_prompt(
        template,
        APP_NAME=app_name,
        ACCOUNT_EMAIL=account_email,
        COMPANY_NAME=company_name or "Individual developer",
        COMPANY_ADDRESS=company_address or "Not applicable",
        UNIQUE_SEED=seed or unique_seed(),
        DATE=date.today().isoformat(),
    )
    return _call_gemini(api_key, prompt, model=model, log=log).strip()


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
