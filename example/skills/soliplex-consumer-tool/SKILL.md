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

## Single-shot curl reference

For scripting or quick one-off calls (not interactive), the `curl` approach from earlier
still works.  See the `## Full Demo (curl + bash)` section below for the step-by-step.

---

## Full Demo (curl + bash)

For scripted (non-interactive) use, here is the raw curl flow:

### 1 — Create a thread

```bash
SOLIPLEX_URL="${SOLIPLEX_URL:-http://localhost:8000}"
THREAD_RESP=$(curl -s -X POST "${SOLIPLEX_URL}/api/v1/rooms/chat/agui" \
  -H "Content-Type: application/json" \
  -d '{"metadata": {"name": "consumer tool demo"}}')
THREAD_ID=$(echo "$THREAD_RESP" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['thread_id'])")
RUN_ID=$(echo "$THREAD_RESP"    | python3 -c "import json,sys; d=json.load(sys.stdin); print(next(iter(d['runs'])))")
```

### 2 — Execute run with tool defined

```bash
SSE=$(curl -s -X POST "${SOLIPLEX_URL}/api/v1/rooms/chat/agui/${THREAD_ID}/${RUN_ID}" \
  -H "Content-Type: application/json" \
  -d "{
    \"threadId\": \"${THREAD_ID}\",
    \"runId\":    \"${RUN_ID}\",
    \"state\": {},
    \"messages\": [{\"id\": \"user_001\", \"role\": \"user\", \"content\": \"what is the secret number\"}],
    \"tools\": [{
      \"name\":        \"secret_number\",
      \"description\": \"Returns the secret number.\",
      \"parameters\":  {\"type\": \"object\", \"properties\": {}, \"required\": []}
    }],
    \"context\": [],
    \"forwardedProps\": {}
  }")
```

### 3 — Parse tool call from SSE

```bash
TOOL_CALL_ID=$(echo "$SSE" | python3 -c "
import json,sys
for l in sys.stdin:
    if l.startswith('data: '):
        ev=json.loads(l[6:])
        if ev.get('type')=='TOOL_CALL_START': print(ev['toolCallId']); break
")
ASST_MSG_ID=$(echo "$SSE" | python3 -c "
import json,sys
for l in sys.stdin:
    if l.startswith('data: '):
        ev=json.loads(l[6:])
        if ev.get('type')=='TOOL_CALL_START': print(ev['parentMessageId']); break
")
TOOL_ARGS=$(echo "$SSE" | python3 -c "
import json,sys; args=''
for l in sys.stdin:
    if l.startswith('data: '):
        ev=json.loads(l[6:])
        if ev.get('type')=='TOOL_CALL_ARGS': args+=ev.get('delta','')
print(args or '{}')
")
```

### 4 — Run the script

```bash
TOOL_RESULT=$(bash ./secret_number.sh)
```

### 5 — New run + submit tool result

```bash
NEW_RUN_ID=$(curl -s -X POST "${SOLIPLEX_URL}/api/v1/rooms/chat/agui/${THREAD_ID}" \
  -H "Content-Type: application/json" -d '{}' \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['run_id'])")

curl -s -X POST "${SOLIPLEX_URL}/api/v1/rooms/chat/agui/${THREAD_ID}/${NEW_RUN_ID}" \
  -H "Content-Type: application/json" \
  -d "{
    \"threadId\": \"${THREAD_ID}\",
    \"runId\":    \"${NEW_RUN_ID}\",
    \"state\": {},
    \"messages\": [
      {\"id\": \"user_001\",       \"role\": \"user\",      \"content\": \"what is the secret number\"},
      {\"id\": \"${ASST_MSG_ID}\", \"role\": \"assistant\", \"content\": null,
       \"toolCalls\": [{\"id\": \"${TOOL_CALL_ID}\", \"type\": \"function\",
         \"function\": {\"name\": \"secret_number\", \"arguments\": \"${TOOL_ARGS}\"}}]},
      {\"id\": \"tool_result_001\", \"role\": \"tool\", \"content\": \"${TOOL_RESULT}\",
       \"toolCallId\": \"${TOOL_CALL_ID}\"}
    ],
    \"tools\": [{
      \"name\": \"secret_number\",
      \"description\": \"Returns the secret number.\",
      \"parameters\": {\"type\": \"object\", \"properties\": {}, \"required\": []}
    }],
    \"context\": [],
    \"forwardedProps\": {}
  }" | python3 -c "
import json,sys; text=''
for l in sys.stdin:
    if l.startswith('data: '):
        ev=json.loads(l[6:])
        if ev.get('type')=='TEXT_MESSAGE_CONTENT': text+=ev.get('delta','')
print(text)
"
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
