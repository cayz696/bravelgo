"""Minimal English listing + policy when Gemini quota is exceeded."""


def stub_listing(app_name: str) -> dict[str, str]:
    title = (app_name or "Game")[:30]
    short = f"Play {title} — fun arcade action and quick sessions."[:80]
    full = (
        f"{title} is a casual arcade game for quick, fun sessions.\n\n"
        "Features:\n"
        "• Easy to learn controls\n"
        "• Short levels you can play anytime\n"
        "• Family-friendly content\n\n"
        "Download and enjoy. Feedback is welcome via store support."
    )[:4000]
    return {"title": title, "short": short, "full": full, "raw": ""}


def stub_policy(app_name: str, email: str) -> str:
    app = app_name or "This App"
    contact = email or "support@example.com"
    return f"""Privacy Policy — {app}

Last updated: 2026-01-01

This policy describes how {app} ("we") handles information when you use our mobile game.

Information we collect
We may collect non-personal technical data (device type, OS version, crash logs) to improve stability. We do not sell personal data.

Children
The game is not directed at children under 13. Contact us if you believe a child provided personal data.

Third parties
We may use analytics or ad partners that process limited device identifiers under their own policies.

Contact
Questions: {contact}

Changes
We may update this policy; continued use means acceptance of the revised version.
""".strip()
