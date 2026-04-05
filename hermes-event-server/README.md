# Hermes Event Server

Thin FastAPI wrapper around [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) that emits structured SSE events for integration with Soliplex.

## Prerequisites

- Docker installed
- An LLM provider API key (Anthropic, OpenAI, MiniMax, OpenRouter, or local Ollama)

## Quick Start

### 1. Build the base Hermes image

```bash
git clone --depth 1 https://github.com/NousResearch/hermes-agent.git /tmp/hermes-agent
cd /tmp/hermes-agent
docker build -t hermes-agent:latest .
```

This takes ~5 minutes. Installs Python, Node.js, Playwright, and all Hermes dependencies.

### 2. Initialize Hermes data directory

```bash
mkdir -p ~/hermes-data

# Run Hermes once to bootstrap config files
docker run --rm -v ~/hermes-data:/opt/data hermes-agent:latest doctor
```

This creates `~/hermes-data/` with:
- `.env` — API keys (**you must edit this — see step 3**)
- `config.yaml` — runtime configuration
- `SOUL.md` — agent personality
- `skills/` — 74 bundled skills

> **Note:** The `.env` file is copied from `.env.example` with all keys blank.
> You must configure at least one LLM provider before the event server will work.
> If you skip this step, all agent requests will fail with HTTP 401.

### 3. Configure your LLM provider

Edit `~/hermes-data/.env` and set at least one API key:

```bash
# Option A: Anthropic (direct)
ANTHROPIC_API_KEY=sk-ant-...

# Option B: OpenAI
OPENAI_API_KEY=sk-...

# Option C: OpenRouter (200+ models)
OPENROUTER_API_KEY=sk-or-...

# Option D: MiniMax
MINIMAX_API_KEY=sk-cp-...
MINIMAX_BASE_URL=https://api.minimax.io/v1
```

Or use `hermes login` for OAuth:
```bash
docker run -it -v ~/hermes-data:/opt/data hermes-agent:latest login
```

Or configure a local model (Ollama):
```bash
# No API key needed — just set the base URL in config.yaml
# model: your-model-name
# provider: custom
# base_url: http://host.docker.internal:11434/v1
```

### 4. Build the event server image

```bash
cd hermes-event-server/
docker build -t hermes-event-server:latest .
```

### 5. Run the event server

```bash
docker run -d \
  --name hermes-events \
  -v ~/hermes-data:/opt/data \
  -p 8642:8642 \
  hermes-event-server:latest
```

### 6. Verify it works

```bash
# Health check
curl http://localhost:8642/health

# List tools (should show 48+)
curl http://localhost:8642/v1/agent/tools | python3 -c "import sys,json; print(json.load(sys.stdin)['tools'][:3])"

# Send a message
curl -N http://localhost:8642/v1/agent/run \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello!", "config": {"max_iterations": 2}}'
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/v1/agent/run` | POST | Run agent, stream SSE events |
| `/v1/agent/tools` | GET | List available tools and toolsets |
| `/v1/agent/skills` | GET | List available skills (74 bundled) |
| `/v1/agent/memory` | GET | Read agent memory and user profile |

### POST /v1/agent/run

```json
{
  "message": "What time is it?",
  "session_id": "optional-session-id",
  "history": [
    {"role": "user", "content": "prior message"},
    {"role": "assistant", "content": "prior response"}
  ],
  "config": {
    "model": "MiniMax-M2.7",
    "max_iterations": 10,
    "enabled_toolsets": ["terminal", "web"],
    "disabled_toolsets": [],
    "system_prompt": "You are a helpful assistant."
  },
  "client_tools": [
    {
      "name": "confirm_action",
      "description": "Ask user to confirm before destructive actions",
      "parameters": {
        "type": "object",
        "properties": {"action": {"type": "string"}},
        "required": ["action"]
      }
    }
  ]
}
```

### SSE Event Schema

```
data: {"type":"run_started","run_id":"..."}
data: {"type":"step","iteration":1,"max_iterations":10,"prev_tools":[]}
data: {"type":"thinking","content":"🧠 pondering..."}
data: {"type":"thinking_end"}
data: {"type":"reasoning_delta","delta":"The user wants..."}
data: {"type":"text_start","message_id":"msg_1"}
data: {"type":"text_delta","delta":"Hello!","message_id":"msg_1"}
data: {"type":"text_end","message_id":"msg_1"}
data: {"type":"tool_start","tool_call_id":"call_abc","name":"terminal","args":{"command":"date"}}
data: {"type":"tool_result","tool_call_id":"call_abc","name":"terminal","content":"{...}"}
data: {"type":"run_finished","run_id":"...","usage":{...},"session_id":"..."}
data: [DONE]
```

## Using with Soliplex

Add a Hermes room to your Soliplex installation:

```yaml
# example/rooms/hermes/room_config.yaml
id: "hermes"
name: "Hermes Agent"
description: "Self-improving AI agent powered by Hermes"
agent:
  kind: hermes
  hermes_url: http://localhost:8642
  hermes_model: "MiniMax-M2.7"
  hermes_max_iterations: 10
  hermes_toolsets:
    - terminal
    - file
    - web
```

Add the room path to your installation config:
```yaml
room_paths:
  - "./rooms/hermes"
```

## Docker Compose (full stack)

```bash
docker compose up -d
```

See `docker-compose.yaml` for the full configuration with PostgreSQL and health checks.

## Persistent Data

Everything persists in `~/hermes-data/`:

| Path | Contents |
|------|----------|
| `auth.json` | Credential pool (API keys, OAuth tokens) |
| `.env` | Environment variables |
| `state.db` | Session history (SQLite) |
| `memories/MEMORY.md` | Agent's learned facts |
| `memories/USER.md` | User profile |
| `skills/` | 74 bundled + user-created skills |
| `config.yaml` | Runtime configuration |
| `sessions/` | Conversation logs |

## Running Integration Tests

```bash
# With Soliplex venv (has httpx)
cd ../backend/main
venv/bin/python3 ../hermes-event-server/test_integration.py
```

13 tests covering: health, tools, skills, memory, text streaming, tool calls, tool ID consistency, thinking events, step events, client-side tools, client tool interrupt, error handling, concurrent isolation.
