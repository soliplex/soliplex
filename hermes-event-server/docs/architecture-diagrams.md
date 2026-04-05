# Hermes + Soliplex Architecture Diagrams

## 1. Runtime Services

```
┌──────────────────────────────────────────────────────────────────┐
│                        HOST MACHINE                              │
│                                                                  │
│  ┌─────────────────────┐   ┌──────────────────────────────────┐  │
│  │  Flutter Frontend   │   │  ~/hermes-data/ (volume)         │  │
│  │  (browser/app)      │   │    auth.json     ← credentials   │  │
│  │  port: 9000         │   │    state.db      ← sessions      │  │
│  └────────┬────────────┘   │    memories/     ← MEMORY.md     │  │
│           │ AG-UI SSE      │    skills/       ← 74 skills     │  │
│           │                │    config.yaml   ← runtime cfg   │  │
│           ▼                └────────┬─────────────────────────┘  │
│  ┌─────────────────────┐           │ docker -v mount             │
│  │  Soliplex Backend   │           │                             │
│  │  FastAPI + Uvicorn  │           │                             │
│  │  port: 8000         │           │                             │
│  │                     │           │                             │
│  │  ┌───────────────┐  │           │                             │
│  │  │ pydantic-ai   │  │           │                             │
│  │  │ rooms (chat,  │  │           │                             │
│  │  │ search, etc.) │  │           │                             │
│  │  └───────────────┘  │           │                             │
│  │  ┌───────────────┐  │   ┌──────▼───────────────────────────┐ │
│  │  │ hermes rooms  │──┼──▶│  Hermes Event Server (Docker)    │ │
│  │  │ (hermes,      │  │   │  FastAPI + Uvicorn               │ │
│  │  │  hermes-quick)│◀─┼───│  port: 8642                      │ │
│  │  └───────────────┘  │   │                                   │ │
│  └────────┬────────────┘   │  ┌─────────────────────────────┐  │ │
│           │                │  │  Hermes AIAgent              │  │ │
│           │                │  │  48 tools, skills, memory    │  │ │
│           ▼                │  │  thread pool (4 workers)     │  │ │
│  ┌─────────────────────┐   │  └──────────┬──────────────────┘  │ │
│  │  PostgreSQL 16      │   │             │                     │ │
│  │  port: 5432         │   └─────────────┼─────────────────────┘ │
│  │  soliplex DB        │                 │                       │
│  │  - threads          │                 ▼                       │
│  │  - run_events       │   ┌──────────────────────────────────┐  │
│  │  - run_agent_input  │   │  LLM Provider (external)         │  │
│  │  - authorization    │   │  MiniMax API (api.minimax.io)    │  │
│  └─────────────────────┘   │  or Anthropic, OpenAI, Ollama    │  │
│                            └──────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

## 2. Network Flow — Simple Text Response

```
 Flutter                    Soliplex :8000              Hermes :8642            MiniMax API
    │                           │                           │                      │
    │  POST /api/v1/rooms/      │                           │                      │
    │  hermes/agui              │                           │                      │
    │  (create thread)          │                           │                      │
    │ ─────────────────────────▶│                           │                      │
    │◀──────────────────────────│                           │                      │
    │  {thread_id, run_id}      │                           │                      │
    │                           │                           │                      │
    │  POST /api/v1/rooms/      │                           │                      │
    │  hermes/agui/{tid}/{rid}  │                           │                      │
    │  body: {messages, state}  │                           │                      │
    │ ─────────────────────────▶│                           │                      │
    │                           │  POST /v1/agent/run       │                      │
    │                           │  {message, config,        │                      │
    │                           │   session_id}             │                      │
    │                           │ ─────────────────────────▶│                      │
    │                           │                           │  POST /v1/chat/      │
    │                           │                           │  completions         │
    │                           │                           │ ────────────────────▶│
    │                           │                           │◀────────────────────│
    │                           │                           │  streaming tokens    │
    │                           │  SSE: text_delta          │                      │
    │                           │◀──────────────────────────│                      │
    │  SSE: TEXT_MESSAGE_       │                           │                      │
    │  CONTENT (camelCase)      │                           │                      │
    │◀──────────────────────────│                           │                      │
    │  ·····(more tokens)·····  │                           │                      │
    │                           │  SSE: run_finished        │                      │
    │                           │◀──────────────────────────│                      │
    │  SSE: STATE_SNAPSHOT      │                           │                      │
    │  SSE: RUN_FINISHED        │                           │                      │
    │◀──────────────────────────│                           │                      │
    │                           │                           │                      │
    │                           │  (background)             │                      │
    │                           │  save events to           │                      │
    │                           │  PostgreSQL               │                      │
    │                           │ ─────────▶ [DB]           │                      │
```

## 3. Network Flow — Tool Call (terminal)

```
 Flutter                    Soliplex :8000              Hermes :8642            MiniMax API
    │                           │                           │                      │
    │  POST agui/{tid}/{rid}    │                           │                      │
    │  "What time is it?"       │                           │                      │
    │ ─────────────────────────▶│                           │                      │
    │                           │  POST /v1/agent/run       │                      │
    │                           │ ─────────────────────────▶│                      │
    │                           │                           │─────▶ LLM API call 1 │
    │                           │                           │◀───── tool_calls:     │
    │                           │                           │       [{terminal,     │
    │  SSE: STEP_STARTED 1/10   │  SSE: step               │        "date"}]       │
    │◀──────────────────────────│◀──────────────────────────│                      │
    │  SSE: THINKING_*          │  SSE: thinking            │                      │
    │◀──────────────────────────│◀──────────────────────────│                      │
    │                           │                           │                      │
    │                           │                           │  ┌─────────────────┐ │
    │                           │                           │  │ execute:        │ │
    │                           │                           │  │ $ date          │ │
    │                           │                           │  │ Sun Apr 5 17:05 │ │
    │                           │                           │  └─────────────────┘ │
    │  SSE: TOOL_CALL_START     │  SSE: tool_start          │                      │
    │  (terminal)               │  (tool_call_id, args)     │                      │
    │◀──────────────────────────│◀──────────────────────────│                      │
    │  SSE: TOOL_CALL_ARGS      │                           │                      │
    │  {"command":"date"}       │                           │                      │
    │◀──────────────────────────│                           │                      │
    │  SSE: TOOL_CALL_END       │                           │                      │
    │◀──────────────────────────│                           │                      │
    │  SSE: TOOL_CALL_RESULT    │  SSE: tool_result         │                      │
    │  "Sun Apr 5 17:05"        │◀──────────────────────────│                      │
    │◀──────────────────────────│                           │                      │
    │                           │                           │─────▶ LLM API call 2 │
    │  SSE: STEP_STARTED 2/10   │  SSE: step                │◀───── text response  │
    │◀──────────────────────────│◀──────────────────────────│                      │
    │  SSE: TEXT_MESSAGE_*      │  SSE: text_delta          │                      │
    │  "It's Sunday, April 5"   │◀──────────────────────────│                      │
    │◀──────────────────────────│                           │                      │
    │  SSE: STATE_SNAPSHOT      │  SSE: run_finished        │                      │
    │  SSE: RUN_FINISHED        │◀──────────────────────────│                      │
    │◀──────────────────────────│                           │                      │
```

## 4. Network Flow — Client-Side Tool (confirm_action)

```
 Flutter                    Soliplex :8000              Hermes :8642            MiniMax API
    │                           │                           │                      │
    │  POST agui/{tid}/{rid1}   │                           │                      │
    │  {messages: ["Delete      │                           │                      │
    │   all files"],            │                           │                      │
    │   tools: [confirm_action],│                           │                      │
    │   state: {}}              │                           │                      │
    │ ─────────────────────────▶│                           │                      │
    │                           │  POST /v1/agent/run       │                      │
    │                           │  {message, client_tools:  │                      │
    │                           │   [confirm_action]}       │                      │
    │                           │ ─────────────────────────▶│                      │
    │                           │                           │  register tool in    │
    │                           │                           │  registry + append   │
    │                           │                           │  to agent.tools      │
    │                           │                           │                      │
    │                           │                           │─────▶ LLM sees       │
    │                           │                           │       confirm_action │
    │                           │                           │◀───── calls it       │
    │                           │                           │                      │
    │                           │                           │  handler fires:      │
    │                           │                           │  agent.interrupt()   │
    │                           │                           │  returns sentinel    │
    │                           │                           │                      │
    │  SSE: TOOL_CALL_START     │  SSE: tool_start          │                      │
    │  (confirm_action)         │  (confirm_action)         │                      │
    │◀──────────────────────────│◀──────────────────────────│                      │
    │  SSE: TOOL_CALL_ARGS      │                           │                      │
    │  {"action":"Delete all"}  │                           │                      │
    │◀──────────────────────────│                           │                      │
    │  SSE: TOOL_CALL_END       │                           │                      │
    │  SSE: TOOL_CALL_RESULT    │  SSE: tool_result         │                      │
    │  (awaiting_client)        │  (awaiting_client)        │                      │
    │◀──────────────────────────│◀──────────────────────────│                      │
    │  SSE: RUN_FINISHED        │  SSE: run_finished        │                      │
    │◀──────────────────────────│◀──────────────────────────│                      │
    │                           │                           │                      │
    │  ┌────────────────────┐   │                           │                      │
    │  │ Flutter shows      │   │                           │                      │
    │  │ confirmation       │   │                           │                      │
    │  │ dialog to user     │   │                           │                      │
    │  │                    │   │                           │                      │
    │  │ User clicks "No"  │   │                           │                      │
    │  └────────────────────┘   │                           │                      │
    │                           │                           │                      │
    │  POST agui/{tid}/{rid2}   │                           │                      │
    │  {messages: [...,         │                           │                      │
    │   {role: "tool",          │                           │                      │
    │    content: "declined"}], │                           │                      │
    │   state: {hermes_         │                           │                      │
    │    session_id: "..."}}    │                           │                      │
    │ ─────────────────────────▶│                           │                      │
    │                           │  POST /v1/agent/run       │                      │
    │                           │  {message, history:       │                      │
    │                           │   [..., tool_result]}     │                      │
    │                           │ ─────────────────────────▶│                      │
    │                           │                           │─────▶ LLM sees       │
    │                           │                           │       "declined"     │
    │                           │                           │◀───── text only      │
    │  SSE: TEXT_MESSAGE_*      │  SSE: text_delta          │                      │
    │  "OK, no files deleted"   │◀──────────────────────────│                      │
    │◀──────────────────────────│                           │                      │
    │  SSE: RUN_FINISHED        │  SSE: run_finished        │                      │
    │◀──────────────────────────│◀──────────────────────────│                      │
```

## 5. Event Translation Layer

```
    Hermes Event Server                    hermes_backend.py              Flutter (AG-UI)
    (raw SSE events)                       (translator)                   (camelCase JSON)
    ─────────────────                      ─────────────────              ──────────────────

    run_started         ──────────────▶    RUN_STARTED        ─────────▶ {"type":"RUN_STARTED",
                                                                          "threadId":"...","runId":"..."}

    step {iteration:1}  ──────────────▶    STEP_STARTED       ─────────▶ {"type":"STEP_STARTED",
                                           "Step 1/10"                     "stepName":"Step 1/10"}

    thinking "🧠..."    ──────────────▶    THINKING_START     ─────────▶ {"type":"THINKING_TEXT_MESSAGE_START",
                                           THINKING_CONTENT                "messageId":"...","role":"assistant"}

    thinking_end        ──────────────▶    THINKING_END       ─────────▶ {"type":"THINKING_TEXT_MESSAGE_END"}

    reasoning_delta     ──────────────▶    THINKING_CONTENT   ─────────▶ {"type":"THINKING_TEXT_MESSAGE_CONTENT",
    "The user wants..."                    (merged into                    "delta":"The user wants..."}
                                            thinking block)

    tool_start          ──────────────▶    TOOL_CALL_START    ─────────▶ {"type":"TOOL_CALL_START",
    {id, name, args}                       + TOOL_CALL_ARGS               "toolCallId":"...","toolCallName":"..."}
                                           + TOOL_CALL_END

    tool_result         ──────────────▶    TOOL_CALL_RESULT   ─────────▶ {"type":"TOOL_CALL_RESULT",
    {id, content}                                                         "toolCallId":"...","content":"..."}

    text_start          ──────────────▶    TEXT_MESSAGE_START  ─────────▶ {"type":"TEXT_MESSAGE_START",
                                                                          "messageId":"...","role":"assistant"}

    text_delta          ──────────────▶    TEXT_MESSAGE_       ─────────▶ {"type":"TEXT_MESSAGE_CONTENT",
    "Hello world"                          CONTENT                        "messageId":"...","delta":"Hello world"}

    text_end            ──────────────▶    TEXT_MESSAGE_END    ─────────▶ {"type":"TEXT_MESSAGE_END"}

    run_finished        ──────────────▶    STATE_SNAPSHOT     ─────────▶ {"type":"STATE_SNAPSHOT",
    {usage, session_id}                    + RUN_FINISHED                  "snapshot":{...}}
                                                                         {"type":"RUN_FINISHED"}

    run_error           ──────────────▶    _close_open_blocks ─────────▶ (close any THINKING/TEXT/STEP)
    {message}                              + RUN_ERROR                    {"type":"RUN_ERROR",
                                                                          "message":"..."}
```

## 6. State Round-Trip

```
    Run 1                                    Run 2
    ─────                                    ─────

    Flutter sends:                           Flutter sends:
    state: {}                                state: {
                                               hermes_session_id: "soliplex-hermes-abc123",
        │                                      artifacts: [],
        ▼                                      last_usage: {input: 50, output: 20},
                                               run_count: 1
    Soliplex extracts                        }
    session_id: null                             │
    → generates:                                 ▼
    "soliplex-hermes-{tid}"
        │                                    Soliplex extracts
        ▼                                    session_id: "soliplex-hermes-abc123"
                                             → passes to Hermes (continuity)
    Hermes runs with                             │
    new session                                  ▼
        │
        ▼                                    Hermes loads session
                                             from SessionDB
    STATE_SNAPSHOT emitted:                      │
    {                                            ▼
      hermes_session_id:
        "soliplex-hermes-abc123",            STATE_SNAPSHOT emitted:
      artifacts: [],                         {
      last_usage: {input: 50,                  hermes_session_id:
                   output: 20},                  "soliplex-hermes-abc123",
      run_count: 1                             artifacts: ["/tmp/script.py"],
    }                                          last_usage: {input: 80, output: 40},
        │                                      run_count: 2
        ▼                                    }
                                                 │
    Flutter stores state                         ▼
    for next run
                                             Flutter stores updated state
```

## 7. Docker Deployment

```
    docker-compose.yaml
    ════════════════════

    ┌─────────────────────────────────────────────────────────────────┐
    │  Docker Network                                                 │
    │                                                                 │
    │  ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐  │
    │  │  postgres     │    │  hermes      │    │  soliplex        │  │
    │  │              │    │              │    │  (optional,      │  │
    │  │  :5432       │    │  :8642       │    │   can run on     │  │
    │  │              │    │              │    │   host instead)  │  │
    │  │  healthcheck:│    │  healthcheck:│    │                  │  │
    │  │  pg_isready  │    │  curl /health│    │  depends_on:     │  │
    │  │              │    │              │    │   postgres ✓     │  │
    │  │  volume:     │    │  volume:     │    │   hermes ✓       │  │
    │  │  pgdata      │    │  ~/hermes-   │    │                  │  │
    │  │              │    │   data:/opt/ │    │  :8000           │  │
    │  │              │    │   data       │    │                  │  │
    │  └──────────────┘    └──────────────┘    └──────────────────┘  │
    │        ▲                     ▲                    │             │
    │        │                     │                    │             │
    │        │  thread persistence │  HTTP SSE          │             │
    │        └─────────────────────┼────────────────────┘             │
    │                              │                                  │
    └──────────────────────────────┼──────────────────────────────────┘
                                   │
                              ~/hermes-data/
                              (host volume)
                              ├── auth.json
                              ├── state.db
                              ├── memories/
                              │   ├── MEMORY.md
                              │   └── USER.md
                              ├── skills/ (74 skills)
                              └── config.yaml
```

## 8. Routing Split in views/agui.py

```
    POST /api/v1/rooms/{room_id}/agui/{thread_id}/{run_id}
                            │
                            ▼
                    ┌───────────────┐
                    │ Load room     │
                    │ config        │
                    └───────┬───────┘
                            │
                    ┌───────▼───────┐
                    │ agent_config  │
                    │ isinstance?   │
                    └───┬───────┬───┘
                        │       │
              HermesAgentConfig  │  AgentConfig / FactoryAgentConfig
                        │       │
                        ▼       ▼
        ┌───────────────────┐  ┌──────────────────────────────┐
        │ _hermes_agent_run │  │ Standard pydantic-ai path    │
        │                   │  │                              │
        │ 1. Parse body     │  │ 1. AGUIAdapter.from_request()│
        │ 2. Extract state  │  │ 2. add_run_input()           │
        │ 3. Extract tools  │  │ 3. run_stream(deps)          │
        │ 4. Build history  │  │ 4. compact_event_stream()    │
        │ 5. add_run_input()│  │ 5. drive_llm_stream()        │
        │ 6. Call Hermes    │  │ 6. encode_stream()           │
        │    event server   │  │ 7. SSE keepalive             │
        │ 7. Translate to   │  │                              │
        │    AG-UI events   │  │  (unchanged)                 │
        │ 8. drive_llm_     │  │                              │
        │    stream()       │  │                              │
        │ 9. SSE keepalive  │  │                              │
        └───────────────────┘  └──────────────────────────────┘
                │                              │
                └──────────┬───────────────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │ StreamingResponse│
                  │ text/event-stream│
                  └─────────────────┘
```
