#!/usr/bin/env python3
"""
Soliplex consumer-tool chat client — stdlib only, no pip required.

Interactive REPL:
    python3 soliplex_chat.py \\
        --url  http://localhost:8000 \\
        --room chat \\
        --tool secret_number:./secret_number.sh

One-shot (non-interactive):
    python3 soliplex_chat.py \\
        --url  http://localhost:8000 \\
        --room chat \\
        --tool secret_number:./secret_number.sh \\
        --message "what is the secret number"

Each --tool argument is  <tool-name>:<path-to-script>.
The script receives the JSON args string on stdin; stdout becomes the tool result.

Multi-tool and multi-turn conversations are fully supported.
Tool calls are transparent — they happen automatically without any visible turn.
"""

from __future__ import annotations

import argparse
import http.client
import json
import subprocess
import sys
import time
import urllib.parse
from typing import Any


# ---------------------------------------------------------------------------
# HTTP helpers (stdlib only — no requests/httpx)
# ---------------------------------------------------------------------------

def _post(url: str, payload: dict, *, accept: str = "application/json") -> str:
    """POST JSON to url, return response body as text."""
    parsed = urllib.parse.urlparse(url)
    host = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    path = parsed.path or "/"
    if parsed.query:
        path += "?" + parsed.query

    body = json.dumps(payload).encode()
    headers = {
        "Content-Type":  "application/json",
        "Accept":        accept,
        "Content-Length": str(len(body)),
        "Connection":    "close",   # avoid keep-alive state bleeding between calls
    }

    if parsed.scheme == "https":
        import ssl
        conn = http.client.HTTPSConnection(host, port,
                                           context=ssl.create_default_context())
    else:
        conn = http.client.HTTPConnection(host, port)

    try:
        conn.request("POST", path, body=body, headers=headers)
        return conn.getresponse().read().decode(errors="replace")
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


def _process_events(events: list[dict]) -> dict[str, Any]:
    """
    Scan SSE events and return one of:
      {"kind": "text",       "msg_id": str, "text": str}
      {"kind": "tool_calls", "calls": [{id, name, args, parent_msg_id}, ...]}
      {"kind": "error",      "message": str}
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
# Soliplex API
# ---------------------------------------------------------------------------

def create_thread(base_url: str, room: str) -> tuple[str, str]:
    """Create a new thread; return (thread_id, initial_run_id)."""
    data = _post(f"{base_url}/api/v1/rooms/{room}/agui",
                 {"metadata": {"name": "consumer-tool session"}})
    d = json.loads(data)
    return d["thread_id"], next(iter(d["runs"]))


def new_run(base_url: str, room: str, thread_id: str) -> str:
    """Create a follow-up run; return the new run_id.

    Retries on failure: the server persists run events in a background task,
    so calling new_run immediately after an SSE response can race with that
    task and return a 500.  A short exponential backoff resolves it.
    """
    for attempt in range(6):
        data = _post(f"{base_url}/api/v1/rooms/{room}/agui/{thread_id}", {})
        try:
            return json.loads(data)["run_id"]
        except (json.JSONDecodeError, KeyError):
            if attempt < 5:
                time.sleep(0.1 * (2 ** attempt))   # 0.1, 0.2, 0.4, 0.8, 1.6 s
            else:
                raise RuntimeError(f"new_run failed after retries: {data!r}")


def execute_run(
    base_url: str,
    room: str,
    thread_id: str,
    run_id: str,
    messages: list[dict],
    tool_defs: list[dict],
) -> list[dict]:
    """Execute a run; return parsed SSE events."""
    return _parse_sse(_post(
        f"{base_url}/api/v1/rooms/{room}/agui/{thread_id}/{run_id}",
        {
            "threadId":       thread_id,
            "runId":          run_id,
            "state":          {},
            "messages":       messages,
            "tools":          tool_defs,
            "context":        [],
            "forwardedProps": {},
        },
        accept="text/event-stream",
    ))


# ---------------------------------------------------------------------------
# Tool execution
# ---------------------------------------------------------------------------

def _run_script(script_path: str, args_json: str) -> str:
    """Run a tool script; stdin = JSON args, stdout = result."""
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
# Inner loop: run until text response (handles chained tool calls)
# ---------------------------------------------------------------------------

def _send_turn(
    base_url: str,
    room: str,
    thread_id: str,
    initial_run_id: str,
    messages: list[dict],
    tools: dict[str, str],
    run_counter: int,
) -> tuple[str, int]:
    """
    Execute runs until the LLM produces a text response.

    Tool calls are handled transparently: the script runs, results are
    appended to messages[], and the loop continues without any output.

    Returns (response_text, updated_run_counter).
    """
    defs = _tool_defs(tools)
    run_id = initial_run_id

    while True:
        if run_counter > 0:
            run_id = new_run(base_url, room, thread_id)
        run_counter += 1

        result = _process_events(
            execute_run(base_url, room, thread_id, run_id, messages, defs)
        )

        if result["kind"] == "error":
            return f"[error] {result['message']}", run_counter

        elif result["kind"] == "tool_calls":
            asst_tool_calls = []
            tool_result_msgs = []
            for i, call in enumerate(result["calls"], 1):
                script = tools.get(call["name"])
                output = (
                    _run_script(script, call["args"] or "{}")
                    if script is not None
                    else f"error: unknown tool '{call['name']}'"
                )
                asst_tool_calls.append({
                    "id":   call["id"],
                    "type": "function",
                    "function": {
                        "name":      call["name"],
                        "arguments": call["args"] or "{}",
                    },
                })
                tool_result_msgs.append({
                    "id":         f"tool_result_{run_counter:03d}_{i:02d}",
                    "role":       "tool",
                    "content":    output,
                    "toolCallId": call["id"],
                })
            messages.append({
                "id":        result["calls"][0]["parent_msg_id"],
                "role":      "assistant",
                "content":   None,
                "toolCalls": asst_tool_calls,
            })
            messages.extend(tool_result_msgs)
            # loop — re-run with tool results injected

        elif result["kind"] == "text":
            messages.append({
                "id":      result["msg_id"],
                "role":    "assistant",
                "content": result["text"],
            })
            return result["text"], run_counter

        else:
            return "[no response]", run_counter


# ---------------------------------------------------------------------------
# Conversation loop (REPL or one-shot)
# ---------------------------------------------------------------------------

def conversation_loop(
    base_url: str,
    room: str,
    tools: dict[str, str],
    initial_message: str | None = None,
) -> None:
    """
    Multi-turn conversation with transparent tool call handling.

    initial_message: if set, send it, print the response, and return
                     (one-shot / non-interactive mode).
                     If None, run an interactive REPL.
    """
    messages: list[dict] = []
    msg_counter = 0
    run_counter = 0

    thread_id, run_id = create_thread(base_url, room)

    if not initial_message:
        print(f"Connected to {base_url}/rooms/{room}  (thread {thread_id[:8]}…)")
        if tools:
            print(f"Tools registered: {', '.join(tools)}")
        print("Type 'quit' or Ctrl-D to exit.\n")

    def _turn(user_input: str) -> None:
        nonlocal msg_counter, run_counter
        msg_counter += 1
        messages.append({
            "id":      f"user_{msg_counter:03d}",
            "role":    "user",
            "content": user_input,
        })
        response, run_counter = _send_turn(
            base_url, room, thread_id, run_id,
            messages, tools, run_counter,
        )
        print(response if initial_message else f"llm: {response}")

    if initial_message:
        _turn(initial_message)
        return

    while True:
        try:
            user_input = input("you: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit"):
            break
        _turn(user_input)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Soliplex multi-turn chat with client-side tools (stdlib only)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  # interactive REPL
  python3 soliplex_chat.py --tool secret_number:./secret_number.sh

  # one-shot
  python3 soliplex_chat.py --message "what is the secret number" \\
      --tool secret_number:./secret_number.sh
        """,
    )
    parser.add_argument("--url",  default="http://localhost:8000",
                        help="Soliplex server base URL")
    parser.add_argument("--room", default="chat",
                        help="Room ID (default: chat)")
    parser.add_argument("--tool", action="append", dest="tools",
                        metavar="NAME:SCRIPT",
                        help="Client-side tool as name:script  (repeatable)")
    parser.add_argument("--message", "-m", default=None,
                        help="Send a single message and exit (non-interactive)")
    args = parser.parse_args()

    tools: dict[str, str] = {}
    for spec in (args.tools or []):
        if ":" not in spec:
            parser.error(f"--tool must be NAME:SCRIPT, got: {spec!r}")
        name, script = spec.split(":", 1)
        tools[name.strip()] = script.strip()

    conversation_loop(
        base_url=args.url,
        room=args.room,
        tools=tools,
        initial_message=args.message,
    )


if __name__ == "__main__":
    main()
