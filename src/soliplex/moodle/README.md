# Moodle Workplace Integration

## Overview

The `soliplex.moodle` package provides:

- **`MoodleClient`** — an async HTTP client for the Moodle REST Web Services API.
- **`moodle_tools_agent_factory`** — a pydantic-ai agent factory that exposes Moodle data as LLM tools for comprehensive training management.

### Available Tools

**Query Tools:**
- `list_courses` — discover courses and IDs
- `find_user` — look up user by username or email
- `get_course_contents` — see sections, activities, and modules in a course
- `list_enrolled_users` — who is in a course
- `get_completion_status` — check one user's completion
- `get_course_completion_overview` — bulk completion rates for a whole course
- `get_user_grades` — grade report for a user in a course
- `get_assignment_grades` — all grades for assignments in a course
- `get_upcoming_events` — calendar events and deadlines
- `list_course_groups` / `get_group_members` — course groups
- `list_cohorts` / `get_cohort_members` — organizational cohorts

**Write Tools (require user confirmation):**
- `enrol_users` — enrol users into a course
- `send_message` — send messages to users

## Prerequisites

- **Moodle 4.x** (or Moodle Workplace 4.x) instance with web services enabled.
- A dedicated **web service account** with an external service that has the required functions enabled (see below).
- Network connectivity from the Soliplex host to the Moodle instance.

## Generating a Moodle API Token

1. In Moodle, go to **Site administration > Server > Web services > External services** and create (or edit) a service.
2. Add the following functions to the service:
   - `core_course_get_courses`
   - `core_course_get_contents`
   - `core_user_get_users_by_field`
   - `core_enrol_get_enrolled_users`
   - `core_completion_get_course_completion_status`
   - `core_completion_get_activities_completion_status`
   - `core_group_get_course_groups`
   - `core_group_get_group_members`
   - `core_cohort_get_cohorts`
   - `core_cohort_get_cohort_members`
   - `mod_assign_get_grades`
   - `gradereport_user_get_grades_table`
   - `core_calendar_get_calendar_events`
   - `enrol_manual_enrol_users`
   - `core_message_send_instant_messages`
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

## Write Operations Safety Model

Write tools (`enrol_users`, `send_message`) use a confirm-before-execute pattern. The LLM must first call the tool without `confirmed=True` to generate a preview, present it to the user, and only execute after explicit user approval.

## Custom Plugin: `local_soliplex`

The `get_team_members` tool queries department members using a custom Moodle plugin (`local_soliplex`). Without the plugin, the tool falls back to the standard `tool_organisation_get_managed_users` endpoint, which only returns direct reports of the API token owner (typically empty for admin accounts).

### Installation

The plugin lives in `moodle_sandbox/local/soliplex/` and provides a single web service function: `local_soliplex_get_department_members`. It queries the `tool_organisation_job` table joined with user and department/position data — no manager scoping.

To install:

```bash
# Install the plugin
docker compose exec -T webserver php admin/cli/upgrade.php --non-interactive

# Re-seed to register the function on the external service
docker compose exec -T webserver php local/seed_data.php
```

The `seed_data.php` script automatically registers `local_soliplex_get_department_members` on all "Soliplex API" external services.

## Limitations

- **Result truncation** — List endpoints return at most 100 records (`MAX_RESULTS`). This is a client-side safeguard to keep LLM context bounded.
- **Completion overview** — The `get_course_completion_overview` tool loops through enrolled users individually (no bulk API exists). It is capped at `MAX_RESULTS` users.
- **Department members** — Without the `local_soliplex` plugin, the `get_team_members` tool falls back to `tool_organisation_get_managed_users` which only returns the token owner's direct reports.
