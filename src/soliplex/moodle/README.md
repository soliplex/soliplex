# Moodle Workplace Integration

## Overview

The `soliplex.moodle` package provides:

- **`MoodleClient`** — an async HTTP client for the Moodle REST Web Services API.
- **`moodle_tools_agent_factory`** — a pydantic-ai agent factory that exposes Moodle data as four LLM tools: courses, users, enrollment, and completion.

## Prerequisites

- **Moodle 4.x** (or Moodle Workplace 4.x) instance with web services enabled.
- A dedicated **web service account** with an external service that has the required functions enabled (see below).
- Network connectivity from the Soliplex host to the Moodle instance.

## Generating a Moodle API Token

1. In Moodle, go to **Site administration > Server > Web services > External services** and create (or edit) a service.
2. Add the following functions to the service:
   - `core_course_get_courses`
   - `core_user_get_users_by_field`
   - `core_enrol_get_enrolled_users`
   - `core_completion_get_course_completion_status`
3. Under **Site administration > Server > Web services > Manage tokens**, create a token for the service account.
4. Copy the token value — you will need it for Soliplex configuration.

## Soliplex Configuration

### Secrets

Add two secrets to your installation YAML:

```yaml
secrets:
  - secret_name: "MOODLE_BASE_URL"
    sources:
      - kind: "env_var"
        env_var_name: "MOODLE_BASE_URL"

  - secret_name: "MOODLE_API_TOKEN"
    sources:
      - kind: "env_var"
        env_var_name: "MOODLE_API_TOKEN"
```

Set the environment variables before starting Soliplex:

```bash
export MOODLE_BASE_URL="https://moodle.example.com"
export MOODLE_API_TOKEN="your_token_here"
```

### Room Path

Include the Moodle tools room in your `room_paths`:

```yaml
room_paths:
  - "./rooms/moodle-tools"
```

The room configuration at `rooms/moodle-tools/room_config.yaml` references the factory and maps the secrets through `extra_config`.

## Custom CA Certificates

If your Moodle instance uses a certificate signed by an internal certificate authority, add `moodle_verify_ssl` to the room's `extra_config`:

```yaml
extra_config:
  moodle_base_url: "secret:MOODLE_BASE_URL"
  moodle_api_token: "secret:MOODLE_API_TOKEN"
  moodle_verify_ssl: "/path/to/ca-bundle.crt"
```

Set `moodle_verify_ssl` to `false` (boolean) to disable TLS verification entirely — **not recommended for production**.

## Limitations

- **Result truncation** — List endpoints return at most 100 records (`MAX_RESULTS`). This is a client-side safeguard to keep LLM context bounded.
- **Read-only** — The integration only queries Moodle data. No write operations (enrollment changes, grade updates, etc.) are exposed.
