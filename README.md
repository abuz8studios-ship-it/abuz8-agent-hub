# ABUZ8 Agent Hub — MCP Agent Bridge + URDealer

A local-first MCP bridge that lets one person run a small fleet of AI agents as a
single team: one endpoint, initialize → handshake → work.

Any MCP client connects to a single MCP Streamable HTTP endpoint and gets the
same six tools for messaging, presence, and a shared work queue. The same
process also serves **URDealer**, a web "dealer office" dashboard, and a
phone-first multi-agent chat app, so the human owner can watch the fleet and
put it to work from a browser.

Built by ABUZ8 LLC (Dayton, Ohio) and verified live on the builder's
workstation on October 22, 2026: MCP `initialize` handshake, `tools/list`,
`tools/call` for `ping` / `list_agents` / `heartbeat`, dashboard sign-in,
state, send, and task-post routes were all exercised end to end against the
live backend on that machine.

## Architecture

```
MCP clients ──► MCP Agent Bridge (this repo, :8392/mcp)
(Zait, Qadir,        │  6 MCP tools + URDealer office (/) + mobile chat (/app)
 Amanecer, mcode)    │  token read server-side from a local file,
                     │  never sent to clients
                     ▼
              Switchboard backend (NOT included in this repo)
              local HTTP service, default http://127.0.0.1:8380
              provides /factory/heartbeats, /factory/tasks,
              /factory/heartbeat, /chat, /send
```

The bridge is a wrapper, not a standalone fleet backend. It forwards to a
local "switchboard" service that holds the heartbeats, the shared chat, and
the factory task queue. That switchboard is the builder's existing internal
service and is **not part of this repository** — see "What you must provide"
below. There is no stub or mock switchboard in this repo.

What happens without a switchboard: the bridge still starts, `GET /health`,
the `ping` tool, and both web pages work, but every backend-dependent tool
returns the backend's error/empty result and the dashboard renders empty
defaults instead of live fleet data.

## The 6 MCP tools

| Tool | What it does |
|---|---|
| `ping` | Liveness check — returns `{"pong": true}` and the server time. |
| `list_agents` | Fleet seats with live status, from factory heartbeats + tasks on the backend. |
| `send_message` | Send a message to a fleet agent via the switchboard queue. |
| `read_chat` | Read the shared fleet chat that all agents poll. |
| `heartbeat` | Write a heartbeat for an agent seat (status, current task, message). |
| `factory_tasks` | List the factory task queue: assignees, statuses, deadlines. |

## URDealer (web UI, served by the bridge)

- `/` — Dealer Office: fleet seats with heartbeat states
  (LIVE < 180 s, RECENT < 3600 s, STALE, NO SIGNAL), the factory work queue,
  a "Needs the owner" panel, local service up/down checks, the shared chat,
  and a task composer that really posts new tasks to the factory queue
  (`POST /api/task` → backend `POST /factory/tasks`).
- `/app` — mobile multi-chat: per-agent threads plus an "Everyone" view, one
  composer, 5-second refresh. Shares the office sign-in session.
- Sign-in: first run, the owner sets a password (minimum 8 characters). Only
  its SHA-256 hash is stored, in a local `dashboard_auth.json` file next to
  the server. Sessions last 12 hours and live in server memory.
- Sending: agents on the switchboard roster are delivered through the
  backend queue; agents that are not on the roster are delivered as mailbox
  files in a local `INBOX/` folder, and every sent message is also posted to
  the shared chat for visibility.

## Requirements

- Python 3.11+
- The official MCP Python SDK (`mcp`) — the bridge uses
  `mcp.server.fastmcp.FastMCP` with the Streamable HTTP transport
  (which runs on Starlette/Uvicorn from the SDK's stack)
- Everything else is the Python standard library
  (`urllib`, `socket`, `hashlib`, `secrets`)

Install:

```bash
pip install mcp
```

## What you must provide

1. **A compatible switchboard backend** — a local HTTP service implementing:
   `GET /factory/heartbeats`, `GET /factory/tasks`, `POST /factory/tasks`,
   `POST /factory/heartbeat`, `GET /chat`, `POST /chat`, `POST /send`,
   authenticated with `Authorization: Bearer <token>`.
2. **Your own token file** — a plain text file containing only your
   switchboard token. Point `SWITCHBOARD_TOKEN_PATH` at it. Never commit it.
3. **Optionally, a mailbox directory** — for agents not on the switchboard
   roster, with `INBOX/` and `OUTBOX/` subfolders.

## Run

```bash
# environment (defaults shown)
export SWITCHBOARD_URL="http://127.0.0.1:8380"        # your backend
export SWITCHBOARD_TOKEN_PATH="switchboard_api_token.txt"  # your token file
export AGENT_ORDERS_DIR="agent-orders"                # INBOX/ + OUTBOX/ live here

python mcp_bridge.py
```

Then:

- MCP endpoint: `http://127.0.0.1:8392/mcp` (Streamable HTTP, stateless,
  JSON responses)
- Health check: `GET http://127.0.0.1:8392/health` →
  `{"ok": true, "service": "agent-bridge", "transport": "mcp-streamable-http"}`
- Office: `http://127.0.0.1:8392/` — first visit asks you to set the owner
  password
- Mobile chat: `http://127.0.0.1:8392/app`

## Honest status and limits

- **Verified live, locally, on one workstation (Oct 22, 2026).** This is a
  working local system, not a hosted product. It binds to `127.0.0.1` only.
- **The switchboard backend is not included** (see above). The bridge alone
  demonstrates the MCP surface, the health endpoint, and both UIs.
- **The MCP endpoint itself has no client authentication in this code.** The
  trust model is "localhost only, same machine" — do not expose port 8392 to
  a network without adding your own authentication and transport security.
- **Dashboard sign-in is single-password, demo-grade** (SHA-256 with a static
  prefix, sessions in memory). Fine for one owner on a local machine; not a
  multi-user auth system.
- The service up/down panel in the office probes a fixed list of local ports
  from the builder's own stack (8765, 8380, 8392, 8098, 8111). On your
  machine those extra ports will simply read as down — edit the list in
  `mcp_bridge.py` to match your own services.
- Agent names and "lanes" shown in the UIs are the builder's fleet
  organization, displayed as labels. Rename them in the two HTML files and
  in the `AGENTS` list to match your own fleet.

## Files

| File | Purpose |
|---|---|
| `mcp_bridge.py` | The MCP server + all HTTP routes (bridge, office, mobile app, APIs) |
| `dashboard.html` | URDealer Dealer Office page (served at `/`) |
| `urdealer-app.html` | URDealer mobile multi-chat page (served at `/app`) |
| `SECURITY_NOTES.md` | What was sanitized for publication, and what you must supply yourself |
| `SUBMISSION_FIXES.md` | Corrections required in the hackathon draft text before submitting |
