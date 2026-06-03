"""Gemini Vision — locate UI when DOM/locale selectors fail."""
from __future__ import annotations

import base64
import json
import re
import urllib.error
import urllib.request
from typing import Any, Callable

VISION_MODEL = "gemini-2.0-flash"


class VisionError(Exception):
    pass


def _call_vision(api_key: str, prompt: str, png_bytes: bytes) -> dict[str, Any]:
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{VISION_MODEL}:generateContent?key={api_key.strip()}"
    )
    body = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                    {
                        "inline_data": {
                            "mime_type": "image/png",
                            "data": base64.b64encode(png_bytes).decode("ascii"),
                        }
                    },
                ]
            }
        ],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 512},
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise VisionError(f"Vision HTTP {exc.code}: {exc.read()[:300]!r}") from exc

    text = ""
    try:
        parts = data["candidates"][0]["content"]["parts"]
        text = "\n".join(p.get("text", "") for p in parts if p.get("text"))
    except (KeyError, IndexError, TypeError) as exc:
        raise VisionError(f"Bad vision response: {data!r:.200}") from exc

    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{[^{}]*\}", text, re.S)
        if m:
            return json.loads(m.group(0))
        raise VisionError(f"Vision did not return JSON: {text[:200]}")


def vision_act(
    page,
    api_key: str,
    goal: str,
    log: Callable[[str], None],
) -> bool:
    """
    Screenshot → Gemini → click by coordinates or Playwright text/role.
    Returns True if an action was performed.
    """
    if not api_key:
        return False
    try:
        png = page.screenshot(type="png", full_page=False)
    except Exception as exc:
        log(f"Vision screenshot fail: {exc}")
        return False

    vp = page.viewport_size or {"width": 1400, "height": 900}
    w, h = vp.get("width", 1400), vp.get("height", 900)

    prompt = f"""You help automate Google Play Console or Google Docs in a browser.
Viewport: {w}x{h} pixels. Screenshot top-left is (0,0).

Goal: {goal}

Return ONLY JSON:
{{
  "action": "click" | "type" | "none",
  "x": <int 0-{w}>,
  "y": <int 0-{h}>,
  "text": "<optional label to click instead of x,y>",
  "keys": "<optional keyboard key name>",
  "reason": "<short>"
}}

Prefer "text" if a visible button/link matches the goal (Save, Share, Next, Copy link, Dashboard).
Use x,y only if no clear text. action "none" if impossible."""

    try:
        plan = _call_vision(api_key, prompt, png)
    except VisionError as exc:
        log(f"Vision: {exc}")
        return False

    action = (plan.get("action") or "none").lower()
    log(f"Vision: {action} — {plan.get('reason', '')[:80]}")

    if action == "none":
        return False

    if action == "type" and plan.get("text"):
        try:
            page.keyboard.insert_text(str(plan["text"]))
            return True
        except Exception:
            pass

    label = (plan.get("text") or "").strip()
    if label:
        try:
            page.get_by_role("button", name=re.compile(re.escape(label), re.I)).first.click(timeout=8000)
            return True
        except Exception:
            try:
                page.get_by_text(re.compile(re.escape(label), re.I)).first.click(timeout=8000)
                return True
            except Exception:
                pass

    if action == "click":
        x = int(plan.get("x", 0))
        y = int(plan.get("y", 0))
        if 0 <= x <= w and 0 <= y <= h:
            page.mouse.click(x, y)
            return True

    keys = plan.get("keys")
    if keys:
        page.keyboard.press(str(keys))
        return True
    return False
