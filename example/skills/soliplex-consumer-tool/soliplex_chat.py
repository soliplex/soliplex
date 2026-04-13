#!/usr/bin/env python3
"""
Soliplex consumer-tool chat client — stdlib only, no pip required.

Usage:
    python3 soliplex_chat.py \\
        --url http://localhost:8000 \\
        --room chat \\
        --tool secret_number:./secret_number.sh \\
        --tool other_tool:./other.sh

Each --tool argument is  <tool-name>:<path-to-script>.
The script is called with the JSON args string as stdin and its stdout
becomes the tool result.

Multi-tool and multi-turn conversations are fully supported.
Tool calls are transparent to the user — they happen automatically
between runs without any visible turn.
"""

from __future__ import annotations

import argparse
import http.client
import json
import subprocess
import sys
import uuid
import urllib.parse
from typing import Any


# ---------------------------------------------------------------------------
# HTTP helpers (stdlib only — no requests/httpx)
# ---------------------------------------------------------------------------

def _post(url: str, payload: dict) -> str:
    """POST JSON to url, return response body as text."""
    parsed = urllib.parse.urlparse(url)
    host = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    path = parsed.path or "/"
    if parsed.query:
        path += "?" + parsed.query

    body = json.dumps(payload).encode()
    headers = {
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
        "Content-Length": str(len(body)),
    }

    if parsed.scheme == "https":
        import ssl
        conn = http.client.HTTPSConnection(host, port,
                                           context=ssl.create_default_context())
    else:
        conn = http.client.HTTPConnection(host, port)

    try:
        conn.request("POST", path, body=body, headers=headers)
        resp = conn.getresponse()
        return resp.read().decode(errors="replace")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# AG-UI / SSE helpers
# ---------------------------------------------------------------------------

def _parse_sse(text: str) -> list[dict]:
    events = []
    for line in text.splitlines():
        if line.startswith("data: "):
            try:
                events.append(json.loads(line[6:]))
            except json.JSONDecodeError:
                pass
    return events


def _tool_defs(tools: dict[str, str]) -> list[dict]:
    """Build the AG-UI tools array from the {name: script_path} mapping."""
    return [
        {
            "name": name,
            "description": f"Client-side tool '{name}'. Invoke to get its result.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        }
        for name in tools
    ]


# ---------------------------------------------------------------------------
# Soliplex API
# ---------------------------------------------------------------------------

def create_thread(base_url: str, room: str) -> tuple[str, str]:
    """Create a new thread; return (thread_id, initial_run_id)."""
    url = f"{base_url}/api/v1/rooms/{room}/agui"
    data = _post(url, {"metadata": {"name": "consumer-tool session"}})
    d = json.loads(data)
    thread_id = d["thread_id"]
    run_id = next(iter(d["runs"]))
    return thread_id, run_id


def new_run(base_url: str, room: str, thread_id: str) -> str:
    """Create a follow-up run; return the new run_id."""
    url = f"{base_url}/api/v1/rooms/{room}/agui/{thread_id}"
    data = _post(url, {})
    return json.loads(data)["run_id"]


def execute_run(
    base_url: str,
    room: str,
    thread_id: str,
    run_id: str,
    messages: list[dict],
    tool_defs: list[dict],
) -> list[dict]:
    """Execute a run; return parsed SSE events."""
    url = f"{base_url}/api/v1/rooms/{room}/agui/{thread_id}/{run_id}"
    payload = {
        "threadId": thread_id,
        "runId": run_id,
        "state": {},
        "messages": messages,
        "tools": tool_defs,
        "context": [],
        "forwardedProps": {},
    }
    return _parse_sse(_post(url, payload))


# ---------------------------------------------------------------------------
# Event processing
# ---------------------------------------------------------------------------

def _process_events(events: list[dict]) -> dict[str, Any]:
    """
    Scan SSE events and return one of:
      {"kind": "text",       "msg_id": ..., "text": ...}
      {"kind": "tool_calls", "calls": [{id, name, args, parent_msg_id}, ...]}
      {"kind": "error",      "message": ...}
      {"kind": "empty"}
    """
    text = ""
    msg_id = None
    tool_calls: list[dict] = []
    current: dict | None = None

    for ev in events:
        t = ev.get("type", "")

        if t == "TEXT_MESSAGE_START":
            msg_id = ev.get("messageId")
        elif t == "TEXT_MESSAGE_CONTENT":
            text += ev.get("delta", "")

        elif t == "TOOL_CALL_START":
            current = {
                "id":            ev["toolCallId"],
                "name":          ev["toolCallName"],
                "parent_msg_id": ev["parentMessageId"],
                "args":          "",
            }
        elif t == "TOOL_CALL_ARGS" and current:
            current["args"] += ev.get("delta", "")
        elif t == "TOOL_CALL_END" and current:
            tool_calls.append(current)
            current = None

        elif t == "RUN_ERROR":
            return {"kind": "error", "message": ev.get("message", "unknown error")}

    if tool_calls:
        return {"kind": "tool_calls", "calls": tool_calls}
    if text:
        return {"kind": "text", "msg_id": msg_id, "text": text}
    return {"kind": "empty"}


# ---------------------------------------------------------------------------
# Tool execution (calls the shell script)
# ---------------------------------------------------------------------------

def _run_script(script_path: str, args_json: str) -> str:
    """
    Execute a tool script.
    The JSON args string is passed on stdin; stdout is the result.
    """
    try:
        result = subprocess.run(
            [script_path],
            input=args_json,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return f"error: script exited {result.returncode}: {result.stderr.strip()}"
        return result.stdout.strip()
    except FileNotFoundError:
        return f"error: script not found: {script_path}"
    except subprocess.TimeoutExpired:
        return "error: script timed out"


# ---------------------------------------------------------------------------
# Conversation loop
# ---------------------------------------------------------------------------

def conversation_loop(
    base_url: str,
    room: str,
    tools: dict[str, str],       # {name: script_path}
):
    """
    Interactive multi-turn conversation with transparent tool call handling.

    State is the messages list.  Tool calls are invisible to the user —
    the script runs automatically and feeds the result back before the
    user sees any response.
    """
    defs = _tool_defs(tools)
    messages: list[dict] = []
    msg_counter = 0
    run_counter = 0

    # Create the initial thread
    thread_id, run_id = create_thread(base_url, room)

    print(f"Connected to {base_url}/rooms/{room}  (thread {thread_id[:8]}…)")
    if tools:
        print(f"Tools registered: {', '.join(tools)}")
    print("Type 'quit' or Ctrl-D to exit.\n")

    while True:
        # --- get user input ---
        try:
            user_input = input("you: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit"):
            break

        msg_counter += 1
        messages.append({
            "id":      f"user_{msg_counter:03d}",
            "role":    "user",
            "content": user_input,
        })

        # --- inner loop: run until we get a text response ---
        # (tool calls are handled transparently here)
        while True:
            # On the first turn of this user message use the existing run_id;
            # subsequent turns (tool result follow-ups) need a new run.
            if run_counter > 0:
                run_id = new_run(base_url, room, thread_id)
            run_counter += 1

            events = execute_run(
                base_url, room, thread_id, run_id, messages, defs
            )
            result = _process_events(events)

            if result["kind"] == "error":
                print(f"[error] {result['message']}", file=sys.stderr)
                break

            elif result["kind"] == "tool_calls":
                # Execute each tool call, accumulate results, then re-run
                # Build the assistant message that records the tool calls
                asst_tool_calls = []
                tool_result_messages = []
                tr_counter = 0

                for call in result["calls"]:
                    script = tools.get(call["name"])
                    if script is None:
                        tool_output = f"error: unknown tool '{call['name']}'"
                    else:
                        tool_output = _run_script(script, call["args"] or "{}")

                    asst_tool_calls.append({
                        "id":   call["id"],
                        "type": "function",
                        "function": {
                            "name":      call["name"],
                            "arguments": call["args"] or "{}",
                        },
                    })
                    tr_counter += 1
                    tool_result_messages.append({
                        "id":         f"tool_result_{msg_counter:03d}_{tr_counter:02d}",
                        "role":       "tool",
                        "content":    tool_output,
                        "toolCallId": call["id"],
                    })

                # Append assistant msg (with toolCalls) + all tool results
                messages.append({
                    "id":        result["calls"][0]["parent_msg_id"],
                    "role":      "assistant",
                    "content":   None,
                    "toolCalls": asst_tool_calls,
                })
                messages.extend(tool_result_messages)
                # loop again with the tool results injected

            elif result["kind"] == "text":
                print(f"llm: {result['text']}")
                messages.append({
                    "id":      result["msg_id"],
                    "role":    "assistant",
                    "content": result["text"],
                })
                break  # done with this user turn

            else:  # empty
                print("[no response]")
                break


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Soliplex multi-turn chat with client-side tools (stdlib only)"
    )
    parser.add_argument(
        "--url", default="http://localhost:8000",
        help="Soliplex server base URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--room", default="chat",
        help="Room ID to connect to (default: chat)",
    )
    parser.add_argument(
        "--tool", action="append", dest="tools", metavar="NAME:SCRIPT",
        help="Register a client-side tool as  name:path/to/script.sh  "
             "(repeatable, e.g. --tool secret_number:./secret_number.sh)",
    )
    args = parser.parse_args()

    tools: dict[str, str] = {}
    for spec in (args.tools or []):
        if ":" not in spec:
            parser.error(f"--tool must be NAME:SCRIPT, got: {spec!r}")
        name, script = spec.split(":", 1)
        tools[name.strip()] = script.strip()

    conversation_loop(base_url=args.url, room=args.room, tools=tools)


if __name__ == "__main__":
    main()
