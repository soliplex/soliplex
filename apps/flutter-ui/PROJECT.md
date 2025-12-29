# PROJECT.md - AG-UI Dashboard Implementation

## Project Overview

AG-UI Dashboard - A Flutter chat application with native widget rendering for Agentic Generative UI.

**Architecture Summary:**
- **AG-UI Protocol**: Standardized SSE communication between AI agent and Flutter client
- **Dash Chat 2**: Manages conversation flow, message history, and user input
- **Native Widget Registry**: Type-safe Flutter widgets rendered via `genui_render` tool

---

## Current Status

### Completed:
- [x] Project foundation with Flutter, Riverpod, Dash Chat 2
- [x] AG-UI SSE streaming with 2-step endpoint flow
- [x] Native widget registry system (InfoCard, MetricDisplay, DataList, etc.)
- [x] Local tool calling framework (`get_my_location` GPS tool)
- [x] `genui_render` tool for rendering widgets in chat
- [x] `canvas_render` tool for rendering widgets on canvas
- [x] Room selector dropdown
- [x] Thread history panel
- [x] Multiple layout modes (Standard, Canvas, ThreeCol)

### Available Widgets:
| Widget | Purpose |
|--------|---------|
| `InfoCard` | Display info with title, subtitle, icon |
| `MetricDisplay` | Show metric with label, value, unit, trend |
| `DataList` | List of key-value pairs |
| `ErrorDisplay` | Error message display |
| `LoadingIndicator` | Loading spinner |
| `ActionButton` | Clickable button |
| `ProgressCard` | Progress bar with percentage |
| `LocationCard` | GPS coordinates display (no map) |

### Remaining Work:
1. **GIS Map Widget** - OpenStreetMap view for location display
2. **Human-in-the-loop** - Send widget events back to agent
3. **Security** - Input validation, sandboxing
4. **Testing** - Unit, widget, integration tests

---

## Server Endpoint Flow (2-Step)

### Step 1: Create Thread
```
POST /api/v1/rooms/{room_id}/agui
Body: {}
Response: { "thread_id": "uuid", "runs": { "run_id": {...} } }
```

### Step 2: Execute Run (SSE Stream)
```
POST /api/v1/rooms/{room_id}/agui/{thread_id}/{run_id}
Content-Type: application/json
Accept: text/event-stream
Body: {
  "thread_id": "...",
  "run_id": "...",
  "messages": [...],
  "tools": [...],
  "forwardedProps": {}
}
```

---

## Key Files

| File | Purpose |
|------|---------|
| `lib/main.dart` | App entry point |
| `lib/core/services/agui_service.dart` | AG-UI SSE connection |
| `lib/core/services/chat_service.dart` | Message state |
| `lib/core/services/local_tools_service.dart` | Local tool execution |
| `lib/core/services/widget_registry.dart` | Widget factory |
| `lib/widgets/registry/*.dart` | Native widget implementations |
| `lib/features/chat/chat_screen.dart` | Main chat UI |

---

## Dependencies

```yaml
dependencies:
  flutter: sdk: flutter
  ag_ui: path: ../../../ag-ui/sdks/community/dart
  dash_chat_2: ^0.0.21
  flutter_riverpod: ^2.6.1
  fl_chart: ^0.69.2
  flutter_svg: ^2.0.17
  cached_network_image: ^3.4.1
  http: ^1.2.2
  uuid: ^4.5.1
  equatable: ^2.0.7
  geolocator: ^13.0.2
```
