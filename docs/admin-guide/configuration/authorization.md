# Room Authorization

Room authorization controls which users can access specific chat rooms. By default, all rooms are public. Authorization policies can restrict access based on authentication status, username, or email.

## Overview

| Aspect | Details |
|--------|---------|
| **Default behavior** | All rooms are public (no policy = allow all) |
| **Storage** | SQLAlchemy with SQLite (in-memory by default) |
| **Policy matching** | First matching ACL entry wins |
| **Fallback** | `default_allow_deny` when no ACL matches |

## Configuration

### Database URI

Configure the authorization database in `installation.yaml`:

```yaml
room_authz_dburi:
  sync: "sqlite:///./db/authz.db"
  async: "sqlite+aiosqlite:///./db/authz.db"
```

| Property | Required | Description |
|----------|----------|-------------|
| `sync` | No | Synchronous database URI (default: in-memory SQLite) |
| `async` | No | Asynchronous database URI (default: in-memory SQLite) |

**Note:** If not configured, authorization policies are stored in memory and lost on server restart.

### Using Secrets in Database URIs

Database URIs can reference secrets:

```yaml
room_authz_dburi:
  sync: "postgresql://user:secret:DB_PASSWORD@localhost/authz"
  async: "postgresql+asyncpg://user:secret:DB_PASSWORD@localhost/authz"

secrets:
  - name: DB_PASSWORD
```

## Authorization Policy Model

### RoomPolicy

A room policy defines access rules for a single room:

```json
{
  "room_id": "research",
  "default_allow_deny": "deny",
  "acl_entries": [
    {
      "allow_deny": "allow",
      "everyone": false,
      "authenticated": true,
      "preferred_username": null,
      "email": null
    }
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `room_id` | string | Room identifier |
| `default_allow_deny` | "allow" \| "deny" | Fallback when no ACL matches |
| `acl_entries` | ACLEntry[] | Ordered list of access rules |

### ACLEntry

Each ACL entry defines a single access rule:

| Field | Type | Description |
|-------|------|-------------|
| `allow_deny` | "allow" \| "deny" | Action when this entry matches |
| `everyone` | boolean | Match all users (including anonymous) |
| `authenticated` | boolean | Match any authenticated user |
| `preferred_username` | string \| null | Match specific username |
| `email` | string \| null | Match specific email |

## ACL Matching Logic

ACL entries are evaluated in order. The first matching entry determines access:

1. If `everyone: true` → match immediately
2. If `authenticated: true` and user is logged in → match
3. If `preferred_username` matches user's username → match
4. If `email` matches user's email → match
5. If no entry matches → use `default_allow_deny`

## Examples

### Allow Only Authenticated Users

```json
{
  "room_id": "internal",
  "default_allow_deny": "deny",
  "acl_entries": [
    {
      "allow_deny": "allow",
      "everyone": false,
      "authenticated": true,
      "preferred_username": null,
      "email": null
    }
  ]
}
```

### Allow Specific Users

```json
{
  "room_id": "admin",
  "default_allow_deny": "deny",
  "acl_entries": [
    {
      "allow_deny": "allow",
      "everyone": false,
      "authenticated": false,
      "preferred_username": "admin",
      "email": null
    },
    {
      "allow_deny": "allow",
      "everyone": false,
      "authenticated": false,
      "preferred_username": null,
      "email": "admin@example.com"
    }
  ]
}
```

### Deny Specific User, Allow Others

```json
{
  "room_id": "general",
  "default_allow_deny": "allow",
  "acl_entries": [
    {
      "allow_deny": "deny",
      "everyone": false,
      "authenticated": false,
      "preferred_username": "blocked_user",
      "email": null
    }
  ]
}
```

## API Endpoints

### Get Room Policy

```http
GET /api/v1/rooms/{room_id}/authz
Authorization: Bearer <token>
```

**Response:**

- `200 OK` with `RoomPolicy` if policy exists
- `200 OK` with `null` if no policy (room is public)
- `404 Not Found` if user doesn't have access

## Behavior Without Policy

Rooms without an authorization policy are **public by default**:

- Any user (authenticated or not) can access the room
- The room appears in room listings for all users

To restrict a room, you must create an authorization policy via the API.

## Database Schema

The authorization system uses two SQLAlchemy tables:

| Table | Purpose |
|-------|---------|
| `room_policy` | Room-level policy with default allow/deny |
| `room_acl_entry` | Individual ACL entries linked to policies |

Tables are created automatically on first use if using the default in-memory database. For persistent databases, ensure the schema is initialized.

## Source Files

| Component | File |
|-----------|------|
| Authorization service | `src/soliplex/authz/__init__.py` |
| SQLAlchemy schema | `src/soliplex/authz/schema.py` |
| API endpoint | `src/soliplex/views/authz.py` |
| Models | `src/soliplex/models.py` (RoomPolicy, ACLEntry) |
