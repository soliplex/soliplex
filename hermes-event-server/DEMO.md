# Hermes + Soliplex Demo

## Setup (one-time, ~5 minutes)

```bash
# 1. Build Hermes base image
git clone --depth 1 https://github.com/NousResearch/hermes-agent.git /tmp/hermes-agent
cd /tmp/hermes-agent && docker build -t hermes-agent:latest .

# 2. Initialize data directory
mkdir -p ~/hermes-data
docker run --rm -v ~/hermes-data:/opt/data hermes-agent:latest doctor
# Edit ~/hermes-data/.env — add at least one LLM API key

# 3. Build + start event server
cd hermes-event-server
docker build -t hermes-event-server:latest .
docker run -d --name hermes-events -v ~/hermes-data:/opt/data -p 8642:8642 hermes-event-server:latest

# 4. Start Soliplex
soliplex-cli serve example/minimal.yaml --no-auth-mode
```

## Quick Validation

```bash
# Everything running?
bash example/skills/soliplex-api/scripts/health_check.sh
```

## Demo Script

### Act 1: Hermes Agent Room (Path 3 — Hermes drives)

Open **"Hermes Agent"** room in Flutter.

**Show: Web search with tool visibility**
> Search the web for latest AI agent news

You'll see:
- Thinking indicator ("pondering...")
- Step progress ("Step 1/10")
- TOOL_CALL card: web_search with args and results
- Streamed text response synthesizing the results

**Show: Terminal access**
> What time is it? Use the terminal.

You'll see:
- TOOL_CALL: terminal → `date` command
- Result from inside the Docker container
- Text response with formatted time

**Show: Memory persistence**
> Remember that my name is Alice and I prefer Python.

Then start a NEW thread:
> What's my name?

Agent recalls "Alice" from memory — persists across sessions.

### Act 2: Hybrid Room (pydantic-ai + Hermes)

Open **"Hybrid Agent"** room in Flutter.

**Show: Platform awareness**
> What tools and capabilities do you have?

Agent lists both Soliplex tools (datetime, file uploads) AND Hermes tools
(web_search, terminal, run_hermes_task) — informed by the soliplex-guide skill.

**Show: Direct Hermes tool call**
> Search the web for Solana price today

Orchestrator calls `hermes_tool("web_search", ...)` — single tool card,
Tavily results returned.

**Show: Complex delegation**
> Use run_hermes_task to research quantum computing advances and write a summary

Orchestrator delegates to Hermes — single tool card but the result contains
a full multi-step research summary (Hermes ran web_search + synthesis internally).

**Show: Cross-room communication**
> Ask the plain room what time it is

Orchestrator calls `ask_room("plain", "What time is it?")` — the plain room's
agent uses its `get_current_datetime` tool and returns the result. Two AG-UI
streams run (hybrid + plain).

### Act 3: Three Rooms Side by Side

Same question in all three rooms:
> Search the web for SpaceX news

| Room | What you see |
|------|-------------|
| **Hermes Agent** | Individual tool cards (web_search), thinking, steps, streamed text |
| **Hermes Quick Chat** | No tools — text-only response (can't search without web toolset) |
| **Hybrid Agent** | One `hermes_tool` card wrapping the web search, then synthesis |

### Act 4: Client-Side Tools

From the Hermes room (or use the script):

```bash
python3 example/skills/soliplex-agui/scripts/client_tool_test.py hermes \
  "Delete all temporary files. You MUST confirm with the user first."
```

Shows:
- Agent decides to call `confirm_action` (client-side tool)
- Run finishes with `awaiting_client` result
- In Flutter, this would show a confirmation dialog

### Act 5: Skill Scripts (for developers)

```bash
# Health check
bash example/skills/soliplex-api/scripts/health_check.sh

# List all rooms
bash example/skills/soliplex-api/scripts/list_rooms.sh

# Hermes tool availability
python3 example/skills/soliplex-api/scripts/hermes_tools.py

# Create thread and run (any room)
python3 example/skills/soliplex-agui/scripts/create_thread_and_run.py hermes "Hello"
python3 example/skills/soliplex-agui/scripts/create_thread_and_run.py plain "What time is it?"
python3 example/skills/soliplex-agui/scripts/create_thread_and_run.py hermes-hybrid "Use hermes_tool to search for AI news"

# Cross-room communication
python3 example/skills/soliplex-agui/scripts/cross_room_test.py plain "What time is it?"

# State round-trip
python3 example/skills/soliplex-agui/scripts/state_roundtrip_test.py hermes

# Full integration test suite (13 tests)
python3 hermes-event-server/test_integration.py
```

## Key Talking Points

1. **Zero pydantic-ai changes** — existing rooms work exactly as before
2. **Event contract pattern** — Hermes and Soliplex are independent services
3. **Three integration patterns** coexist:
   - Path 3 rooms (Hermes drives, full tool visibility)
   - Hybrid rooms (pydantic-ai drives, Hermes as tools)
   - Cross-room communication (rooms call each other)
4. **30 Hermes tools + 74 skills** available alongside Soliplex native tools
5. **AG-UI protocol** — thinking, steps, state snapshots, client-side tools all work
6. **Memory persists** across sessions — self-improving agent
7. **Skills teach the agent** about the platform — API reference, AG-UI protocol
8. **3145 unit tests passing**, 13 integration tests, 7 skill scripts
