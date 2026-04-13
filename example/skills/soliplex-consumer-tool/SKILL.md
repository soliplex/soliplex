---
name: soliplex-consumer-tool
description: Multi-turn Soliplex chat with client-side (consumer) tools — local shell scripts registered as AG-UI tools, with transparent tool-call handling and full conversation state
---

# Soliplex Consumer Tool

This skill lets you hold a **stateful multi-turn conversation** with a Soliplex room while
registering **local shell scripts** as tools.  When the LLM calls a tool, the script runs
locally and the result is fed back silently — the user only ever sees the final text replies.

## What "consumer tools" means

In the AG-UI protocol the `tools` array in `RunAgentInput` describes **client-side tools** —
the server exposes them to the LLM but never executes them.  The client is responsible for:

1. Running the script when the LLM calls it
2. Submitting the result in a follow-up run on the same thread
3. Repeating until the LLM produces a text response (tool chains are possible)

## Conversation state model

```
messages[]   ← the single source of truth; grows with every turn
thread_id    ← fixed for the session
run_id       ← new one per HTTP request

user turn N:
  append → {role: user, content: "..."}
  while True:
      execute_run(messages, tools)   ← always pass the full list
      ┌─ tool call? → run script, append assistant+tool-result msgs, loop
      └─ text?      → print, append assistant msg, break → next user turn
```

Key rules:
- **Always send the full `messages[]` array** on every run — the server is stateless.
- **Always send the `tools` array** on every run — it is not persisted server-side.
- Tool calls are **invisible to the user**; handle them in the inner loop before printing anything.

## Quick start

```bash
# Run a session with the built-in example tool
python3 soliplex_chat.py \
    --url  http://localhost:8000 \
    --room chat \
    --tool secret_number:./secret_number.sh
```

The `secret_number.sh` script next to this skill just echoes `42`.  The conversation
looks like:

```
Connected to http://localhost:8000/rooms/chat  (thread 4aa71b4e…)
Tools registered: secret_number
Type 'quit' or Ctrl-D to exit.

you: Hi
llm: Hi! How can I help you today?

you: what is the secret number?
llm: The secret number is 42.

you: Do you see any other tools?
llm: I only have access to one tool: secret_number.

you: quit
```

The tool call on turn 2 is completely invisible — `soliplex_chat.py` ran the script,
submitted the result, and the LLM responded with "42" without any visible intermediate turn.

## Registering multiple tools

Each `--tool` flag registers one script:

```bash
python3 soliplex_chat.py \
    --url  http://localhost:8000 \
    --room chat \
    --tool secret_number:./secret_number.sh \
    --tool get_time:./get_time.sh \
    --tool weather:./weather.sh
```

## Writing a tool script

Scripts receive the LLM's JSON argument string on **stdin** and must write their result
to **stdout**.  Exit code 0 = success; anything else is reported as an error to the LLM.

```bash
#!/bin/bash
# secret_number.sh — no arguments needed
echo "42"
```

```bash
#!/bin/bash
# get_time.sh — args on stdin (ignored here)
date -u +"%Y-%m-%dT%H:%M:%SZ"
```

A script with named parameters (Python example for clarity):

```python
#!/usr/bin/env python3
# unit_converter.py
import json, sys
args = json.load(sys.stdin)        # e.g. {"value": 100, "from": "km", "to": "miles"}
value = args["value"]
# ... convert ...
print(result)
```

## No external dependencies

`soliplex_chat.py` uses **Python stdlib only** (`http.client`, `json`, `subprocess`, `urllib`).
No `pip install` required — runs on any Python 3.8+ installation.

## One-shot (non-interactive)

Use `--message` / `-m` to send a single message and exit — useful in scripts or CI:

```bash
python3 soliplex_chat.py \
    --room chat \
    --tool secret_number:./secret_number.sh \
    --message "what is the secret number"
# → The secret number is 42.
```

Capture the output:

```bash
ANSWER=$(python3 soliplex_chat.py -m "what is the secret number" \
    --tool secret_number:./secret_number.sh)
echo "Got: $ANSWER"
```

---

## AG-UI consumer tool event reference

| SSE event | Key fields | What to do |
|---|---|---|
| `TOOL_CALL_START` | `toolCallId`, `toolCallName`, `parentMessageId` | Record; `parentMessageId` becomes the assistant message `id` |
| `TOOL_CALL_ARGS`  | `toolCallId`, `delta` | Concatenate `delta` values → full args JSON string |
| `TOOL_CALL_END`   | `toolCallId` | Args complete |
| `RUN_FINISHED`    | — | Run done; execute tool(s) now, then create a new run |
| `TEXT_MESSAGE_CONTENT` | `delta` | Concatenate → final response text |
| `RUN_ERROR`       | `message` | Report error; abort |

**Tool result message format** (in the follow-up run's `messages` array):

```json
[
  {
    "id": "<parentMessageId from TOOL_CALL_START>",
    "role": "assistant",
    "content": null,
    "toolCalls": [
      {"id": "<toolCallId>", "type": "function",
       "function": {"name": "<toolCallName>", "arguments": "<args JSON string>"}}
    ]
  },
  {
    "id": "tool_result_001",
    "role": "tool",
    "content": "<script stdout>",
    "toolCallId": "<toolCallId>"
  }
]
```
