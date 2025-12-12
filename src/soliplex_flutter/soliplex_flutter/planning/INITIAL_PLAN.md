---
Best practices:
I want initial bare minimum flutter app, that is fully cross platform.
Following community best practices, strict lint.
Automated testing framework.
Analyzer configured in the pubspec to configured to lint for everything.
---

# Implementation Plan: Soliplex Flutter Client

This plan provides an incremental, modular approach to building the Flutter frontend as described in CLAUDE.md.

Refer to /Users/jaeminjo/enfold/Soliplex-planning as reference. These are information extracted from previous versions of prototype.
Put heaviest weight to the planning files in the current directory, then the files in /Users/jaeminjo/enfold/Soliplex-planning/new_dash_2, then everything else.

## Overview

Build a Flutter client with 2 components:

1. a client that interacts with the backend through http and agui protocols. (will refer to as `Soliplex Client` or `Client`)
  1.a Want this to be as little flutter UI code as possible, so it will be possible to test in isolation
2. a flutter frontend that utilizes all the features provided by the backend. (will refer to as `Soliplex Frontend` or `Frontend`)

## Backend features

### Endpoints

- `GET /docs` - API documentation
- `GET /v1/rooms` - List all available rooms
- `GET /api/v1/rooms/{room_id}/agui` - List threads in a room
- `GET /api/v1/rooms/{room_id}/agui/{thread_id}` - Get info about a specific thread,  
- `GET /api/v1/rooms/{room_id}/agui/{thread_id}/{run_id}` - Get info about a specific run,  
- `POST /api/v1/rooms/{room_id}/agui` - Start a new thread, and use the returned thread_id and initial run_id
- `POST /api/v1/rooms/{room_id}/agui/{thread_id}/{run_id}` - Execute a run
- `POST /api/v1/rooms/{room_id}/agui/{thread_id}` - Create a new run in a thread (before executing it)
- `POST /api/v1/rooms/{room_id}/agui/{thread_id}/meta` - Add metadata (name, description) to a thread
- `POST /api/v1/rooms/{room_id}/agui/{thread_id}/{run_id}/meta` - Add metadata (label) to a run
- `DELETE /api/v1/rooms/{room_id}/agui/{thread_id}` - Delete a thread

## Requirements

### Client

- Be able to handle http(s) and agui protocols
  - refer to <https://docs.ag-ui.com/introduction> for agui documentation
  - refer to the AGUI SDK library listed below, but feel free to use anything else, or make modifications:
    - `ag_ui` from `https://github.com/soliplex/ag-ui.git` (path: `sdks/community/dart`)
  - refer to below list of dart code for handling the agui, but feel free to modify:
    - `../flutter/lib/infrastructure/quick_agui/thread.dart`
    - `../flutter/lib/infrastructure/quick_agui/run.dart`
    - `../flutter/lib/infrastructure/quick_agui/text_message_buffer.dart`
    - `../flutter/lib/infrastructure/quick_agui/tool_call_reception_buffer.dart`
    - `../flutter/lib/infrastructure/quick_agui/tool_call_registry.dart`
- Be able to retrieve all room information
- From the room, capture all threads relevant to the room
- From the thread, capture all runs in the thread
- From the run, capture all history in the run
- Be able to create new threads, create new runs, and execute runs
- Be able to interact with all backend endpoints
- Be able to configure to different urls (default to <http://localhost:8000>)

### Frontend

- Be able to represent all items captured / received by the client with widgets
- Be able to interact with and utilize all client features through the represented widgets

#### Frontend components

Each of these components will be a widget that encapsulates the functionalities I need from the frontend.
These components can be a reference point, for future discussion to enhance the system.

- `Chat` widget:

  Each user message will start a new run. If a response to these run include tool calls intended for client to perform, the client will perform the tool calls, and start new run with the tool call results.
  The chat view could include messages (of type text / video / audio / image / interactive widget items) sent by the user or the backend server agents.
  The scope of the chat is limited to a run. Everytime a different run is specified, the chat will change to reflect the messages of that run.
  
  - Refer to the libraries below, but feel free to use anything else, or write your own:
    - `flutter_chat_ui: ^2.0.0`
    - `flutter_chat_core: ^2.0.0`
    - `dash_chat_2: ^0.0.21`

- `CurrentCanvas` widget:

  This canvas will represent the shared state between the frontend and the backend server.
  Stream / receive all `ActivitySnapshot` events, and `StateSnapshot` events and display and update them here automatically.
  The items here are ephemeral, and only hold the current state.
  This canvas scope is limited to a run. Everytime a different run is specified, the canvas will change to reflect the state of that run.

- `PermanentCanvas` widget:

  This canvas will hold items explicitly specified by the user to keep in this canvas. The items will persist app shutdown and show up on the next app start.
  This canvas scope will be across threads and rooms - item additions from any room / thread will be added here.

- `History` widget:
  
  This widget displays widgets to represent threads in each room. Whenever user specifies a different room, this widget's contents will change to reflect the threads in that room.

- `Details` widget:

  This widget displays all the events, runs, thinking, and state in the selected thread. Whenever user specifies a different thread, this widget will update it self to reflect the correct detail.

##### Initial thoughts on the frontend layout

- **Left (1/4)**: History panel - thread list for current room (collapsible)
- **Center (3/4)**: Canvas panel - `CurrentCanvas` and `PermanentCanvas` selectable through tabs
- **Right (collapsible)**: Split vertically into Details (top) and Chat (bottom)

┌─────────┬───────────────────────┬─────────────┐
│         │                       │  Details    │
│ History │       Canvas          │─────────────│
│  (1/4)  │       (3/4)           │    Chat     │
│         │                       │             │
└─────────┴───────────────────────┴─────────────┘

### For every iteration of development

- Be very careful to always put in the best design choice possible in terms of robustness, performance efficiency, readability, and ease of future modification.
- Keep unit test coverage of at least 80%, preferably 100%, and make sure they pass after any development.
- Document the current state of the system, and keep it updated.
- Always enforce the linter strictly.
