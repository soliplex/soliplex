# OIDC Configuration

Configure OpenID Connect (OIDC) authentication providers.

## Quick Start

```yaml
# oidc/config.yaml
auth_systems:
  - id: "google"
    title: "Sign in with Google"
    server_url: "https://accounts.google.com"
    client_id: "your-client-id.apps.googleusercontent.com"
    scope: "openid email profile"
    token_validation_pem: |
      -----BEGIN PUBLIC KEY-----
      MIIBIjANBg...
      -----END PUBLIC KEY-----
```

## Directory Structure

```
oidc/
├── config.yaml      # Provider configuration
└── cacert.pem       # CA certificates (optional)
```

## Configuration Reference

### auth_systems (required)

List of OIDC providers:

```yaml
auth_systems:
  - id: "keycloak"
    title: "Corporate SSO"
    server_url: "https://sso.company.com/realms/main"
    client_id: "soliplex"
    client_secret: "secret:KEYCLOAK_CLIENT_SECRET"
    scope: "openid email profile"
    token_validation_pem: |
      -----BEGIN PUBLIC KEY-----
      ...
      -----END PUBLIC KEY-----
```

### oidc_client_pem_path

Shared CA certificate store:

```yaml
oidc_client_pem_path: "./cacert.pem"
```

If not set, uses system CA certificates.

## Provider Configuration

### id (required)

Unique identifier for the provider:

```yaml
id: "google"
```

### title (required)

Display name for login button:

```yaml
title: "Sign in with Google"
```

### server_url (required)

OIDC provider URL:

```yaml
server_url: "https://accounts.google.com"
```

### client_id (required)

OAuth client ID:

```yaml
client_id: "your-client-id.apps.googleusercontent.com"
```

### client_secret

OAuth client secret (for confidential clients):

```yaml
client_secret: "secret:GOOGLE_CLIENT_SECRET"
```

Use `secret:` prefix to reference a configured secret.

### scope

OAuth scopes:

```yaml
scope: "openid email profile"
```

### token_validation_pem (required)

Public key for token validation:

```yaml
token_validation_pem: |
  -----BEGIN PUBLIC KEY-----
  MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA...
  -----END PUBLIC KEY-----
```

## Provider Examples

### Google

```yaml
auth_systems:
  - id: "google"
    title: "Sign in with Google"
    server_url: "https://accounts.google.com"
    client_id: "your-id.apps.googleusercontent.com"
    scope: "openid email profile"
    token_validation_pem: |
      -----BEGIN PUBLIC KEY-----
      # Get from https://www.googleapis.com/oauth2/v3/certs
      -----END PUBLIC KEY-----
```

### Keycloak

```yaml
auth_systems:
  - id: "keycloak"
    title: "Corporate SSO"
    server_url: "https://keycloak.company.com/realms/main"
    client_id: "soliplex"
    client_secret: "secret:KEYCLOAK_CLIENT_SECRET"
    scope: "openid email profile"
    token_validation_pem: |
      -----BEGIN PUBLIC KEY-----
      # Get from Keycloak admin console
      -----END PUBLIC KEY-----
```

### Azure AD

```yaml
auth_systems:
  - id: "azure"
    title: "Sign in with Microsoft"
    server_url: "https://login.microsoftonline.com/{tenant-id}/v2.0"
    client_id: "your-app-id"
    client_secret: "secret:AZURE_CLIENT_SECRET"
    scope: "openid email profile"
    token_validation_pem: |
      -----BEGIN PUBLIC KEY-----
      # Get from Azure AD
      -----END PUBLIC KEY-----
```

### Okta

```yaml
auth_systems:
  - id: "okta"
    title: "Sign in with Okta"
    server_url: "https://your-domain.okta.com"
    client_id: "your-client-id"
    client_secret: "secret:OKTA_CLIENT_SECRET"
    scope: "openid email profile"
    token_validation_pem: |
      -----BEGIN PUBLIC KEY-----
      # Get from Okta admin
      -----END PUBLIC KEY-----
```

## Multiple Providers

Configure multiple authentication options:

```yaml
auth_systems:
  - id: "google"
    title: "Personal Google"
    server_url: "https://accounts.google.com"
    client_id: "personal-client-id"
    scope: "openid email profile"
    token_validation_pem: |
      ...

  - id: "corporate"
    title: "Corporate SSO"
    server_url: "https://sso.company.com"
    client_id: "corporate-client-id"
    client_secret: "secret:CORPORATE_SECRET"
    scope: "openid email profile"
    token_validation_pem: |
      ...
```

## Disabling Authentication

For development, disable authentication:

**In installation.yaml:**
```yaml
oidc_paths:
  -    # Empty entry
```

**Or via CLI:**
```bash
soliplex-cli serve installation.yaml --no-auth-mode
```

**Warning:** Never use `--no-auth-mode` in production.

## Authentication Flow

1. User clicks "Sign in with {Provider}"
2. Browser redirects to `/login/{provider_id}`
3. Server redirects to provider's authorization URL
4. User authenticates with provider
5. Provider redirects back to `/auth/{provider_id}`
6. Server validates token and redirects to app with credentials

## Token Refresh

The Flutter app automatically handles token refresh:

1. Access token expires
2. App uses refresh token to get new access token
3. If refresh fails, user is redirected to login

## Secrets Configuration

Configure client secrets in installation.yaml:

```yaml
# installation.yaml
secrets:
  - secret_name: "KEYCLOAK_CLIENT_SECRET"
    sources:
      - kind: "env_var"
        env_var_name: "KEYCLOAK_CLIENT_SECRET"
```

## API Endpoints

### GET /login

List available providers:

```json
{
  "google": {
    "id": "google",
    "display_name": "Sign in with Google"
  },
  "corporate": {
    "id": "corporate",
    "display_name": "Corporate SSO"
  }
}
```

### GET /login/{provider_id}

Initiate authentication flow.

### GET /auth/{provider_id}

Complete authentication flow.

### GET /user_info

Get authenticated user profile:

```json
{
  "preferred_username": "user@example.com",
  "given_name": "John",
  "family_name": "Doe",
  "email": "user@example.com"
}
```

## Troubleshooting

### Invalid Token

- Verify `token_validation_pem` matches provider's public key
- Check that the key hasn't rotated
- Verify token hasn't expired

### Redirect URI Mismatch

- Configure correct redirect URI in provider: `https://your-domain/auth/{provider_id}`
- Ensure no trailing slashes

### Client Secret Issues

- Verify secret is correctly configured in Soliplex secrets
- Check secret value matches provider configuration

## Source Code

- OIDC configuration: `src/soliplex/config.py`
- Authentication: `src/soliplex/auth.py`
- Auth endpoints: `src/soliplex/views/auth.py`
