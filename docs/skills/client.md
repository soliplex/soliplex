# Consumer Tool Client

The `soliplex-consumer-tool` skill demonstrates **client-side (consumer) tool calling**
with a Soliplex server.  Local shell scripts are registered as AG-UI tools; when the LLM
calls one the script runs on the client and the result is fed back silently — the user only
ever sees the final text response.

The implementation lives in
`example/skills/soliplex-consumer-tool/` and requires only Python's standard library
(no `pip install`).

## Quick start

```bash
cd example/skills/soliplex-consumer-tool

# Interactive REPL
python3 soliplex_chat.py \
    --url  http://localhost:8000 \
    --room chat \
    --tool secret_number:./secret_number.sh

# One-shot (non-interactive)
python3 soliplex_chat.py \
    --message "what is the secret number" \
    --tool secret_number:./secret_number.sh
```

## Environment variables

| Variable | Purpose | CLI override |
|---|---|---|
| `SOLIPLEX_URL` | Server base URL (default: `http://localhost:8000`) | `--url` |
| `SOLIPLEX_ACCESS_TOKEN` | Bearer token for OIDC-protected servers | `--token` |

```bash
# OIDC-protected server
SOLIPLEX_URL=https://my.server.com \
SOLIPLEX_ACCESS_TOKEN=<token> \
python3 soliplex_chat.py --tool secret_number:./secret_number.sh
```

## Registering tools

Each `--tool` flag registers one executable script as a client-side tool:

```bash
python3 soliplex_chat.py \
    --tool secret_number:./secret_number.sh \
    --tool get_time:./get_time.sh \
    --tool weather:./weather.sh
```

## Writing a tool script

Scripts receive the LLM's JSON argument string on **stdin** and must write their result
to **stdout**.  Exit code 0 is success; any other exit code is reported as an error to
the LLM.

```bash
#!/bin/bash
# secret_number.sh — no arguments needed
echo "42"
```

```bash
#!/bin/bash
# get_time.sh
date -u +"%Y-%m-%dT%H:%M:%SZ"
```

Python scripts can parse structured arguments:

```python
#!/usr/bin/env python3
# unit_converter.py
import json, sys
args = json.load(sys.stdin)   # {"value": 100, "from": "km", "to": "miles"}
# ... convert and print result ...
```

## How consumer tools work

In the AG-UI protocol, `tools` in `RunAgentInput` are **consumer tools** — the server
exposes them to the LLM but does not execute them.  When the LLM calls one:

1. The server emits `TOOL_CALL_START` / `TOOL_CALL_ARGS` / `TOOL_CALL_END` events then `RUN_FINISHED`.
2. The client executes the script locally.
3. The client creates a **new run** on the same thread, passing all prior messages plus
   the assistant's tool call and the tool result.
4. Steps 1–3 repeat until the LLM produces a text response (tool chains are supported).

### Conversation state model

```
messages[]   ← the only state; grows with every turn
thread_id    ← fixed for the session
run_id       ← new one per HTTP request

user turn N:
  append → {role: user, content: "..."}
  while True:
      execute_run(messages, tools)   ← always pass the full list
      ┌─ tool call? → run script, append [assistant + tool_result], loop
      └─ text?      → print, append assistant msg, break
```

Two rules that must always hold:

- **Send the full `messages[]` on every run** — the server is stateless between runs.
- **Send the `tools` array on every run** — it is not persisted server-side.

## AG-UI event reference

| SSE event | Key fields | Action |
|---|---|---|
| `TOOL_CALL_START` | `toolCallId`, `toolCallName`, `parentMessageId` | Record IDs; `parentMessageId` is the assistant message `id` |
| `TOOL_CALL_ARGS` | `toolCallId`, `delta` | Concatenate `delta` strings → full args JSON |
| `TOOL_CALL_END` | `toolCallId` | Args complete |
| `RUN_FINISHED` | — | Run done; execute tool now, then create a new run |
| `TEXT_MESSAGE_CONTENT` | `delta` | Concatenate → final response text |
| `RUN_ERROR` | `message` | Report error; stop |

### Tool result message format

The assistant message uses `parentMessageId` (from `TOOL_CALL_START`) as its `id`.
`function.arguments` is a **JSON string**, not an object.

```json
[
  {
    "id": "<parentMessageId>",
    "role": "assistant",
    "content": null,
    "toolCalls": [
      {
        "id": "<toolCallId>",
        "type": "function",
        "function": { "name": "<toolCallName>", "arguments": "{}" }
      }
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
