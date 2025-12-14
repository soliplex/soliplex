# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.
Update this file whenever there is a change in the project.

## Project Overview

A new, fully cross platform frontend project for the Soliplex AI-powered RAG system.

### Planning Files

```
planning/
├── client.md                - Pure Dart HTTP/AGUI client spec
├── core_frontend.md         - Flutter infrastructure spec
├── external_backend_service.md - Backend API reference
└── ui/                      - UI component specs
    ├── chat.md
    ├── history.md
    ├── detail.md
    ├── current_canvas.md
    └── permanent_canvas.md
```

### External Dependencies

- **Backend**: `../soliplex/` - Python FastAPI server with RAG, MCP, multi-room architecture
- **Reference Flutter clients**:
  - `../flutter/` - Original client with OIDC auth, maps, markdown
  - `../soliplex_flutter/` - Newer client with AG-UI protocol, 3-column layout

## Slash Commands

Use these commands for common tasks:

| Command | Description |
|---------|-------------|
| `/start-backend` | Start backend server on localhost:8000 |
| `/stop-backend` | Stop the backend server |
| `/test-flutter` | Run Flutter tests |
| `/lint` | Run code quality checks |
| `/api-docs` | View API documentation and endpoints |
| `/explore-backend` | Guide to backend architecture |
| `/explore-flutter` | Guide to existing Flutter patterns |

## Architecture

### 3-Layer Component Structure

1. **Client** (`planning/client.md`)
   - Pure Dart, minimal Flutter dependencies
   - HTTP/AGUI protocols for backend communication
   - Room/Thread/Run data management

2. **Core Frontend** (`planning/core_frontend.md`)
   - Flutter infrastructure using Client
   - Login, backend URL configuration, navigation
   - Provides plumbing for UI components

3. **UI Components** (`planning/ui/`)
   - Pluggable widgets using Core Frontend

### UI Components

| Component | Scope | Description |
|-----------|-------|-------------|
| **History** | Room | Thread list for current room |
| **Chat** | Thread | Messages, shows agent state, copy/pin to canvas |
| **Detail** | Thread | Event log, thinking, state |
| **CurrentCanvas** | Thread | Ephemeral ActivitySnapshot/StateSnapshot display |
| **PermanentCanvas** | Global | Persistent user-pinned items across rooms |

## Implementation Roadmap

Implementation order with dependencies:

```
┌─────────────────────────────────────────────────────────────────────┐
│  1. client (6 phases)                                               │
│     Pure Dart, no dependencies                                      │
└─────────────────────┬───────────────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────────────┐
│  2. core_frontend (3 phases)                                        │
│     Depends on: client                                              │
│     Note: Phase 2 must include ActiveRunNotifier extensions for     │
│           rawEvents, stateItems, currentActivity                    │
└─────────────────────┬───────────────────────────────────────────────┘
                      │
        ┌─────────────┼─────────────┬─────────────┐
        │             │             │             │
┌───────▼───────┐ ┌───▼───┐ ┌───────▼───────┐ ┌───▼───────────┐
│ 3a. history   │ │3b.chat│ │ 3c. detail    │ │3d.current_    │
│ (8 phases)    │ │(3 ph) │ │ (7 phases)    │ │   canvas (5)  │
│               │ │       │ │ Needs:        │ │ Needs:        │
│               │ │       │ │ ActiveRun     │ │ ActiveRun     │
│               │ │       │ │ extensions    │ │ extensions    │
└───────────────┘ └───┬───┘ └───────────────┘ └───────┬───────┘
                      │                               │
                      └───────────────┬───────────────┘
                                      │
                      ┌───────────────▼───────────────┐
                      │ 4. permanent_canvas (5 phases)│
                      │ Depends on: chat, current_    │
                      │             canvas            │
                      └───────────────────────────────┘
```

### Phase Counts by Component

| Component | Phases | Coverage Target |
|-----------|--------|-----------------|
| client | 6 | 85% |
| core_frontend | 3 | 85% |
| history | 8 | 85% |
| chat | 3 | 85% |
| detail | 7 | 85% |
| current_canvas | 5 | 85% |
| permanent_canvas | 5 | 85% |

### Implementation Notes

- **Parallel work**: After core_frontend Phase 2, history/chat/detail/current_canvas can proceed in parallel
- **ActiveRunNotifier extensions**: Must be completed in core_frontend Phase 2 before detail and current_canvas can fully function
- **CLAUDE.md updates**: Each component's final phase includes updating this file with new patterns and file structure

## Development Rules

Key rules from `~/.claude/RULES.md` that apply to this project:

**Code Quality**

- All functions must include concise, purpose-driven docstrings
- Implement structured error handling with specific failure modes
- Verify preconditions before critical operations
- Strictly follow flutter lint and analysis

**Design Philosophy**

- **KISS**: Straightforward solutions, avoid over-engineering
- **YAGNI**: Only immediate requirements, no speculative features
- **SOLID**: Single responsibility, dependency inversion

**Testing**

- All new logic must include unit and integration tests
- Code coverage should exceed 85%
- All tests must pass before deployment

**Security**

- No hardcoded credentials - use secure storage
- Validate and sanitize all inputs
- Follow principle of least privilege
