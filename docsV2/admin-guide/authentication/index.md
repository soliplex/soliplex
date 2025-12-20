# Authentication

Soliplex uses OpenID Connect (OIDC) for authentication, supporting various identity providers.

## Overview

| Aspect | Details |
|--------|---------|
| **Protocol** | OpenID Connect (OIDC) |
| **Token Type** | Bearer (JWT) |
| **Supported Providers** | Any OIDC-compliant provider |

## Authentication Flow

```
┌──────────┐     ┌──────────────┐     ┌─────────────────┐
│  Client  │────▶│   Soliplex   │────▶│  OIDC Provider  │
│          │     │   /login     │     │  (Google, etc.) │
└──────────┘     └──────────────┘     └─────────────────┘
     ▲                                        │
     │                                        │
     └────────────────────────────────────────┘
              Redirect with tokens
```

1. Client calls `GET /login` to get available providers
2. Client redirects to `GET /login/{provider}`
3. User authenticates with OIDC provider
4. Provider redirects to `GET /auth/{provider}` with code
5. Soliplex exchanges code for tokens
6. Client receives access/refresh tokens

## Configuration

### OIDC Provider Configuration

```yaml
# oidc/google.yaml
id: "google"
client_id: "secret:GOOGLE_CLIENT_ID"
client_secret: "secret:GOOGLE_CLIENT_SECRET"
issuer: "https://accounts.google.com"
scopes:
  - "openid"
  - "profile"
  - "email"
```

### Installation Reference

```yaml
# installation.yaml
oidc_provider_paths:
  - "./oidc/google.yaml"
  - "./oidc/okta.yaml"
```

## Development Mode

For local development without authentication:

```bash
soliplex-cli serve example/minimal.yaml --no-auth-mode
```

!!! warning "Security"
    Never use `--no-auth-mode` in production!

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/login` | GET | List OIDC providers |
| `/login/{system}` | GET | Start OIDC flow |
| `/auth/{system}` | GET | Complete OIDC flow |
| `/user_info` | GET | Get authenticated user |

## Token Handling

### Access Token

Used for API authentication:

```http
GET /api/v1/rooms HTTP/1.1
Authorization: Bearer <access_token>
```

### Token Refresh

The OIDC flow handles token refresh automatically. See `src/soliplex/views/auth.py` for implementation details.

## User Profile

Authenticated users have profile information available:

```json
{
  "given_name": "John",
  "family_name": "Doe",
  "email": "john@example.com",
  "preferred_username": "johndoe"
}
```

This is accessible to agents via `ctx.deps.user`.

## Troubleshooting

### Token Expired

Symptom: 401 Unauthorized responses

Solution: Re-authenticate via the OIDC flow

### Missing Scopes

Symptom: User profile incomplete

Solution: Ensure required scopes are configured in OIDC provider
