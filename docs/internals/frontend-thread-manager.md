# Frontend Thread Manager Subsystem

## Overview
The Frontend Thread Manager is the core engine on the Flutter client that drives the conversation loop. It handles network communication, message history, tool execution, and state synchronization.

## Key Components

### 1. `Thread` Class
**File:** `lib/infrastructure/quick_agui/thread.dart`

The `Thread` class is the central controller for a single conversation thread.

*   **Responsibilities:**
    *   **Network Transport:** Manages the connection to the backend via `_runAgentDelegate`.
    *   **Event Loop:** Consumes the SSE stream (`startRun`) and dispatches events.
    *   **State Management:** Holds the `currentState` and exposes it via `stateStream`.
    *   **Tool Registry:** Tracks client-side tools and handles their execution.

### 2. Event Handling Loop
The `startRun` method contains the main `await for` loop that processes incoming SSE events:

*   **Text Handling:** Buffers text chunks (`TextMessageChunkEvent`) into `TextMessageBuffer` to handle out-of-order or fragmented delivery.
*   **Tool Handling:**
    *   Buffers tool call arguments (`ToolCallArgsEvent`).
    *   On `ToolCallEndEvent`, registers the call in `_toolRegistry`.
    *   After the stream closes, it **executes** pending client-side tools via `_executeClientTools`.
*   **State Handling:**
    *   `StateSnapshotEvent`: Replaces the current state.
    *   `StateDeltaEvent`: Merges updates into the current state (simple Map merge).

### 3. Tool Execution
**File:** `lib/infrastructure/quick_agui/thread.dart`

*   **Registry:** `ToolCallRegistry` tracks which tools need to be called.
*   **Execution:** `_executeClientTools` invokes the registered `ToolExecutor` (e.g., `canvas_render`).
*   **Loop:** After tools execute, `sendToolResults` calls `startRun` again, sending the results back to the server to continue the conversation.

### 4. Client-Side Tools
The `Thread` supports "Fire-and-Forget" tools (e.g., UI rendering commands) via `addTool(..., fireAndForget: true)`. These execute but do not trigger a new server round-trip, optimizing latency for UI updates.

## Current Status
*   **Robustness:** Handles network timeouts and cancellation gracefully.
*   **State Sync:** Implements basic state merging (Map-based).
*   **Tooling:** Supports both bidirectional (calculator) and unidirectional (render) tools.
