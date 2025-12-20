# Authentication

Soliplex uses OpenID Connect (OIDC) for authentication, supporting any OIDC-compliant identity provider.

## Overview

| Aspect | Details |
|--------|---------|
| **Protocol** | OpenID Connect (OIDC) |
| **Token Type** | Bearer (JWT with RS256) |
| **Supported Providers** | Any OIDC-compliant provider (Keycloak, Okta, Google, etc.) |

## Authentication Flow

```
┌──────────┐     ┌──────────────┐     ┌─────────────────┐
│  Client  │────▶│   Soliplex   │────▶│  OIDC Provider  │
│          │     │   /login     │     │  (Keycloak,etc) │
└──────────┘     └──────────────┘     └─────────────────┘
     ▲                                        │
     │                                        │
     └────────────────────────────────────────┘
              Redirect with tokens
```

1. Client calls `GET /login` to list available providers
2. Client redirects user to `GET /login/{provider}?return_to=/callback`
3. User authenticates with OIDC provider
4. Provider redirects to `GET /auth/{provider}` with authorization code
5. Soliplex exchanges code for tokens via authlib
6. Soliplex redirects client to `return_to` URL with tokens in query params

## Configuration

### Directory Structure

OIDC providers are configured in a directory containing a `config.yaml` file:

```
oidc/
└── config.yaml          # Contains auth_systems list
    └── cacert.pem       # Optional: CA certificate for self-signed certs
```

### OIDC Provider Configuration

```yaml
# oidc/config.yaml

# Optional: CA certificate for providers with self-signed certs
oidc_client_pem_path: "./cacert.pem"

auth_systems:
  - id: "keycloak"
    title: "Sign in with Keycloak"
    server_url: "https://sso.example.com/realms/myapp"
    client_id: "soliplex-client"
    client_secret: "secret:KEYCLOAK_CLIENT_SECRET"
    scope: "openid email profile"
    token_validation_pem: |
      -----BEGIN PUBLIC KEY-----
      MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA...
      -----END PUBLIC KEY-----

  - id: "okta"
    title: "Sign in with Okta"
    server_url: "https://dev-12345.okta.com"
    client_id: "0oa1234567890abcdef"
    client_secret: "secret:OKTA_CLIENT_SECRET"
    scope: "openid email profile"
    token_validation_pem: |
      -----BEGIN PUBLIC KEY-----
      ...
      -----END PUBLIC KEY-----
```

### Configuration Fields

| Field | Required | Description |
|-------|----------|-------------|
| `id` | Yes | Unique provider identifier (used in URLs) |
| `title` | Yes | Display name shown to users |
| `server_url` | Yes | OIDC provider base URL (discovery via `/.well-known/openid-configuration`) |
| `client_id` | Yes | OAuth client ID |
| `client_secret` | No | OAuth client secret (use `secret:NAME` for secrets) |
| `scope` | No | Space-separated OAuth scopes (no default; behavior depends on provider) |
| `token_validation_pem` | Yes | Public key (PEM format) for JWT signature validation |
| `oidc_client_pem_path` | No | Path to CA certificate for self-signed provider certs |

### Installation Reference

Reference OIDC config directories in your installation config:

```yaml
# installation.yaml
oidc_paths:
  - "./oidc"              # Directory containing config.yaml
  - "./oidc-secondary"    # Multiple directories supported
```

## Development Mode

For local development without authentication:

```bash
soliplex-cli serve example/minimal.yaml --no-auth-mode
```

This mode:
- Skips JWT validation
- Returns a mock user: `{"name": "Phreddy Phlyntstone", "email": "phreddy@example.com"}`
- Disables `/login/{system}` and `/auth/{system}` endpoints (404)

!!! warning "Security"
    Never use `--no-auth-mode` in production!

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/login` | GET | List configured OIDC providers |
| `/login/{system}` | GET | Initiate OIDC flow (accepts `?return_to=` param) |
| `/auth/{system}` | GET | Complete OIDC flow (callback from provider) |
| `/user_info` | GET | Get authenticated user profile |

### Example: List Providers

```bash
curl http://localhost:8000/login
```

```json
{
  "keycloak": {
    "id": "keycloak",
    "title": "Sign in with Keycloak",
    "server_url": "https://sso.example.com/realms/myapp",
    "token_validation_pem": "-----BEGIN PUBLIC KEY-----\nMIIBI...",
    "client_id": "soliplex-client",
    "scope": "openid email profile"
  }
}
```

Note: The `token_validation_pem` public key is included in the response.

## Token Handling

### Access Token

The OIDC callback redirects to the client with tokens in query parameters:

```
/callback?token=<access_token>&refresh_token=<refresh_token>&expires_in=300&refresh_expires_in=1800
```

Use the access token for API authentication:

```http
GET /api/v1/rooms HTTP/1.1
Authorization: Bearer <access_token>
```

### Token Refresh

Token refresh is handled **client-side**. The server provides:
- `refresh_token`: Token for obtaining new access tokens
- `expires_in`: Access token lifetime in seconds
- `refresh_expires_in`: Refresh token lifetime in seconds

The client (Flutter app) must track expiration and re-authenticate when needed.

### JWT Validation

Access tokens are validated using:
- RS256 algorithm
- Public key from `token_validation_pem`
- Audience validation disabled (provider-agnostic)

## User Profile

Authenticated users have profile information from JWT claims:

```json
{
  "sub": "user-uuid-12345",
  "name": "John Doe",
  "given_name": "John",
  "family_name": "Doe",
  "email": "john@example.com",
  "preferred_username": "johndoe"
}
```

The exact fields depend on your OIDC provider and configured scopes. Common claims:
- `sub`: Subject (unique user ID)
- `name`: Full name
- `email`: Email address
- `preferred_username`: Username

This profile is accessible to agents via `ctx.deps.user`.

## Troubleshooting

### Token Expired (401 Unauthorized)

**Symptom**: API calls return 401

**Cause**: Access token has expired

**Solution**: Re-authenticate via the OIDC flow or use refresh token

### JWT Validation Failed

**Symptom**: 401 with "JWT validation failed"

**Causes**:
- Wrong `token_validation_pem` public key
- Token from different provider than configured
- Token algorithm mismatch (must be RS256)

**Solution**: Verify public key matches your OIDC provider's signing key

### Missing User Profile Fields

**Symptom**: User profile incomplete

**Causes**:
- Missing scopes (e.g., `email`, `profile`)
- Provider doesn't include claims in access token

**Solution**:
1. Add required scopes to `scope` field
2. Check provider configuration for claim mapping

### SSL Certificate Errors

**Symptom**: Connection errors to OIDC provider

**Cause**: Self-signed or private CA certificate

**Solution**: Set `oidc_client_pem_path` to your CA certificate file

## Source Files

| Component | File |
|-----------|------|
| OAuth setup | `src/soliplex/auth.py` |
| Auth endpoints | `src/soliplex/views/auth.py` |
| OIDC config parsing | `src/soliplex/config.py` (OIDCAuthSystemConfig) |
| MCP token auth | `src/soliplex/mcp_auth.py` |