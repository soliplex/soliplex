---
name: soliplex-feedback
description: Submit and retrieve feedback on Soliplex agent responses — thumbs up/down with optional reasons
---

# Soliplex Feedback

This skill covers submitting and retrieving feedback on agent responses in Soliplex. Feedback is attached to individual runs within a conversation thread.

## Submit Feedback on a Run

After receiving an agent response, submit feedback:

```bash
curl -X POST ${SOLIPLEX_URL}/api/v1/rooms/{room_id}/agui/{thread_id}/{run_id}/feedback \
  -H "Content-Type: application/json" \
  -d '{"feedback": "thumbs_up", "reason": "Accurate and helpful response"}'
```

The `feedback` field is a string — typically `"thumbs_up"` or `"thumbs_down"`.

The `reason` field is optional — a free-text explanation of why the feedback was given.

Returns HTTP 200 on success.

## Retrieve Feedback for a Run

Check existing feedback on a specific run:

```bash
curl ${SOLIPLEX_URL}/api/v1/rooms/{room_id}/agui/{thread_id}/{run_id}/feedback
```

Response:

```json
{
  "feedback": "thumbs_up",
  "reason": "Accurate and helpful response"
}
```

Returns `null` if no feedback has been submitted for this run.

## Query Recent Feedback (Admin)

These endpoints are for reviewing feedback across conversations.

### All rooms:

```bash
curl -X POST ${SOLIPLEX_URL}/api/v1/agui/feedback \
  -H "Content-Type: application/json" \
  -d '{"limit": 20, "since": "2025-01-01T00:00:00Z"}'
```

Both `limit` and `since` are optional filters.

### By room:

```bash
curl -X POST ${SOLIPLEX_URL}/api/v1/agui/feedback/rooms/{room_id} \
  -H "Content-Type: application/json" \
  -d '{"limit": 20}'
```

### By user:

```bash
curl -X POST ${SOLIPLEX_URL}/api/v1/agui/feedback/user/{user_name} \
  -H "Content-Type: application/json" \
  -d '{"limit": 20}'
```

## Review and Resolve Feedback (Admin)

Mark feedback as reviewed:

```bash
curl -X POST ${SOLIPLEX_URL}/api/v1/agui/feedback/review \
  -H "Content-Type: application/json" \
  -d '{
    "user_name": "reviewer",
    "room_id": "chat",
    "thread_id": "aaaaaaaa-...",
    "run_id": "11111111-...",
    "note": "Reviewed — response was correct"
  }'
```

Mark feedback as resolved:

```bash
curl -X POST ${SOLIPLEX_URL}/api/v1/agui/feedback/resolve \
  -H "Content-Type: application/json" \
  -d '{
    "user_name": "resolver",
    "room_id": "chat",
    "thread_id": "aaaaaaaa-...",
    "run_id": "11111111-...",
    "note": "Resolved — added to training data"
  }'
```
