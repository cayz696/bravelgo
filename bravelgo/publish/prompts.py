"""Default Gemini prompt templates for Publish tab."""

DEFAULT_LISTING_PROMPT = """You are a professional ASO copywriter for mobile games.
Your task is to generate a Google Play Store description for an arcade game.

Game title: "{APP_NAME}"
Developer contact email (for consistency only, do not paste in description): {ACCOUNT_EMAIL}
Category: Arcade
Unique run id: {UNIQUE_SEED} — vary phrasing each time; do not repeat stock openings.

Requirements:
1. Generate:
   - Short Description (max 80 characters)
   - Full Description (well-structured, 1500–2500 characters)
2. Style:
   - Clear, natural English
   - No hype, no spammy phrases
   - No emojis
   - No fake multiplayer or features
   - No references to real brands or copyrighted content
3. Content rules:
   - The game is a simple arcade experience
   - Focus on gameplay loop, control, progression, challenge
   - Keep it generic but appealing
   - Do NOT invent complex systems (no RPG, no story, no online unless implied by name)
   - Safe for Google Play review (no policy risks)
4. Structure for Full Description:
   - Intro paragraph (what the game is)
   - Core gameplay explanation
   - Key Features (bullet points using "•")
   - Progression / challenge section
   - Closing paragraph (why user should try it)
5. Keywords:
   - Naturally include: arcade, gameplay, control, challenge, speed, levels, reaction, skill
6. Output format (plain text, no markdown fences):
Title: {APP_NAME}
Short Description: <text>
Full Description: <text>
"""

DEFAULT_PRIVACY_PROMPT = """You are a legal copywriter for mobile app privacy policies on Google Play.

App name: "{APP_NAME}"
Developer / contact email: {ACCOUNT_EMAIL}
Company legal name (if known): {COMPANY_NAME}
Company address (if known): {COMPANY_ADDRESS}
Target age: 16+
Collects personal data: No
Unique run id: {UNIQUE_SEED} — use slightly different wording than typical templates.

Write a complete privacy policy suitable for pasting into Google Docs (plain text with clear headings).
Sections: Introduction, Information We Collect, How We Use Information, Third-Party Services,
Children's Privacy, Data Security, Changes to This Policy, Contact Us.
State clearly that the app does not collect personal data if that is the case.
Include "Last updated: {DATE}" at the top.
No HTML tags. No markdown code fences. English only.
"""
