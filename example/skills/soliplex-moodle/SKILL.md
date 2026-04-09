---
name: soliplex-moodle
description: Interact with a Moodle Workplace room on a Soliplex server — courses, users, org structure, certifications, programs, dynamic rules, and reporting via the AG-UI conversational protocol
---

# Soliplex Moodle Consumer

This skill teaches you how to interact with a Soliplex server's Moodle Workplace room as an external consumer. Through the AG-UI protocol (REST + Server-Sent Events), you can query and manage an entire Moodle Workplace instance: courses, users, organizational structure, certifications, learning programs, dynamic rules, and reporting.

This skill is self-contained. You do not need the generic `soliplex-client` skill.

## Connection

The Soliplex server URL is provided by the user or read from the `SOLIPLEX_URL` environment variable. All API endpoints are prefixed with `/api`. The versioned API lives at `/api/v1`.

### Authentication

Soliplex supports two modes:

**No-auth mode** (development/demo): No token required. All API calls work without an `Authorization` header.

**OIDC mode** (production): Requires a Bearer token in the `Authorization` header.

To authenticate with OIDC:

1. Discover available providers:

```bash
curl ${SOLIPLEX_URL}/api/login
```

Response: a dict of provider objects, each with `id`, `title`, `server_url`, `client_id`, and optionally `scope`.

2. Obtain a token via the OIDC password grant:

```bash
curl -X POST "${PROVIDER_SERVER_URL}/protocol/openid-connect/token" \
  -d "client_id=${CLIENT_ID}" \
  -d "grant_type=password" \
  -d "username=${USERNAME}" \
  -d "password=${PASSWORD}"
```

Response includes `access_token`, `refresh_token`, `expires_in`, `refresh_expires_in`.

3. Use the access token on all subsequent requests:

```bash
-H "Authorization: Bearer ${ACCESS_TOKEN}"
```

If the token is already known, it can be set in the `SOLIPLEX_ACCESS_TOKEN` environment variable.

### Token Refresh

Access tokens expire after `expires_in` seconds. For long-running automations, refresh the token before it expires:

```bash
curl -X POST "${PROVIDER_SERVER_URL}/protocol/openid-connect/token" \
  -d "client_id=${CLIENT_ID}" \
  -d "grant_type=refresh_token" \
  -d "refresh_token=${REFRESH_TOKEN}"
```

Response includes a new `access_token` and `refresh_token`.

## Room Discovery and Targeting

### Discover Available Rooms

The Moodle room ID may vary by installation. Discover rooms with:

```bash
curl ${SOLIPLEX_URL}/api/v1/rooms
```

Returns a dict of room objects keyed by room ID. Look for the room with a Moodle Workplace description. The default room ID is `moodle-tools`.

### The Moodle Workplace Room

The `moodle-tools` room is a training management assistant backed by the Moodle Workplace LMS. It has 100 tools organized into 7 skill domains. You interact with it by sending natural-language requests through the AG-UI conversational protocol — you do not call individual tools directly.

The room internally routes your request to the appropriate skill domain, calls the relevant Moodle Web Service APIs, and returns a natural-language response.

MCP tool access is not available for this room. Use the AG-UI protocol described below.

## Moodle Capabilities

The Moodle room covers 7 skill domains. When you send a request, the room's agent routes it to the appropriate domain automatically.

### Courses (19 tools)

Manage courses, categories, enrollments, completion tracking, grades, calendar events, and groups.

- List all courses and discover course IDs
- View course contents (sections, activities, modules)
- List enrolled users and check completion status
- Get bulk completion overview across all users in a course
- View user grades and assignment scores
- List course groups, cohort memberships, and upcoming events
- Create, update, delete, and duplicate courses
- Create course categories
- Enroll users into courses

### Users (9 tools)

Manage user accounts, messaging, and tenant assignments.

- Look up users by name, username, or email
- Create, update, and delete user accounts
- Suspend and unsuspend users
- Send messages to users
- List and assign users to organizational tenants

### Organisation (15 tools)

Manage the Moodle Workplace organizational hierarchy: departments, positions, job assignments, and manager relationships.

- List departments and positions
- View team members by department or position
- Create, update, and delete departments and positions
- Assign users to jobs (department + position)
- Set and remove manager relationships
- Query valid parent departments/positions for hierarchy moves

### Certifications (13 tools)

Manage certification lifecycle, allocations, and audit trails.

- List and search certifications
- View certification allocations and user certification history
- Certify users and revoke certifications
- Deallocate users from certifications (individual and bulk)
- Lifecycle: **Active -> Archive -> Delete (permanent)** or **Archive -> Restore -> Active**
- Certifications must be archived before they can be deleted or restored

### Programs (19 tools)

Manage learning programs (structured learning paths), the course catalogue, and competencies.

- Search programs and view program content (courses inside)
- Browse the learning catalogue and view user enrollments
- List competency frameworks, learning plans, and user competencies
- Allocate and deallocate users from programs (individual and bulk)
- Reset program progress for users
- Duplicate programs and control program visibility
- Lifecycle: **Active -> Archive -> Delete (permanent)** or **Archive -> Restore -> Active**
- Programs must be archived before they can be deleted or restored

### Dynamic Rules (14 tools)

Manage the Moodle Workplace automation engine. Dynamic rules automatically assign actions (enroll in course, add to cohort, grant competency) when users match conditions.

- List rules by name, ID, or status
- Check if a rule meets prerequisites for enabling
- View users currently matching a rule and historically matched users
- Search cohorts and competencies available for rule conditions/outcomes
- Enable, disable, archive, unarchive, delete, and duplicate rules
- Remove individual conditions or outcomes from a rule
- Rules can be referenced by name or ID
- Lifecycle: **Disabled -> Enable -> Enabled -> Disable -> Disabled -> Archive -> Archived -> Unarchive or Delete (permanent)**

### Reporting (11 tools)

Access Report Builder custom reports, UTM and Advanced Completion reports, and Workplace data import/export.

- List available Report Builder reports and retrieve report data (paginated)
- Run UTM completion reports by department
- Run Advanced Completion reports
- Export Workplace data (start export, poll status, download)
- Import Workplace data from export files
- Clean up completed exports and imports

## AG-UI Conversation Protocol

Conversations use the AG-UI protocol. The flow is: **create a thread** -> **create a run** -> **execute the run** (streaming) -> **parse SSE events**.

### Create a Thread

Start a new conversation by creating a thread. This also creates the initial (empty) run:

```bash
curl -X POST ${SOLIPLEX_URL}/api/v1/rooms/moodle-tools/agui \
  -H "Content-Type: application/json" \
  -d '{"metadata": {"name": "Training compliance check"}}'
```

Response:

```json
{
  "room_id": "moodle-tools",
  "thread_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
  "created": "2025-01-01T00:00:00Z",
  "metadata": {"name": "Training compliance check", "description": null},
  "runs": {
    "11111111-2222-3333-4444-555555555555": {
      "thread_id": "aaaaaaaa-...",
      "run_id": "11111111-...",
      "parent_run_id": null,
      "run_input": {
        "thread_id": "aaaaaaaa-...",
        "run_id": "11111111-...",
        "state": {},
        "messages": [],
        "tools": [],
        "context": [],
        "forwarded_props": null
      },
      "events": [],
      "metadata": null,
      "usage": null
    }
  }
}
```

Extract `thread_id` and the single `run_id` from the `runs` dict. The `run_input.state` contains the initial AG-UI feature state — **preserve it and pass it back on every run execution**.

### Execute a Run (Send a Message)

POST a `RunAgentInput` to the run endpoint. The response is an SSE stream of AG-UI events.

```bash
curl -X POST ${SOLIPLEX_URL}/api/v1/rooms/moodle-tools/agui/{thread_id}/{run_id} \
  -H "Content-Type: application/json" \
  -d '{
    "threadId": "aaaaaaaa-...",
    "runId": "11111111-...",
    "state": {},
    "messages": [
      {"id": "user_001", "role": "user", "content": "What courses are available?"}
    ],
    "tools": [],
    "context": [],
    "forwardedProps": {}
  }'
```

**Critical: Message Accumulation**

You MUST include all prior messages in the `messages` array for each run. The server does not maintain message history across runs — the client is responsible for accumulating the conversation.

For each turn:
1. Append the user's new message with `role: "user"` and an incrementing ID (`user_001`, `user_002`, etc.)
2. After receiving the response, append the assistant's reply with `role: "assistant"` (`assistant_001`, `assistant_002`, etc.)
3. On the next turn, send all accumulated messages

**Field names use camelCase** in JSON (`threadId`, `runId`, `forwardedProps`), matching the AG-UI protocol specification.

### Create a Follow-Up Run

For subsequent messages in the same thread, create a new run first:

```bash
curl -X POST ${SOLIPLEX_URL}/api/v1/rooms/moodle-tools/agui/{thread_id} \
  -H "Content-Type: application/json" \
  -d '{}'
```

Response includes a new `run_id` and `parent_run_id`. Then execute this new run with the full accumulated message history.

### Parsing the SSE Stream

The response is a Server-Sent Events stream. Each line is either:
- A comment starting with `:` — keepalive, ignore it
- A data line starting with `data: ` — strip the prefix and JSON-parse the remainder

Each event is a JSON object with a `type` field.

**Text response events** — assemble these to build the agent's reply:

| Event Type | Key Fields | Description |
|---|---|---|
| `TEXT_MESSAGE_START` | `messageId` | Response text begins |
| `TEXT_MESSAGE_CONTENT` | `messageId`, `delta` | Text chunk — append `delta` to build the response |
| `TEXT_MESSAGE_END` | `messageId` | Response text complete |

**Tool call events** — the agent using Moodle tools internally (informational):

| Event Type | Key Fields | Description |
|---|---|---|
| `TOOL_CALL_START` | `toolCallId`, `toolCallName` | Tool invocation begins |
| `TOOL_CALL_ARGS` | `toolCallId`, `delta` | Tool argument chunk |
| `TOOL_CALL_END` | `toolCallId` | Tool call complete |
| `TOOL_CALL_RESULT` | `toolCallId`, `result` | Tool result |

**Lifecycle events**:

| Event Type | Description |
|---|---|
| `RUN_STARTED` | Run begins |
| `RUN_FINISHED` | Run completed successfully — **stop reading** |
| `RUN_ERROR` | Run failed — **stop reading**, report the `message` field |
| `STEP_STARTED` | Processing step begins |
| `STEP_FINISHED` | Processing step ends |

Other event types (`STATE_SNAPSHOT`, `STATE_DELTA`, `ACTIVITY_SNAPSHOT`, `ACTIVITY_DELTA`, `THINKING_*`) may appear and can be safely ignored for basic consumption.

### Assembling a Response

```
: keepalive                              <- ignore
data: {"type": "RUN_STARTED"}           <- run begins
data: {"type": "TEXT_MESSAGE_START", "messageId": "msg_1"}
data: {"type": "TEXT_MESSAGE_CONTENT", "messageId": "msg_1", "delta": "Here are the "}
data: {"type": "TEXT_MESSAGE_CONTENT", "messageId": "msg_1", "delta": "available courses:\n\n"}
data: {"type": "TEXT_MESSAGE_CONTENT", "messageId": "msg_1", "delta": "1. Safety Fundamentals\n2. Cybersecurity Basics"}
data: {"type": "TEXT_MESSAGE_END", "messageId": "msg_1"}
data: {"type": "RUN_FINISHED"}          <- done
```

Assembled text: "Here are the available courses:\n\n1. Safety Fundamentals\n2. Cybersecurity Basics"

After assembling, add to the accumulating messages array:

```json
{"id": "assistant_001", "role": "assistant", "content": "Here are the available courses:\n\n1. Safety Fundamentals\n2. Cybersecurity Basics"}
```

### Error Handling

- **HTTP 404**: Invalid room ID, thread ID, or run ID
- **HTTP 401/403**: Authentication failure (OIDC mode)
- **`RUN_ERROR` SSE event**: The agent encountered an error during execution. The `message` field contains details. Stop reading the stream.
- **Moodle API errors**: Surfaced as text in the agent's normal response (e.g., "Error: Course not found"). These are NOT HTTP errors — the run still completes with `RUN_FINISHED`.

### Complete Two-Turn Example

**Turn 1 (new conversation):**

1. Create thread: `POST /api/v1/rooms/moodle-tools/agui` with `{"metadata": {"name": "Compliance check"}}` -> get `thread_id`, `run_id`, `state`
2. Execute run: `POST /api/v1/rooms/moodle-tools/agui/{thread_id}/{run_id}` with:
   ```json
   {"threadId": "...", "runId": "...", "state": {}, "messages": [{"id": "user_001", "role": "user", "content": "Who hasn't completed Safety Fundamentals?"}], "tools": [], "context": [], "forwardedProps": {}}
   ```
3. Parse SSE -> assemble response text (e.g., "Bob Smith and Carol Williams have not completed...")
4. Store: `messages = [user_001, assistant_001]`

**Turn 2 (follow-up):**

1. Create new run: `POST /api/v1/rooms/moodle-tools/agui/{thread_id}` with `{}` -> get new `run_id`
2. Execute run with accumulated messages:
   ```json
   {"threadId": "...", "runId": "...", "state": {}, "messages": [{"id": "user_001", "role": "user", "content": "Who hasn't completed Safety Fundamentals?"}, {"id": "assistant_001", "role": "assistant", "content": "Bob Smith and Carol Williams have not completed..."}, {"id": "user_002", "role": "user", "content": "Enroll them both in the Cybersecurity Basics course too"}], "tools": [], "context": [], "forwardedProps": {}}
   ```
3. Parse SSE -> this triggers the write confirmation flow (see below)

## Write Confirmation Flow

All write operations in the Moodle room use a two-stage preview/confirm pattern. This applies to any operation that creates, updates, or deletes data: enrollments, user creation, department changes, program lifecycle operations, etc.

### How It Works

**Turn 1 — Request:** Send a natural-language request describing the write operation.

The agent responds with a **preview** showing what will happen and asks for confirmation. This is a normal text response, not a special event type.

**Turn 2 — Confirm:** Create a new run, include the full message history (including the preview response), and send a confirmation message like "Yes, proceed" or "Yes, create it".

The agent executes the operation and responds with a confirmation.

### Example: Create a User

**Turn 1 messages:**
```json
[{"id": "user_001", "role": "user", "content": "Create a user with username jdoe, name John Doe, email john.doe@example.com"}]
```

Agent responds with a preview table showing the user details and asks "Should I proceed?"

**Turn 2 messages (accumulated):**
```json
[
  {"id": "user_001", "role": "user", "content": "Create a user with username jdoe, name John Doe, email john.doe@example.com"},
  {"id": "assistant_001", "role": "assistant", "content": "Here's a preview of the user to create:\n\n| Field | Value |\n|...|...|\n\nShould I proceed?"},
  {"id": "user_002", "role": "user", "content": "Yes, create it"}
]
```

Agent executes the creation and responds with confirmation.

### Destructive Operations

Operations like `delete_user`, `delete_course`, and `delete_department` include a WARNING in the preview text indicating the operation is permanent. The confirmation flow is the same — but pay attention to the warning text before confirming.

### Lifecycle Operations

Programs, certifications, and dynamic rules have specific lifecycle states (see the Capabilities section). Attempting to skip states (e.g., deleting without archiving first) will result in an error message from the agent, not a crash.

## Common Workflow Recipes

These are natural-language messages you send through the AG-UI protocol. The Moodle agent handles all internal tool routing and cross-domain lookups automatically.

### Training Compliance Audit

```
"Who hasn't completed the Safety Fundamentals course?"
```

Returns a completion overview with per-user status. Follow up with:

```
"Show me the UTM report for Safety Fundamentals"
```

Returns department-level completion breakdown.

### Bulk Enrollment

```
"Enroll Alice Johnson and Bob Smith into Cybersecurity Basics"
```

Triggers the preview/confirm flow. The agent resolves user names to IDs internally.

### New Employee Onboarding

This is a multi-turn workflow that spans multiple skill domains:

```
"Create a new user with username jdoe, name John Doe, email john.doe@example.com"
```

Confirm the preview, then:

```
"Assign John Doe to the Engineering department as a Senior Engineer"
```

Confirm, then:

```
"Allocate John Doe to the Onboarding Program"
```

Each write step requires its own confirmation turn.

### Organization Restructuring

```
"Create a new department called Security with idnumber SEC under Engineering"
```

Confirm, then:

```
"Create a Security Analyst position in the Security department"
```

Confirm, then:

```
"Assign Bob Smith to the Security department as Security Analyst"
```

### Report Generation

```
"What custom reports are available?"
```

Returns the list of Report Builder reports with IDs. Follow up with:

```
"Show me the data from report 2"
```

Or for pre-built reports:

```
"Show me the advanced completion report for Cybersecurity Basics"
```

## Thread Lifecycle

### Delete a Thread

For automated consumers that create many threads, clean up when done:

```bash
curl -X DELETE ${SOLIPLEX_URL}/api/v1/rooms/moodle-tools/agui/{thread_id}
```

### Update Thread Metadata

Rename a thread or add a description:

```bash
curl -X POST ${SOLIPLEX_URL}/api/v1/rooms/moodle-tools/agui/{thread_id}/meta \
  -H "Content-Type: application/json" \
  -d '{"name": "New thread name", "description": "Optional description"}'
```

Returns HTTP 205 on success.

### Get Run Usage

After a run completes, check token usage:

```bash
curl ${SOLIPLEX_URL}/api/v1/rooms/moodle-tools/agui/{thread_id}/{run_id}
```

The `usage` field (when present): `{input_tokens, output_tokens, requests, tool_calls}`.

## Limitations

- **Result cap**: All queries return at most 100 records per request. For larger datasets, use the reporting tools or refine the query.
- **No MCP access**: The Moodle room exposes tools only through the AG-UI conversational protocol, not via MCP.
- **Custom reports**: The UTM and Advanced Completion report tools require custom Moodle plugins (`local_soliplex`). These may not be available in all Moodle instances. Standard Report Builder reports work everywhere.
- **Cross-domain routing**: The agent automatically routes requests across skill domains (e.g., looking up a user ID before enrolling). You do not need to chain calls manually.
- **Moodle API errors**: When a Moodle Web Service call fails (e.g., invalid course ID, permission denied), the error appears as text in the agent's response. The AG-UI run still completes normally with `RUN_FINISHED`.
