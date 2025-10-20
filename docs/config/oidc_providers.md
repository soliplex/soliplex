# OIDC Provider Configuraton

The `config.yaml` file in an OIDC provider configuration directory specifies
one or more authentication systems, sharing a common CA certificate
store:

```yaml
oidc_client_pem_path: "./cacert.pem"

auth_systems:

  - id: "myprovder"
    title: "Authenticate with MyProovider"
    server_url: "https://oidc.excample.com/"
    client_id: "myprovider-token-service"
    client_secret: ""  # "secret:{MYPROVIDER_CLIENT_SECRET}"
    scope: "openid email profile"
    token_validation_pem: |
        -----BEGIN PUBLIC KEY-----
        MII..AQAB
        -----END PUBLIC KEY-----
```

## Required Configuration Elements

- `authsystems` is a list of one or more OIDC provider configurations
  (see below).

## Optional Configuration Elements

- `oidc_client_pem_path` points to a file on the filesystem containing
  the shared CA certificate store.  If not configured, the Soliplex
  application will use systemwide default CA certificates.

## Required OIDC Provider Elements

- `id`: a string, should be unique across all configured providers

- `title`: a string, might be displayed by a client

- `server_url`: URL for initiating the token auth flow.

- `token_validation_pem`: a string, the public key used to verify
   the providers tokens.

- `client_id`: a string identifying the client to the provider.

## Optional OIDC Provider Elements

- `client_secret`: a string;  if not empty, should be in the form
  `"secret:MYPROVIDER_CLIENT_SECRET"`, where the name following the
  `secret:` prefix is the name of a configured installation secret
  (see [this page](secrets.md) for details).

- `scope`: string, an OAuth scope specifier.
