# Plan: Soliplex–Moodle Workplace Integration (Revised)

## Context

Soliplex needs to query Moodle Workplace for course, enrollment, and completion data so an AI agent can answer questions about training status. A Docker-based Moodle Workplace 5.0.2 sandbox exists at `/Users/ryan.day/Dev/moodle_sandbox/`.

**Two hard constraints** killed the original MCP-tool-calling approach:

1. **The LLMs are bad at tool calling.** Soliplex runs local/offline models ("gpt-oss:latest") that unreliably select and invoke MCP tools.
2. **No separate deployable service.** A standalone `moodle-mcp-tools` repo requires deploying, hosting, and approving a separate service. Non-starter.

## Revised Approach: Dynamic System Prompt with Pre-Fetched Context

Use Pydantic AI's **`@agent.system_prompt` decorator** — the standard pattern for injecting dynamic context. The factory creates a normal `pydantic_ai.Agent` and registers an async system prompt function that fetches Moodle data before every LLM call.

1. **Moodle client code lives in Soliplex** as `src/soliplex/moodle/` — ships with the package, no separate deployment
2. **Factory** builds a standard `pydantic_ai.Agent` with an `@agent.system_prompt` function that pre-fetches Moodle data
3. **The LLM just reads and answers** — no tool calling required

### Runtime Flow

```
User asks: "Has testuser1 completed the safety course?"
    ↓
Pydantic AI calls @agent.system_prompt function automatically
    ↓
Function fetches from Moodle REST API:
  - Course list
  - Enrolled users per course
  - Completion status per user/course
    ↓
Returns formatted markdown text → prepended to system prompt
    ↓
LLM receives: base system prompt + Moodle data + user question
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
