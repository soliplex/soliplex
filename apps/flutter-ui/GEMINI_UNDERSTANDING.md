# Gemini Understanding: AG-UI Dashboard 2 (GUI Layer)

This document outlines the understanding of the application's GUI layer based on a review of the source code.

## 1. Overview
The application is a Flutter-based dashboard for an "Agentic UI" (AG-UI) system. It allows users to interact with AI agents that can dynamically render native UI widgets (GenUI) within the chat stream.

**Tech Stack:**
*   **Framework:** Flutter (Material 3)
*   **State Management:** Riverpod (`flutter_riverpod`)
*   **Architecture:** Feature-based folder structure with a core registry pattern for dynamic widgets.

## 2. UI Entry & Navigation
*   **Entry Point (`lib/main.dart`):** Initializes `AgUiDashApp` wrapped in a `ProviderScope`. It sets up the `MaterialApp` with light and dark themes based on a blue seed color.
*   **App Shell (`lib/app_shell.dart`):** Acts as the main controller for the app's lifecycle. It uses a state machine pattern (via `appStateStreamProvider`) to handle:
    *   Server Connection Setup
    *   Authentication
    *   Initialization
    *   Navigation to the main `ChatScreen`.

## 3. The GenUI System


### 3.1 Architecture
The "GenUI" system allows the backend (Agent) to specify a widget by name and provide data for it. The client maps this name to a native Flutter widget.

1.  **Widget Registry (`lib/core/services/widget_registry.dart`):**
    *   A service that maintains a map of `String` (widget name) to `WidgetBuilder` functions.
    *   Default widgets are registered at startup (e.g., `InfoCard`, `MetricDisplay`, `SkillsCard`).
    *   Exposed via `widgetRegistryProvider`.

2.  **Factory Pattern (`lib/widgets/registry/*`):**
    *   Each registered widget (e.g., `InfoCardWidget`) implements a static `fromData` factory method.
    *   **Signature:** `Widget fromData(Map<String, dynamic> data, Function? onEvent)`.
    *   **Parsing:** Uses `widget_utils.dart` to safely parse types (e.g., `parseColor` for hex/int colors, `parseIcon` for code points).

3.  **Rendering (`lib/features/chat/widgets/genui_message_widget.dart`):**
    *   Takes a `GenUiContent` object (containing `widgetName` and `data`).
    *   Lookups the builder in `WidgetRegistry`.
    *   If found, builds the widget.
    *   If not found, renders a fallback "Unknown Widget" card for debugging.

### 3.2 Example Flow
1.  **Agent** sends: `{ "widget_name": "InfoCard", "data": { "title": "Hello" } }`
2.  **App** receives this as a `ChatMessage` of type `genUi`.
3.  **GenUiMessageWidget** calls `registry.build('InfoCard', data)`.
4.  **WidgetRegistry** executes `InfoCardWidget.fromData(data)`.
5.  **InfoCardWidget** parses data and returns a native `Card` widget.

## 4. Chat Interface
The chat UI is the primary interaction surface.

*   **Message Bubble (`lib/features/chat/widgets/chat_message_bubble.dart`):**
    *   The central dispatcher for rendering messages.
    *   Uses a `switch` statement on `message.type` to decide rendering strategy.
    *   **Text Messages:** Renders markdown (`StreamingMarkdownWidget`) and optional "Thinking" or "Tool Call" sections.
    *   **GenUI Messages:** Delegates to `GenUiMessageWidget`.
    *   **Action Row:** Provides "Copy" and "Send to Canvas" functionality.

*   **Canvas Integration:**
    *   Messages (text or GenUI) can be sent to a "Canvas" side panel.
    *   For GenUI messages, the widget data is passed directly.
    *   For Text messages, a `CanvasContentService` attempts to "analyze" the text to convert it into a widget format.

## 5. State Management & Theming
*   **Riverpod:** Used exclusively for state. Providers are typically scoped globally or per-feature. `ConsumerWidget` is the standard for UI components.
*   **Theming:** The app uses standard Material 3 design tokens (`Theme.of(context).colorScheme`). There is no custom styling language; it relies on the Flutter theme system.

## 6. Layout & Responsiveness
The application supports multiple layouts to adapt to different screen sizes or user preferences, found in `lib/features/layouts`.

*   **Standard Layout (`StandardLayout`):**
    *   A single-column view dedicated to the `ChatContent`.
    *   Typically used for mobile devices or simple focus mode.

*   **Three-Column Layout (`ThreeColumnLayout`):**
    *   Designed for desktop/large screens.
    *   **Left Column:** Thread History (interactive list of past conversations).
    *   **Middle Column:** Main `ChatContent` (flexible width).
    *   **Right Column:** `ContextPane` (shows active state, tool results, etc.).

## 7. Chat Content & Interaction Logic
The `ChatContent` widget (`lib/features/chat/chat_content.dart`) is the orchestrator of the chat experience.

*   **Message Orchestration:**
    *   Subscribes to `connectionManagerProvider` to get the single source of truth for messages.
    *   Handles sending messages via `connectionManager.chat()`.
    *   Implements local "Slash Commands" (e.g., `/search`, `/canvas`, `/demo`) which are processed client-side without hitting the server.

*   **UI Tool Handling:**
    *   The backend can invoke "UI Tools" like `genui_render` and `canvas_render`.
    *   `ChatContent` intercepts these tool calls via a `uiToolHandler` callback passed to the connection manager.
    *   **`genui_render`**: Adds a specialized `GenUiContent` message to the chat stream.
    *   **`canvas_render`**: Directs the `activeCanvasNotifierProvider` to add or update items in the side panel.

## 8. Features: Canvas & Side Panels
The "Canvas" and "Context Pane" are persistent side panels (or separate views) that augment the chat.

*   **Canvas View (`lib/features/canvas/canvas_view.dart`):**
    *   Watches `canvasProvider` for a list of `CanvasItem` objects.
    *   Uses the same `WidgetRegistry` as the chat to render content.
    *   Wraps each item in a `_CanvasItemCard` that provides a standard header and a "Remove" button.
    *   Allows long-lived widgets (like a dashboard metric or a note) to persist outside the linear chat history.

*   **Context Pane Logic (`lib/core/services/context_pane_service.dart`):**
    *   Powered by `ContextPaneNotifier`, which listens to a stream of events from the `RoomSession`.
    *   Aggregates diverse events: `state_snapshot` (backend state), `tool_result`, `genui_render`, and even standard text messages.
    *   Provides a "Debugging / Inspector" view of the conversation's internal state, useful for understanding *why* the agent did something.

## 9. Summary
The application is a sophisticated "Chat + GUI" hybrid. It moves beyond simple text by treating UI widgets as first-class citizens in the conversation. The Agent acts as a "UI Composer," sending high-level intent (`widget_name` + `data`), which the Flutter client translates into performant, native components via a registry system.
