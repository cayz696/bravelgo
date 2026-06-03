# BravelGo Publish Playbook

UI automation only (Firefox profile + Playwright). No Play API / service account.

## Publish tab fields

| Field | Usage |
|-------|--------|
| Account email | Content ratings, contact details, Gemini prompts |
| Package name | Open app in Console, create app |
| App name | Create app, Docs title, listing title |
| Listing / Privacy prompts | Gemini with `{APP_NAME}`, `{ACCOUNT_EMAIL}`, `{UNIQUE_SEED}` |
| Gemini API key | Per VM, stored in `~/.bravelgo.json` |
| Graphics folder | Optional: `icon-512.png`, `feature-1024x500.png`, `phone/*.png` |

## Google Docs (privacy URL)

1. `https://docs.google.com/document/u/0/?pli=1`
2. Blank document
3. Paste policy text
4. Share → name dialog → Save
5. Anyone with link → Viewer → Copy link
6. URL saved to `publish.last_privacy_url`

## Play Console flow

1. Create application (optional if app exists): en-US, Game, Free, declarations, check package
2. Dashboard → Set up your app → View tasks
3. Privacy policy URL → Save → Dashboard
4. App access / Ads / Content ratings / Target audience (16–17 + 18+) / Data safety / Gov / Financial / Health
5. Store settings: Arcade + contact email
6. Default store listing: texts + graphics

**Bot does not** submit for production — finish manually.

## Firefox

- **System deb Firefox** (`/usr/lib/firefox/firefox`), not snap
- **Profile auto-detect**: `~/.bravelgo.json` → `ff_profile` → `profiles.ini` Default → newest `bravelgo-*`
- Same cookies/2FA as **Launch Firefox** and Warmup

## Flow (Full publish)

1. **Detached** worker starts (background, like Warmup)
2. Playwright opens Firefox with your profile
3. You open **play.google.com/console** (developer / app)
4. Click **Continue — I'm on Console** in BravelGo (or auto when URL matches)
5. Google Docs → policy URL
6. Play Console dashboard tasks → store listing
7. You finish prod manually

## Gemini Vision

When a button is not found (UA/RU/EN UI), screenshot → Gemini → click Save/Share/Next.

## Buttons in UI

- **Continue — I'm on Console** — unblocks worker (`~/.bravelgo-publish-go`)
- **Generate texts** — Gemini only (no browser)
- **Docs only** / **Console only** / **Full publish**
- **Detached** ON = background + Tail log

## Logs

`~/.bravelgo-publish.log`
