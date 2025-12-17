# Authentication

## Backend Login Endpoints Reference

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/login` | List OIDC providers |
| GET | `/api/login/{system}` | Initiate OIDC flow |
| GET | `/api/auth/{system}` | Complete OIDC flow (callback) |
| GET | `/api/user_info` | Get user profile |

## Authentication Flow

1. GET `/api/login`, get list of OIDC providers
    - For each provider, create a button to enable the user to connect
    - When a provider's button is pressed, GET `/api/login/{system}` where system is the provider associated with the button
        - If there are no providers, auth
