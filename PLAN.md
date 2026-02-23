# Plan: Soliplex–Moodle Workplace Integration

## Context

Soliplex (AMIA JOSCE) needs to query Moodle Workplace for course, enrollment, and completion data so an AI agent can answer questions about training status. A Docker-based Moodle Workplace 5.0.2 sandbox exists at `/Users/ryan.day/Dev/moodle_sandbox/` with test data (courses, users, completions, two custom report plugins).

The user plans **multiple system integrations** over time, so we need a repeatable pattern — not one-off code.

## Architectural Decision: FastMCP Server

**Approach**: Build a standalone Python FastMCP server (`moodle-mcp-tools`) that wraps Moodle's REST Web Services API. Soliplex consumes it via its existing `mcp_client_toolsets` config.

**Why this approach**:
- **Pydantic AI standard** — `FastMCPToolset` is the recommended way to integrate external services
- **Zero Soliplex code changes** — Soliplex already supports stdio/HTTP MCP client toolsets in room configs
- **Reusable** — Any MCP client (Claude Desktop, other agents) can use the same server
- **Repeatable pattern** — Each future integration (ATAAPS, DTS, etc.) follows the same pattern: standalone MCP server + Soliplex room config
- **Clean separation** — Moodle-specific code lives in its own repo/package, not in Soliplex

## Instance-Agnostic Design

The MCP server connects to **any** Moodle Workplace instance — not just the local sandbox. Configuration is purely via environment variables:

- `MOODLE_BASE_URL` — local sandbox (`http://localhost:9000`), SOF LMS, or any other instance
- `MOODLE_API_TOKEN` — instance-specific web service token

## Scope: Read-Only (Phase 1)

Initial tools query Moodle — no mutations.

## What Was Built

### 1. New repo: `moodle-mcp-tools/` (`/Users/ryan.day/Dev/moodle-mcp-tools/`)

- `pyproject.toml` — FastMCP + httpx deps
- `src/moodle_mcp/server.py` — FastMCP server with 6 tools
- `src/moodle_mcp/client.py` — Async httpx Moodle REST API client
- `src/moodle_mcp/models.py` — Pydantic response models
- `src/moodle_mcp/__main__.py` — `python -m moodle_mcp` entry point
- `tests/test_client.py` — 12 unit tests with mocked HTTP (all passing)

### 2. MCP Tools

| Tool | Moodle WS Function | Description |
|------|---------------------|-------------|
| `list_courses` | `core_course_get_courses` | List all courses with metadata |
| `search_courses` | `core_course_get_courses_by_field` | Search courses by name/ID/shortname |
| `get_enrolled_users` | `core_enrol_get_enrolled_users` | List users enrolled in a course |
| `get_course_completion` | `core_completion_get_course_completion_status` | Course-level completion for a user |
| `get_activity_completion` | `core_completion_get_activities_completion_status` | Activity-level completion for a user in a course |
| `get_user_info` | `core_user_get_users_by_field` | Look up user by username/email/ID |

### 3. Soliplex Changes (feature/moodle branch)

- `example/rooms/moodle/room_config.yaml` — New room config
- `example/minimal.yaml` — Added room path + 2 secrets (MOODLE_BASE_URL, MOODLE_API_TOKEN)
- `tests/unit/test_moodle_room.py` — Unit test verifying room config loads

## Remaining Manual Steps

### Moodle Admin Setup (one-time, in browser)

1. Change Moodle sandbox port to 9000: `export MOODLE_DOCKER_WEB_PORT=9000`
2. Enable web services: Site Admin > Advanced features > Enable web services
3. Enable REST protocol: Site Admin > Plugins > Web services > Manage protocols
4. Create external service with the 6 core functions
5. Create a token for the admin user
6. Set env vars: `MOODLE_BASE_URL=http://localhost:9000` and `MOODLE_API_TOKEN=<token>`

### End-to-End Verification

1. Start Moodle sandbox (port 9000) + Soliplex (port 8000)
2. Chat with the Moodle room: "What courses are available?"
3. Verify completion queries return test data

## Phase 2 Notes (not in scope)

- Custom report plugins (`report_utm`, `report_adv_comp`) web service functions
- Write-back tools (enroll users, mark completions, reset progress)
