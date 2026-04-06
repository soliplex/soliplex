"""
Hermes Event Server — M1

Wraps Hermes AIAgent in a FastAPI app that emits structured SSE events.
Bridges AIAgent's sync callbacks to async SSE via asyncio.Queue + ThreadPoolExecutor.

Event schema:
  {"type":"run_started","run_id":"..."}
  {"type":"thinking","content":"..."}
  {"type":"text_delta","delta":"...","message_id":"msg_1"}
  {"type":"tool_start","tool_call_id":"call_abc","name":"web_search","args":{...}}
  {"type":"tool_result","tool_call_id":"call_abc","content":"..."}
  {"type":"run_finished","usage":{...}}
  {"type":"run_error","message":"..."}
"""

import asyncio
import json
import logging
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("hermes_event_server")

# Load Hermes .env from HERMES_HOME (mounted volume) — must happen before any imports
from dotenv import load_dotenv
_hermes_home = os.environ.get("HERMES_HOME", os.path.expanduser("~/.hermes"))
_env_path = os.path.join(_hermes_home, ".env")
if os.path.exists(_env_path):
    load_dotenv(_env_path, override=True)
    logger.info("Loaded env from %s", _env_path)
    logger.info("MINIMAX_API_KEY=%s...", os.environ.get("MINIMAX_API_KEY", "NOT SET")[:15])
    logger.info("TAVILY_API_KEY=%s...", os.environ.get("TAVILY_API_KEY", "NOT SET")[:15])

# Signal to Hermes tools that we're in an interactive/gateway context
# and force local terminal (no Docker-in-Docker inside the container)
os.environ["HERMES_INTERACTIVE"] = "1"
os.environ["HERMES_GATEWAY_SESSION"] = "1"
# Don't override TERMINAL_ENV if .env already set it — AIAgent reloads .env
# Only set if not present at all (bare container with no .env)
if not os.environ.get("TERMINAL_ENV"):
    _terminal_env = "daytona" if os.environ.get("DAYTONA_API_KEY") else "local"
    os.environ["TERMINAL_ENV"] = _terminal_env
logger.info("TERMINAL_ENV=%s (DAYTONA_API_KEY=%s)",
            os.environ.get("TERMINAL_ENV", "not set"),
            "set" if os.environ.get("DAYTONA_API_KEY") else "not set")

# Import model_tools early to populate the tool registry (tools self-register on import)
import model_tools as _mt  # noqa: E402

# Register Soliplex integration tools in Hermes registry
from tools.registry import registry as _registry


def _soliplex_list_rooms(**kwargs) -> str:
    """List available Soliplex rooms."""
    import json as _json
    import requests as _requests
    soliplex_url = os.environ.get("SOLIPLEX_URL", "http://host.docker.internal:8000/api")
    try:
        r = _requests.get(f"{soliplex_url}/v1/rooms", timeout=10)
        rooms = r.json()
        lines = []
        for room_id, room_data in rooms.items():
            if isinstance(room_data, dict):
                name = room_data.get("name", room_id)
                desc = room_data.get("description", "")
                kind = room_data.get("agent", {}).get("kind", "default")
                tools = list(room_data.get("tools", {}).keys())
                line = f"- {room_id} [{kind}]: {name} — {desc}"
                if tools:
                    line += f"\n  tools: {', '.join(tools[:5])}"
                lines.append(line)
        return "\n".join(lines) or "No rooms found."
    except Exception as e:
        return _json.dumps({"error": str(e)})


def _soliplex_ask_room(room_id: str = "", message: str = "", **kwargs) -> str:
    """Send a message to another Soliplex room and get the response."""
    import json as _json
    import uuid as _uuid
    import requests as _requests
    soliplex_url = os.environ.get("SOLIPLEX_URL", "http://host.docker.internal:8000/api")
    try:
        # Create thread
        r = _requests.post(f"{soliplex_url}/v1/rooms/{room_id}/agui", json={}, timeout=10)
        if r.status_code != 200:
            return f"Error: Cannot access room '{room_id}' (HTTP {r.status_code})"
        data = r.json()
        tid = data["thread_id"]
        rid = list(data["runs"].keys())[0]

        # Send run
        body = {
            "threadId": tid, "runId": rid, "state": {},
            "messages": [{"id": str(_uuid.uuid4()), "role": "user", "content": message}],
            "tools": [], "context": [], "forwardedProps": {},
        }
        r = _requests.post(
            f"{soliplex_url}/v1/rooms/{room_id}/agui/{tid}/{rid}",
            json=body, stream=True, timeout=120,
        )

        # Collect text from SSE
        text_parts = []
        tool_calls = []
        for raw_line in r.iter_lines():
            line = raw_line.decode("utf-8") if isinstance(raw_line, bytes) else raw_line
            if not line or not line.startswith("data:"):
                continue
            d = line[6:].strip()
            if d == "[DONE]":
                break
            try:
                event = _json.loads(d)
                etype = event.get("type", "")
                if "TEXT_MESSAGE_CONTENT" in etype:
                    text_parts.append(event.get("delta", ""))
                elif "TOOL_CALL_START" in etype:
                    tool_calls.append(event.get("toolCallName", ""))
            except _json.JSONDecodeError:
                pass

        result = "".join(text_parts)
        if tool_calls:
            result += f"\n[Room '{room_id}' used: {', '.join(tool_calls)}]"
        return result or f"Room '{room_id}' returned no response."
    except Exception as e:
        return _json.dumps({"error": str(e)})


_registry.register(
    name="soliplex_list_rooms",
    toolset="soliplex",
    schema={
        "name": "soliplex_list_rooms",
        "description": "List all available Soliplex rooms with their names, descriptions, and tools. Use this to discover what rooms exist.",
        "parameters": {"type": "object", "properties": {}},
    },
    handler=lambda args, **kw: _soliplex_list_rooms(**args, **kw),
)

_registry.register(
    name="soliplex_ask_room",
    toolset="soliplex",
    schema={
        "name": "soliplex_ask_room",
        "description": "Send a message to another Soliplex room's agent and get the response. Each room has its own agent and tools.",
        "parameters": {
            "type": "object",
            "properties": {
                "room_id": {"type": "string", "description": "Target room ID (e.g. 'plain', 'search', 'chat')"},
                "message": {"type": "string", "description": "Message to send to the room's agent"},
            },
            "required": ["room_id", "message"],
        },
    },
    handler=lambda args, **kw: _soliplex_ask_room(**args, **kw),
)

app = FastAPI(title="Hermes Event Server", version="0.1.0")

# Shared thread pool for agent execution
_executor = ThreadPoolExecutor(max_workers=4)


# ---------------------------------------------------------------------------
# Request / config models
# ---------------------------------------------------------------------------

class AgentConfig(BaseModel):
    model: Optional[str] = None
    enabled_toolsets: Optional[list[str]] = None
    disabled_toolsets: Optional[list[str]] = None
    max_iterations: int = 10
    system_prompt: Optional[str] = None


class ClientTool(BaseModel):
    """A tool defined by the AG-UI client (Flutter) for callback execution."""
    name: str
    description: str = ""
    parameters: dict = Field(default_factory=dict)


class RunRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    history: Optional[list[dict]] = None
    config: AgentConfig = Field(default_factory=AgentConfig)
    client_tools: Optional[list[ClientTool]] = None


# ---------------------------------------------------------------------------
# SSE helpers
# ---------------------------------------------------------------------------

def _sse_line(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


# ---------------------------------------------------------------------------
# Core: run agent, bridge callbacks to queue
# ---------------------------------------------------------------------------

def _run_agent_blocking(
    request: RunRequest,
    queue: asyncio.Queue,
    loop: asyncio.AbstractEventLoop,
) -> dict:
    """Run AIAgent synchronously in a thread. Push structured events into queue."""

    from run_agent import AIAgent

    logger.info("Agent thread: TERMINAL_ENV=%s DAYTONA_API_KEY=%s",
                os.environ.get("TERMINAL_ENV", "NOT SET"),
                "set" if os.environ.get("DAYTONA_API_KEY") else "NOT SET")

    # Debug: check which tools pass check_fn
    from tools.registry import registry as _dbg_reg
    for _tn in ["terminal", "process", "read_file", "write_file"]:
        _entry = _dbg_reg._tools.get(_tn)
        if _entry and _entry.check_fn:
            try:
                _ok = _entry.check_fn()
            except Exception as _e:
                _ok = f"error: {_e}"
            logger.info("  tool %s check_fn=%s", _tn, _ok)
        elif _entry:
            logger.info("  tool %s no check_fn", _tn)
        else:
            logger.info("  tool %s NOT IN REGISTRY", _tn)

    run_id = str(uuid.uuid4())
    msg_counter = {"n": 0}
    current_msg = {"id": None}

    def _put(event: dict):
        loop.call_soon_threadsafe(queue.put_nowait, event)

    # --- callbacks ---

    def on_stream_delta(delta):
        if delta is None:
            # Signal: text segment ended, tools coming next
            if current_msg["id"] is not None:
                _put({"type": "text_end", "message_id": current_msg["id"]})
                current_msg["id"] = None
            return
        # Start new text segment if needed
        if current_msg["id"] is None:
            msg_counter["n"] += 1
            current_msg["id"] = f"msg_{msg_counter['n']}"
            _put({"type": "text_start", "message_id": current_msg["id"]})
        _put({"type": "text_delta", "delta": delta, "message_id": current_msg["id"]})

    def on_tool_start(tool_call_id, name, args):
        # Close any open text segment
        if current_msg["id"] is not None:
            _put({"type": "text_end", "message_id": current_msg["id"]})
            current_msg["id"] = None
        _put({
            "type": "tool_start",
            "tool_call_id": tool_call_id,
            "name": name,
            "args": args if isinstance(args, dict) else {},
        })

    def on_tool_complete(tool_call_id, name, args, result):
        _put({
            "type": "tool_result",
            "tool_call_id": tool_call_id,
            "name": name,
            "content": result if isinstance(result, str) else str(result),
        })

    def on_thinking(content):
        if content:  # Non-empty = thinking started/updated
            _put({"type": "thinking", "content": content})
        else:  # Empty = thinking cleared (first token arrived)
            _put({"type": "thinking_end"})

    def on_reasoning(content):
        if content:
            _put({"type": "reasoning_delta", "delta": content})

    def on_step(api_call_count, prev_tools):
        _put({
            "type": "step",
            "iteration": api_call_count,
            "max_iterations": request.config.max_iterations,
            "prev_tools": prev_tools if isinstance(prev_tools, list) else [],
        })

    def on_status(status_type, message):
        _put({"type": "status", "status_type": status_type, "message": message})

    # --- build agent ---

    cfg = request.config
    agent_kwargs = {
        "model": cfg.model or os.environ.get("HERMES_MODEL", "MiniMax-M2.7"),
        "max_iterations": cfg.max_iterations,
        "quiet_mode": True,
        "verbose_logging": False,
        "skip_context_files": True,
        "platform": "soliplex",
        "stream_delta_callback": on_stream_delta,
        "tool_start_callback": on_tool_start,
        "tool_complete_callback": on_tool_complete,
        "thinking_callback": on_thinking,
        "reasoning_callback": on_reasoning,
        "step_callback": on_step,
        "status_callback": on_status,
    }

    if cfg.enabled_toolsets is not None:
        agent_kwargs["enabled_toolsets"] = cfg.enabled_toolsets
    if cfg.disabled_toolsets is not None:
        agent_kwargs["disabled_toolsets"] = cfg.disabled_toolsets
    if cfg.system_prompt:
        agent_kwargs["ephemeral_system_prompt"] = cfg.system_prompt
    if request.session_id:
        agent_kwargs["session_id"] = request.session_id

    # Load credentials from auth.json credential pool
    _auth_path = os.path.join(_hermes_home, "auth.json")
    if os.path.exists(_auth_path):
        import json as _json
        _auth = _json.load(open(_auth_path))
        _pool = _auth.get("credential_pool", {})
        # Find first usable credential (not exhausted)
        for _provider_name, _creds in _pool.items():
            for _cred in _creds:
                if _cred.get("last_status") == "exhausted":
                    continue
                if _cred.get("access_token") and _cred.get("base_url"):
                    agent_kwargs["api_key"] = _cred["access_token"]
                    agent_kwargs["base_url"] = _cred["base_url"]
                    # Use anthropic_messages mode for /anthropic endpoints
                    if "/anthropic" in _cred["base_url"]:
                        agent_kwargs["api_mode"] = "anthropic_messages"
                    break
            if "api_key" in agent_kwargs:
                break

    # Emit run_started
    _put({"type": "run_started", "run_id": run_id})

    try:
        agent = AIAgent(**agent_kwargs)

        # --- Client tool injection ---
        # Register client-side tools (from AG-UI RunAgentInput.tools)
        # These tools trigger an interrupt when called, yielding control
        # back to the client via the multi-run AG-UI protocol.
        client_tool_names = set()
        if request.client_tools:
            from tools.registry import registry
            import threading

            for ct in request.client_tools:
                client_tool_names.add(ct.name)

                def _make_handler(tool_name, _agent=agent):
                    def handler(args=None, **kwargs):
                        _agent.interrupt(f"client_tool:{tool_name}")
                        return json.dumps({
                            "awaiting_client": True,
                            "tool": tool_name,
                            "args": args or {},
                        })
                    return handler

                registry.register(
                    name=ct.name,
                    toolset="agui_client",
                    schema={
                        "name": ct.name,
                        "description": ct.description,
                        "parameters": ct.parameters or {
                            "type": "object", "properties": {}
                        },
                    },
                    handler=_make_handler(ct.name),
                )

                # Append schema to agent's tool list so LLM sees it
                agent.tools.append({
                    "type": "function",
                    "function": {
                        "name": ct.name,
                        "description": ct.description,
                        "parameters": ct.parameters or {
                            "type": "object", "properties": {}
                        },
                    },
                })
                if hasattr(agent, 'valid_tool_names') and agent.valid_tool_names:
                    agent.valid_tool_names.add(ct.name)

        # Use session_id as task_id so Daytona reuses sandboxes across runs
        effective_task_id = request.session_id or "default"

        result = agent.run_conversation(
            user_message=request.message,
            conversation_history=request.history or [],
            task_id=effective_task_id,
        )

        # Close any open text segment
        if current_msg["id"] is not None:
            _put({"type": "text_end", "message_id": current_msg["id"]})
            current_msg["id"] = None

        # Emit run_finished with usage
        _put({
            "type": "run_finished",
            "run_id": run_id,
            "usage": {
                "input_tokens": result.get("input_tokens", 0),
                "output_tokens": result.get("output_tokens", 0),
                "total_tokens": result.get("total_tokens", 0),
                "cache_read_tokens": result.get("cache_read_tokens", 0),
                "reasoning_tokens": result.get("reasoning_tokens", 0),
            },
            "session_id": getattr(agent, "session_id", request.session_id),
            "client_tool_names": sorted(client_tool_names) if client_tool_names else [],
        })

        return result

    except Exception as e:
        logger.exception("Agent error")
        _put({
            "type": "run_error",
            "run_id": run_id,
            "message": str(e),
        })
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post("/v1/agent/run")
async def agent_run(request: RunRequest):
    """Run Hermes agent, stream structured SSE events."""

    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_running_loop()

    async def event_stream():
        # Launch agent in thread pool
        future = loop.run_in_executor(
            _executor,
            _run_agent_blocking,
            request,
            queue,
            loop,
        )

        # Stream events from queue
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                # Check if agent finished without more events
                if future.done():
                    # Drain remaining
                    while not queue.empty():
                        event = queue.get_nowait()
                        yield _sse_line(event)
                    break
                # Send keepalive
                yield ": keepalive\n\n"
                continue

            yield _sse_line(event)

            # Stop after terminal events
            if event.get("type") in ("run_finished", "run_error"):
                break

        yield "data: [DONE]\n\n"

        # Ensure thread completes (propagate exceptions)
        try:
            await asyncio.wrap_future(future)
        except Exception:
            pass

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/health")
async def health():
    return {"status": "ok", "service": "hermes-event-server"}


class ToolCallRequest(BaseModel):
    """Single tool dispatch — no agent loop."""
    tool: str
    args: dict = Field(default_factory=dict)


@app.post("/v1/agent/tool")
async def call_tool(request: ToolCallRequest):
    """Execute a single Hermes tool without the agent loop."""
    from tools.registry import registry
    import time

    entry = registry._tools.get(request.tool)
    if not entry:
        return {"error": f"Unknown tool: {request.tool}", "available_tools": sorted(registry._tools.keys())}

    if entry.check_fn:
        try:
            if not entry.check_fn():
                return {"error": f"Tool '{request.tool}' is not available (failed check)"}
        except Exception:
            return {"error": f"Tool '{request.tool}' availability check failed"}

    start = time.time()
    try:
        result = registry.dispatch(request.tool, request.args)
        duration_ms = int((time.time() - start) * 1000)
        return {"result": result, "tool": request.tool, "duration_ms": duration_ms}
    except Exception as e:
        duration_ms = int((time.time() - start) * 1000)
        return {"error": str(e), "tool": request.tool, "duration_ms": duration_ms}


@app.get("/v1/agent/tools")
async def list_tools():
    """List all tools with availability status per toolset."""
    from tools.registry import registry

    tool_map = registry.get_tool_to_toolset_map()
    toolsets = {}

    for name, entry in sorted(registry._tools.items()):
        ts = entry.toolset
        available = True
        if entry.check_fn:
            try:
                available = bool(entry.check_fn())
            except Exception:
                available = False

        toolsets.setdefault(ts, {"tools": [], "available": True})
        toolsets[ts]["tools"].append({
            "name": name,
            "available": available,
            "description": entry.description or "",
        })
        if not available:
            toolsets[ts]["available"] = False

    return {
        "toolsets": {
            ts: {
                "available": info["available"],
                "tool_count": len(info["tools"]),
                "tools": info["tools"],
            }
            for ts, info in sorted(toolsets.items())
        },
        "summary": {
            "total_tools": sum(len(i["tools"]) for i in toolsets.values()),
            "available_tools": sum(
                1 for i in toolsets.values()
                for t in i["tools"] if t["available"]
            ),
            "available_toolsets": [
                ts for ts, i in toolsets.items() if i["available"]
            ],
            "gated_toolsets": [
                ts for ts, i in toolsets.items() if not i["available"]
            ],
        },
    }


@app.get("/v1/agent/memory")
async def get_memory():
    """Return Hermes agent memory and user profile."""
    from pathlib import Path

    mem_dir = Path(_hermes_home) / "memories"
    result = {}

    for name in ("MEMORY.md", "USER.md"):
        path = mem_dir / name
        if path.exists():
            content = path.read_text().strip()
            entries = [
                line.strip().lstrip("- ")
                for line in content.splitlines()
                if line.strip() and not line.startswith("#")
            ]
            result[name.replace(".md", "").lower()] = {
                "raw": content,
                "entries": entries,
            }
        else:
            result[name.replace(".md", "").lower()] = {
                "raw": "",
                "entries": [],
            }

    return result


@app.get("/v1/agent/skills")
async def list_skills():
    """Return available Hermes skills from the volume."""
    from pathlib import Path
    import yaml

    skills_dir = Path(_hermes_home) / "skills"
    skills = []

    if skills_dir.is_dir():
        for skill_md in skills_dir.rglob("SKILL.md"):
            try:
                content = skill_md.read_text()
                if not content.startswith("---"):
                    continue
                parts = content.split("---", 2)
                if len(parts) < 3:
                    continue
                fm = yaml.safe_load(parts[1])
                if not isinstance(fm, dict):
                    continue

                tags = []
                meta = fm.get("metadata", {})
                if isinstance(meta, dict):
                    hermes_meta = meta.get("hermes", {})
                    if isinstance(hermes_meta, dict):
                        tags = hermes_meta.get("tags", [])

                skills.append({
                    "name": fm.get("name", skill_md.parent.name),
                    "description": fm.get("description", ""),
                    "version": fm.get("version"),
                    "author": fm.get("author"),
                    "tags": tags,
                    "path": str(skill_md.parent.relative_to(skills_dir)),
                })
            except Exception:
                continue

    return {
        "count": len(skills),
        "skills": sorted(skills, key=lambda s: s["name"]),
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("HERMES_EVENT_SERVER_PORT", "8642"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
