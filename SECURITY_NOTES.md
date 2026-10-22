# Security notes — sanitization record for this public copy

This repository is a sanitized copy of a working local system, prepared on
2026-10-22 for public release. The originals stay on the builder's machine;
nothing was changed in the originals.

## What was checked

All three copied files (`mcp_bridge.py`, `dashboard.html`,
`urdealer-app.html`) were swept for: token values, passwords, API keys,
hardcoded credential file paths, personal email addresses, and phone
numbers.

**Result of the sweep:** no token values, no passwords, no API keys, no
email addresses, and no phone numbers were present in the source files.
The bridge never contained its backend token — by design it reads the token
from a local file at runtime. The items below are the path/configuration
and identifier changes that were still made so the public copy is generic
and cannot leak machine layout.

## Changes made in `mcp_bridge.py`

1. **Hardcoded Windows path to the switchboard token file** (the
   `TOKEN_PATH` assignment) → replaced with the `SWITCHBOARD_TOKEN_PATH`
   environment variable, defaulting to the placeholder filename
   `switchboard_api_token.txt` in the working directory.
2. **Hardcoded Windows path to the agent mailbox directory** (the
   `ORDERS_DIR` assignment) → replaced with the `AGENT_ORDERS_DIR`
   environment variable, defaulting to a repo-local `agent-orders/` folder.
3. **Hardcoded switchboard URL** → overridable via `SWITCHBOARD_URL`
   (same localhost default).
4. **Module docstring** — a personal build-credit line and the builder's
   workstation name were removed; the description now names the backend
   contract instead of a specific machine.
5. **Default sender identifiers** (two places: the `/api/send` default and
   the mailbox note author) — a personal first name used as the owner
   username was genericized to `owner`.

## Changes made in `dashboard.html`

1. **Workstation name** (three occurrences: sign-in footer, the
   "password stored hashed" line, the footer data-source line) →
   generic "local host" / "this machine" wording.
2. **Owner first name** (two occurrences: the "Needs …" panel heading and
   the task-composer approval hint) → "the owner".

## Changes made in `urdealer-app.html`

1. **Sender username identifier** (two places: the "is this from the owner"
   check and the message payload's `from` field) — the same personal first
   name as above, genericized to `owner` / `owner-urdealer` so the app and
   the bridge stay consistent inside this pack.

Project branding (ABUZ8 LLC, URDealer) and the fleet's agent names/lanes
were intentionally kept — they are the product's public identity in the
hackathon submission, not credentials or private data.

## What a user must provide themselves

- Their own **switchboard backend** implementing the endpoints listed in
  the README (not included in this repo).
- Their own **switchboard token file** (contents never ship with the code).
- Their own **dashboard password**, set on first run; only its SHA-256 hash
  is stored locally in `dashboard_auth.json` (gitignored).
- Their own **agent-orders directory** with `INBOX/` and `OUTBOX/`, if they
  use mailbox delivery for non-roster agents.

## Known security limitations (honest list)

- The MCP endpoint has **no client authentication** in this code. It is
  safe only under its intended model: bound to `127.0.0.1`, same machine,
  same user. Do not port-forward or reverse-proxy it without adding auth.
- Dashboard password hashing is SHA-256 with a static prefix — adequate
  for a single local owner gate, not a credential store. Use a unique
  password you do not reuse elsewhere.
- Sessions are random tokens held in server memory (12-hour expiry); a
  server restart logs everyone out. There is no rate limiting on the login
  route in this code.
- The switchboard token is read from disk on every backend call and sent
  only to the configured backend URL over localhost HTTP.
