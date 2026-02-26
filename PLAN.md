# Plan: Soliplex–Moodle Workplace Integration (Revised)

## Context

Soliplex needs to query Moodle Workplace for course, enrollment, and completion data so an AI agent can answer questions about training status. A Docker-based Moodle Workplace 5.0.2 sandbox exists at `/Users/ryan.day/Dev/moodle_sandbox/`.

**Two hard constraints** killed the original MCP-tool-calling approach:

1. **The LLMs are bad at tool calling.** Soliplex runs local/offline models ("gpt-oss:latest") that unreliably select and invoke MCP tools.
2. **No separate deployable service.** A standalone `moodle-mcp-tools` repo requires deploying, hosting, and approving a separate service. Non-starter.

## Revised Approach: Dynamic System Prompt with Pre-Fetched Context

Use Pydantic AI's **`instructions` callable** — an async function passed to the `Agent` constructor that is evaluated on every request (unlike `@agent.system_prompt` which is skipped when AG-UI provides `message_history`). The factory creates a normal `pydantic_ai.Agent` and passes an async `instructions` callable that fetches Moodle data before every LLM call.

1. **Moodle client code lives in Soliplex** as `src/soliplex/moodle/` — ships with the package, no separate deployment
2. **Factory** builds a standard `pydantic_ai.Agent` with an `instructions` callable that pre-fetches Moodle data
3. **The LLM just reads and answers** — no tool calling required

### Runtime Flow

```
User asks: "Has testuser1 completed the safety course?"
    ↓
Pydantic AI calls instructions callable automatically
    ↓
Function fetches from Moodle REST API:
  - Course list
  - Enrolled users per course
  - Completion status per user/course
    ↓
Returns formatted markdown text → used as system instructions
    ↓
LLM receives: base prompt + Moodle data + user question
    ↓
LLM answers from context (no tool calling)
```

## What Was Built

### 1. Moodle client module: `src/soliplex/moodle/`

```
src/soliplex/moodle/
├── __init__.py
├── client.py       # Async httpx Moodle REST API client
├── models.py       # Pydantic response models
└── agent.py        # Factory agent with dynamic system prompt
```

### 2. Room config: `example/rooms/moodle/room_config.yaml`

Uses `kind: factory` with `extra_config` for Moodle secrets.

### 3. Dependencies

- `httpx` added to `pyproject.toml` (was already transitive)

### 4. Coverage

- `src/soliplex/moodle/agent.py` added to `[tool.coverage.run] omit` in `pyproject.toml` — the factory instantiates real Pydantic AI models that require an LLM provider at runtime

### 5. Tests

- `tests/unit/test_moodle_client.py` — 14 client unit tests with mocked httpx
- `tests/unit/test_moodle_room.py` — Room config loading test (updated for factory pattern)

## Key Files Created

- `src/soliplex/moodle/__init__.py` — Package init
- `src/soliplex/moodle/client.py` — Async httpx Moodle REST API client
- `src/soliplex/moodle/models.py` — Pydantic response models
- `src/soliplex/moodle/agent.py` — Factory agent with dynamic system prompt
- `tests/unit/test_moodle_client.py` — Client unit tests

## Key Files Modified

- `pyproject.toml` — Added `httpx` dependency; added `agent.py` to coverage omit
- `example/rooms/moodle/room_config.yaml` — Changed from `default` + MCP toolsets to `factory` kind
- `tests/unit/test_moodle_room.py` — Updated assertions for new factory config shape

---

## Phase 2: Tool-Calling Research Variant

### Motivation

The Phase 1 `moodle` room pre-fetches all Moodle data into the LLM's instructions — reliable but doesn't test tool-calling ability. A parallel `moodle-tools` room exposes Moodle API methods as Pydantic AI tools, letting the LLM decide which to call. This gives a direct A/B comparison with the same model, data, and questions.

### What Was Built

A second factory function (`moodle_tools_agent_factory`) in `agent.py` that creates a `pydantic_ai.Agent` with 4 `@agent.tool_plain`-decorated functions wrapping `MoodleClient` methods:

| Tool | Client Method | Parameters | Purpose |
|------|--------------|------------|---------|
| `list_courses` | `get_courses()` | none | Entry point — discover course IDs |
| `find_user` | `get_users_by_field()` | `field`, `value` | Look up user ID by username/email |
| `list_enrolled_users` | `get_enrolled_users()` | `courseid` | See who's in a course |
| `get_completion_status` | `get_course_completion_status()` | `courseid`, `userid` | Check if user completed course |

Each tool returns a JSON string (minimal projection of the Pydantic model) to keep the LLM's context lean. `get_completion_status` wraps exceptions in `{"error": ...}` JSON since completion tracking may be disabled.

### Key Design Decisions

- **Same file as Phase 1 factory** — shares `_build_model()` helper; both in coverage omit
- **`@agent.tool_plain` decorator** — tools don't need `RunContext`, cleaner for closures over `MoodleClient`
- **Static `instructions`** (not async callable) — the LLM discovers data via tools, not pre-loaded context
- **Tool docstrings** — Pydantic AI passes them to the LLM as function descriptions
- **`extra_config` supports different models** — set `provider_type`/`model_name` in room YAML to test tool calling with different LLMs

### Files Created

- `example/rooms/moodle-tools/room_config.yaml` — Room config for tool-calling variant
- `tests/unit/test_moodle_tools_room.py` — Room config loading test

### Files Modified

- `src/soliplex/moodle/agent.py` — Added `MOODLE_TOOLS_PROMPT`, `moodle_tools_agent_factory()` with 4 tools
- `example/minimal.yaml` — Added `./rooms/moodle-tools` to room paths
