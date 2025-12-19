# Frontend State Provider Subsystem

## Overview
This subsystem manages the specific application state (e.g., the "Canvas") within the Flutter application. It is responsible for holding the data, updating the UI, and serializing the state for transmission to the backend agent.

## Key Components

### 1. `CanvasState` & `CanvasItem`
**File:** `lib/core/services/canvas_service.dart`

These classes define the data model for the Canvas feature.

*   **`CanvasItem`**: Represents a single widget on the canvas (ID, type, data).
    *   **Serialization:** `toJson()` returns `{'id': ..., 'widget': ..., 'data': ...}`.
    *   **Semantic IDs:** Uses a deterministic ID generation strategy (e.g., `staff-{id}`) to prevent duplicate widgets.
*   **`CanvasState`**: The collection of items.
    *   **Serialization:** `toJson()` returns `{'canvas': [item.toJson(), ...]}`. This defines the **implicit schema** expected by the backend.

### 2. `CanvasNotifier`
**File:** `lib/core/services/canvas_service.dart`

A Riverpod notifier that manages updates to the `CanvasState`.

*   **Server Scoping:** Extends `ServerScopedNotifier` to automatically reset state when switching servers.
*   **Operations:** Provides methods like `addItem`, `removeItem`, `updateItem` for the UI or Agents to modify state.
*   **Agent Interaction:** When the agent calls a tool like `canvas_render`, the implementation of that tool calls methods on this notifier.

### 3. State Injection
**File:** `lib/features/chat/chat_content.dart` (implied from investigation)

When sending a message:
1.  The app reads `ref.read(canvasProvider)`.
2.  It calls `toJson()` to get the `Map<String, dynamic>`.
3.  This map is passed to `AgUiService.chat(..., state: map)`.
4.  The `Thread` sends this map in the `state` field of the `RunAgentInput`.

## implicit Contract
The subsystem relies on an implicit contract with the backend:
*   **Key:** `"canvas"`
*   **Value:** List of objects with `id`, `widget`, `data`.

If the backend agent tries to read `state["whiteboard"]` or expects `data` to have a specific field, it will fail at runtime if this provider doesn't match.

## Current Status
*   **Serialization:** JSON-based serialization is implemented.
*   **Reactive:** UI updates automatically via Riverpod when state changes.
*   **Loose Coupling:** The "Canvas" logic is self-contained but tightly coupled to the specific string keys used in JSON.
