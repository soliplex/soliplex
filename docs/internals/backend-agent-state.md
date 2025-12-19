# Backend Agent State Subsystem

## Overview
The Backend Agent State subsystem manages the lifecycle of the AI agent, its dependencies, and the state injection mechanism. It bridges the gap between the `soliplex` application context (users, tools, config) and the `pydantic-ai` agent execution model.

## Key Components

### 1. `AgentDependencies`
**File:** `src/soliplex/agents.py`

This class serves as the context container for every agent execution run. It implements the `pydantic-ai` **StateHandler** protocol.

*   **Type:** `dataclasses.dataclass` (Required for StateHandler compatibility)
*   **Fields:**
    *   `the_installation`: Reference to the global application configuration.
    *   `user`: The authenticated user profile.
    *   `tool_configs`: Configuration for available tools.
    *   `agui_emitter`: An emitter for sending events back to the client.
    *   `state`: **Critically**, this field holds the client-provided state.
        *   Type: `agui.AGUI_State` (alias for `dict[str, Any]`)
        *   Populated automatically by `pydantic-ai` from the `RunAgentInput`.

### 2. Dependency Injection
**File:** `src/soliplex/installation.py`

The `Installation.get_agent_deps_for_room` method constructs the `AgentDependencies` instance.

*   It injects the `AGUIEmitter` if a `RunAgentInput` is provided.
*   It ensures the `state` field is available for the agent runtime.

### 3. Agent Factory
**File:** `src/soliplex/agents.py`

*   `get_agent_from_configs`: Retrieves or creates `pydantic_ai.Agent` instances.
*   It configures the agent to use `AgentDependencies` as its `deps_type`.
*   This ensures that when `agent.run()` is called, the `ctx.deps` object is an instance of `AgentDependencies`.

## State Flow
1.  **Client Request:** The client sends a JSON payload including a `state` field (e.g., `{ "canvas": [...] }`).
2.  **Adapter:** `AGUIAdapter` extracts this state.
3.  **Injection:** `pydantic-ai` injects this dictionary into `AgentDependencies.state`.
4.  **Usage:** The agent (in tools or system prompts) accesses `ctx.deps.state` to read the client's context.

## Current Status
*   **Protocol Compliance:** The `AgentDependencies` class is correctly defined as a dataclass with a `state` field, satisfying the requirements to receive client state without crashing.
*   **Type Safety:** The state is currently a raw `dict`, meaning there is no validation of the state structure (e.g., checking if "canvas" exists or has the correct format).
