"""ABUZ8 Agent Bridge - MCP server (v1, 2026-10-22).

One instant bus for the whole fleet. Any MCP client (OpenClaw/Zait, Hermes/Qadir
and Amanecer, Muse/mcode, Aisha's tooling) connects to this single endpoint
and gets the same tools: ping, list_agents, send_message, read_chat, heartbeat,
factory_tasks. The bridge wraps an existing local "switchboard" backend
(default http://127.0.0.1:8380, override with SWITCHBOARD_URL). The switchboard
token is read server-side from a local file (see SWITCHBOARD_TOKEN_PATH) and
is never sent to MCP clients.

Transport: MCP Streamable HTTP on 127.0.0.1:8392 (localhost only,
same trust pattern as the switchboard). Health: GET /health.
"""
import json
import os
import pathlib
import time
import urllib.request
import urllib.error

from mcp.server.fastmcp import FastMCP

SWITCHBOARD = os.environ.get("SWITCHBOARD_URL", "http://127.0.0.1:8380")
# Path to a local text file containing ONLY your switchboard API token.
# Provide your own file; never commit a real token or token file.
TOKEN_PATH = pathlib.Path(os.environ.get("SWITCHBOARD_TOKEN_PATH", "switchboard_api_token.txt"))

mcp = FastMCP("abuz8-agent-bridge", host="127.0.0.1", port=8392,
              stateless_http=True, json_response=True)


def _token():
    return TOKEN_PATH.read_text(encoding="utf-8").strip()


def _call(method, path, payload=None, cap=60000):
    data = None
    headers = {"Authorization": "Bearer " + _token()}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(SWITCHBOARD + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return {"ok": True, "status": r.status, "body": r.read().decode("utf-8", "replace")[:cap]}
    except urllib.error.HTTPError as e:
        return {"ok": False, "status": e.code, "body": e.read().decode("utf-8", "replace")[:1000]}
    except Exception as e:
        return {"ok": False, "status": -1, "body": repr(e)}


@mcp.tool()
def ping() -> dict:
    """Liveness check for the agent bridge. Returns pong and the server time."""
    return {"pong": True, "at": time.strftime("%Y-%m-%dT%H:%M:%S")}


@mcp.tool()
def list_agents() -> dict:
    """List fleet seats with live status computed from factory heartbeats and tasks."""
    beats = _call("GET", "/factory/heartbeats")
    tasks = _call("GET", "/factory/tasks")
    return {"heartbeats": beats.get("body", ""), "tasks": tasks.get("body", "")}


@mcp.tool()
def send_message(to_agent: str, text: str, from_agent: str = "aisha") -> dict:
    """Send a message to a fleet agent (zait, qadir, amanecer, soloman) via the switchboard queue."""
    return _call("POST", "/send", {"agent": to_agent, "channel": from_agent, "text": text})


@mcp.tool()
def read_chat(limit: int = 20) -> dict:
    """Read the shared fleet chat (the switchboard chat store all agents poll)."""
    res = _call("GET", "/chat")
    return res


@mcp.tool()
def heartbeat(agent: str, status: str, current_task: str = "", message: str = "") -> dict:
    """Write a heartbeat for an agent seat so the fleet can see it is alive and what it is doing."""
    payload = {"agent": agent, "status": status, "current_task": current_task, "message": message}
    return _call("POST", "/factory/heartbeat", payload)


@mcp.tool()
def factory_tasks() -> dict:
    """List factory tasks (the fleet work queue: assignees, statuses, deadlines)."""
    return _call("GET", "/factory/tasks")


@mcp.custom_route("/health", methods=["GET"])
async def health(request):
    from starlette.responses import JSONResponse
    return JSONResponse({"ok": True, "service": "agent-bridge", "transport": "mcp-streamable-http"})


import hashlib
import os
import secrets
import socket

HERE = pathlib.Path(__file__).resolve().parent
DASH_HTML_PATH = HERE / "dashboard.html"
AUTH_PATH = HERE / "dashboard_auth.json"
# Directory holding INBOX/ and OUTBOX/ mailbox folders used for agents that
# are not on the switchboard roster. Provide your own; see README.
ORDERS_DIR = pathlib.Path(os.environ.get("AGENT_ORDERS_DIR", "agent-orders"))
_sessions = {}


def _pw_hash(pw):
    return hashlib.sha256(("abuz8-fleet-command::" + pw).encode("utf-8")).hexdigest()


def _new_session():
    tok = secrets.token_urlsafe(32)
    _sessions[tok] = time.time() + 12 * 3600
    return tok


def _session_ok(request):
    tok = request.headers.get("x-session", "")
    exp = _sessions.get(tok)
    return bool(exp and exp > time.time())


def _svc_up(port):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1.2):
            return True
    except Exception:
        return False


def _mailbox_state():
    out = {"latest_outbox": None, "mcp_connected": [], "mcp_pending": []}
    try:
        ob = ORDERS_DIR / "OUTBOX"
        files = sorted(ob.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if files:
            f0 = files[0]
            out["latest_outbox"] = f0.name + " · " + time.strftime("%H:%M", time.localtime(f0.stat().st_mtime))
        connected = set()
        for f in ob.glob("*_mcp_connected_*.json"):
            connected.add(f.name.split("_mcp_connected_")[0].lower())
        out["mcp_connected"] = sorted(connected)
        out["mcp_pending"] = [a for a in ("zait", "qadir", "amanecer", "mcode") if a not in connected]
    except Exception:
        pass
    return out


@mcp.custom_route("/", methods=["GET"])
async def dash_root(request):
    from starlette.responses import HTMLResponse
    return HTMLResponse(DASH_HTML_PATH.read_text(encoding="utf-8"))


@mcp.custom_route("/api/authstate", methods=["GET"])
async def dash_authstate(request):
    from starlette.responses import JSONResponse
    return JSONResponse({"needs_setup": not AUTH_PATH.exists()})


@mcp.custom_route("/api/setup", methods=["POST"])
async def dash_setup(request):
    from starlette.responses import JSONResponse
    if AUTH_PATH.exists():
        return JSONResponse({"ok": False, "error": "password already set"}, status_code=409)
    body = await request.json()
    pw = (body.get("password") or "")
    if len(pw) < 8:
        return JSONResponse({"ok": False, "error": "password too short"}, status_code=400)
    AUTH_PATH.write_text(json.dumps({"sha256": _pw_hash(pw)}), encoding="utf-8")
    return JSONResponse({"ok": True, "session": _new_session()})


@mcp.custom_route("/api/login", methods=["POST"])
async def dash_login(request):
    from starlette.responses import JSONResponse
    if not AUTH_PATH.exists():
        return JSONResponse({"ok": False, "error": "setup required"}, status_code=409)
    body = await request.json()
    saved = json.loads(AUTH_PATH.read_text(encoding="utf-8")).get("sha256", "")
    if secrets.compare_digest(_pw_hash(body.get("password") or ""), saved):
        return JSONResponse({"ok": True, "session": _new_session()})
    return JSONResponse({"ok": False, "error": "wrong password"}, status_code=401)


@mcp.custom_route("/api/logout", methods=["POST"])
async def dash_logout(request):
    from starlette.responses import JSONResponse
    _sessions.pop(request.headers.get("x-session", ""), None)
    return JSONResponse({"ok": True})


@mcp.custom_route("/api/state", methods=["GET"])
async def dash_state(request):
    from starlette.responses import JSONResponse
    if not _session_ok(request):
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)
    beats = _call("GET", "/factory/heartbeats")
    tasks = _call("GET", "/factory/tasks")
    chat = _call("GET", "/chat")
    def parse(res, key):
        try:
            return json.loads(res.get("body", "{}")).get(key, {} if key != "tasks" else [])
        except Exception:
            return {} if key != "tasks" else []
    state = {
        "heartbeats": parse(beats, "heartbeats"),
        "tasks": parse(tasks, "tasks"),
        "chat": parse(chat, "chat") if isinstance(parse(chat, "chat"), list) else [],
        "services": [
            {"name": "bridge", "port": 8765, "up": _svc_up(8765)},
            {"name": "switchboard", "port": 8380, "up": _svc_up(8380)},
            {"name": "agent-bridge", "port": 8392, "up": True},
            {"name": "brain", "port": 8098, "up": _svc_up(8098)},
            {"name": "ornith", "port": 8111, "up": _svc_up(8111)},
        ],
    }
    state.update(_mailbox_state())
    return JSONResponse(state)


@mcp.custom_route("/app", methods=["GET"])
async def dash_app(request):
    from starlette.responses import HTMLResponse
    return HTMLResponse((HERE / "urdealer-app.html").read_text(encoding="utf-8"))


@mcp.custom_route("/api/send", methods=["POST"])
async def dash_send(request):
    from starlette.responses import JSONResponse
    if not _session_ok(request):
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)
    body = await request.json()
    agent = (body.get("agent") or "").strip().lower()
    text = (body.get("text") or "").strip()
    sender = body.get("from", "owner")
    if not agent or not text:
        return JSONResponse({"ok": False, "error": "agent and text required"}, status_code=400)
    roster = ("zait", "qadir", "amanecer", "soloman")
    if agent in roster:
        res = _call("POST", "/send", {"agent": agent, "channel": sender, "text": text})
        mode = "queue"
        ok = res.get("ok")
    else:
        # Aisha / Asred / mcode live on the mailbox bus, not the switchboard roster.
        stamp = time.strftime("%Y%m%dT%H%M%S")
        note = {"from": "owner (URDealer)", "to": agent, "text": text,
                "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
        path = ORDERS_DIR / "INBOX" / ("urdealer_to_" + agent + "_" + stamp + ".json")
        try:
            path.write_text(json.dumps(note, indent=2), encoding="utf-8")
            ok, mode = True, "mailbox"
        except Exception as e:
            return JSONResponse({"ok": False, "error": repr(e)}, status_code=502)
    if ok:
        # Board visibility: every sent message also lands on the shared chat.
        _call("POST", "/chat", {"from": sender, "message": "@" + agent + " " + text})
        return JSONResponse({"ok": True, "mode": mode})
    return JSONResponse({"ok": False, "error": "delivery failed", "mode": mode}, status_code=502)


@mcp.custom_route("/api/task", methods=["POST"])
async def dash_task(request):
    from starlette.responses import JSONResponse
    if not _session_ok(request):
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)
    body = await request.json()
    title = (body.get("title") or "").strip()
    if not title:
        return JSONResponse({"ok": False, "error": "title required"}, status_code=400)
    res = _call("POST", "/factory/tasks", {
        "title": title,
        "objective": body.get("objective", ""),
        "assigned_to": body.get("assigned_to", ""),
        "created_by": "fleet-command",
    })
    try:
        out = json.loads(res.get("body", "{}"))
    except Exception:
        out = {"ok": False, "error": "switchboard unreachable"}
    return JSONResponse(out, status_code=200 if out.get("ok") else 502)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
