---
name: soliplex-consumer-tool
description: Demonstrate AG-UI client-side (consumer) tool calling against a Soliplex server — register a local shell script as a tool, invoke a room, handle tool calls from the SSE stream, and feed results back in a follow-up run
---

# Soliplex Consumer Tool Demo

This skill demonstrates **client-side (consumer) tool calling** in the AG-UI protocol with a Soliplex server using `curl`. A local shell script is registered as a tool; when the LLM calls it, the client executes the script and returns the result in a follow-up run.

## How Consumer Tools Work

In AG-UI, `tools` in `RunAgentInput` are **consumer tools** — the server exposes them to the LLM but does NOT execute them. When the LLM calls one:

1. Server emits `TOOL_CALL_START` / `TOOL_CALL_ARGS` / `TOOL_CALL_END`, then `RUN_FINISHED`
2. Client executes the tool locally (the shell script)
3. Client creates a **new run** on the same thread, passing:
   - All prior messages
   - An assistant message containing the tool call (`role: "assistant"`, `toolCalls: [...]`)
   - A tool result message (`role: "tool"`, `toolCallId`, `content`)
   - The **same `tools` array** again (required every run)

## Setup: The Tool Script

The `secret_number.sh` script lives alongside this skill:

```bash
#!/bin/bash
echo "42"
```

To use a different script, set `TOOL_SCRIPT` before running the demo.

## Full Demo (curl + bash)

Set `SOLIPLEX_URL` if not using the default:

```bash
export SOLIPLEX_URL="${SOLIPLEX_URL:-http://localhost:8000}"
export TOOL_SCRIPT="${TOOL_SCRIPT:-./secret_number.sh}"
```

### Step 1 — Create a thread

```bash
THREAD_RESP=$(curl -s -X POST "${SOLIPLEX_URL}/api/v1/rooms/chat/agui" \
  -H "Content-Type: application/json" \
  -d '{"metadata": {"name": "consumer tool demo"}}')

THREAD_ID=$(echo "$THREAD_RESP" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['thread_id'])")
RUN_ID=$(echo "$THREAD_RESP"    | python3 -c "import json,sys; d=json.load(sys.stdin); print(next(iter(d['runs'])))")
```

### Step 2 — Execute the run with the tool defined

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
      \"description\": \"Returns the secret number. Call this to find out what the secret number is.\",
      \"parameters\":  {\"type\": \"object\", \"properties\": {}, \"required\": []}
    }],
    \"context\": [],
    \"forwardedProps\": {}
  }")
```

### Step 3 — Parse the SSE stream for tool calls

```bash
TOOL_CALL_ID=$(echo "$SSE" | python3 -c "
import json, sys
for line in sys.stdin:
    if line.startswith('data: '):
        ev = json.loads(line[6:])
        if ev.get('type') == 'TOOL_CALL_START':
            print(ev['toolCallId']); break
")

ASST_MSG_ID=$(echo "$SSE" | python3 -c "
import json, sys
for line in sys.stdin:
    if line.startswith('data: '):
        ev = json.loads(line[6:])
        if ev.get('type') == 'TOOL_CALL_START':
            print(ev['parentMessageId']); break
")

TOOL_ARGS=$(echo "$SSE" | python3 -c "
import json, sys
args = ''
for line in sys.stdin:
    if line.startswith('data: '):
        ev = json.loads(line[6:])
        if ev.get('type') == 'TOOL_CALL_ARGS':
            args += ev.get('delta', '')
print(args or '{}')
")
```

If `TOOL_CALL_ID` is empty the LLM answered directly (no tool call needed). Otherwise continue:

### Step 4 — Execute the local tool script

```bash
TOOL_RESULT=$(bash "$TOOL_SCRIPT")
echo "Tool result: $TOOL_RESULT"
```

### Step 5 — Create a follow-up run

```bash
NEW_RUN=$(curl -s -X POST "${SOLIPLEX_URL}/api/v1/rooms/chat/agui/${THREAD_ID}" \
  -H "Content-Type: application/json" \
  -d '{}')
NEW_RUN_ID=$(echo "$NEW_RUN" | python3 -c "import json,sys; print(json.load(sys.stdin)['run_id'])")
```

### Step 6 — Submit the tool result (with tools array)

```bash
FINAL=$(curl -s -X POST "${SOLIPLEX_URL}/api/v1/rooms/chat/agui/${THREAD_ID}/${NEW_RUN_ID}" \
  -H "Content-Type: application/json" \
  -d "{
    \"threadId\": \"${THREAD_ID}\",
    \"runId\":    \"${NEW_RUN_ID}\",
    \"state\": {},
    \"messages\": [
      {\"id\": \"user_001\",        \"role\": \"user\",      \"content\": \"what is the secret number\"},
      {\"id\": \"${ASST_MSG_ID}\",  \"role\": \"assistant\", \"content\": null,
       \"toolCalls\": [{
         \"id\":   \"${TOOL_CALL_ID}\",
         \"type\": \"function\",
         \"function\": {\"name\": \"secret_number\", \"arguments\": \"${TOOL_ARGS}\"}
       }]},
      {\"id\": \"tool_result_001\", \"role\": \"tool\", \"content\": \"${TOOL_RESULT}\",
       \"toolCallId\": \"${TOOL_CALL_ID}\"}
    ],
    \"tools\": [{
      \"name\":        \"secret_number\",
      \"description\": \"Returns the secret number. Call this to find out what the secret number is.\",
      \"parameters\":  {\"type\": \"object\", \"properties\": {}, \"required\": []}
    }],
    \"context\": [],
    \"forwardedProps\": {}
  }")
```

### Step 7 — Extract the final text response

```bash
echo "$FINAL" | python3 -c "
import json, sys
text = ''
for line in sys.stdin:
    if line.startswith('data: '):
        try:
            ev = json.loads(line[6:])
            if ev.get('type') == 'TEXT_MESSAGE_CONTENT':
                text += ev.get('delta', '')
        except: pass
print(text)
"
```

## AG-UI Consumer Tool Reference

### Tool definition (in `tools` array)

```json
{
  "name": "tool_name",
  "description": "What this tool does — the LLM uses this to decide when to call it",
  "parameters": {
    "type": "object",
    "properties": {
      "arg1": {"type": "string", "description": "..."}
    },
    "required": ["arg1"]
  }
}
```

### SSE events emitted for a tool call

| Event | Key fields | Action |
|---|---|---|
| `TOOL_CALL_START` | `toolCallId`, `toolCallName`, `parentMessageId` | Record IDs |
| `TOOL_CALL_ARGS`  | `toolCallId`, `delta` | Accumulate `delta` strings into args JSON |
| `TOOL_CALL_END`   | `toolCallId` | Args complete |
| `RUN_FINISHED`    | — | Run done; execute the tool now |

### Message format for follow-up run

The assistant message carrying the tool call uses the `parentMessageId` from `TOOL_CALL_START` as its `id`. The `arguments` field in `function` is a **JSON string** (not an object):

```json
{
  "id": "<parentMessageId>",
  "role": "assistant",
  "content": null,
  "toolCalls": [
    {
      "id": "<toolCallId>",
      "type": "function",
      "function": {
        "name": "<toolCallName>",
        "arguments": "{\"arg1\": \"value\"}"
      }
    }
  ]
}
```

The tool result message references the same `toolCallId`:

```json
{
  "id": "tool_result_001",
  "role": "tool",
  "content": "<output from your script>",
  "toolCallId": "<toolCallId>"
}
```

**Always include the `tools` array again on every run** — the server does not persist tool definitions between runs.
