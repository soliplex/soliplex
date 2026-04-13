# Logfire Configuration

The `logfire_config` attribute of the Soliplex installation configuration
allows defining policies for how [Logfire](https://logfire.pydantic.dev) is
[configured](https://logfire.pydantic.dev/docs/reference/api/logfire/#logfire.configure)
at server startup.

## Default behavior

If the `logfire_config` attribute is not present in the Soliplex installation
configuration, Soliplex configures it as follows:

```python
logfire.configure(send_to_logfire="if-token-present")
logfire.instrument_pydantic_ai()
logfire.instrument_fastapi(app, capture_headers=True)
```

That is, the `logfire` library will only send spans to the default Logfire
server if the `LOGFIRE_TOKEN` environment variable is set:  all other
configuration is done via OS environment variables (not in the Soliplex
configuration).  See the Logfire
[docs on environment variables](https://logfire.pydantic.dev/docs/reference/configuration/#using-environment-variables).

## Required attributes

- `token` should name the [secret](secrets.md) which contains the
  token issued by Logfire.  E.g.:

  ```yaml
  logfire_config:
      token: "secret:LOGFIRE_TOKEN"
  ```

## Optional attributes

- `service_name` defines the service name reported to Logfire
  for the appliction.  See
  [this page](https://logfire.pydantic.dev/docs/reference/api/logfire/#logfire.configure(service_name))
  for details

  It can be a literal, or else use a configured installation
  environment value.  E.g.:

  ```yaml
  logfire_config:
      ...
      service_name: "env:LOGFIRE_SERVICE_NAME"
  ```

- `service_version` defines the service version reported to Logfire
  for the appliction.  See
  [this page](https://logfire.pydantic.dev/docs/reference/api/logfire/#logfire.configure(service_version))
  for details

  It can be a literal, or else use a configured installation
  environment value.  E.g.:

  ```yaml
  logfire_config:
      ...
      service_version: "env:LOGFIRE_SERVICE_VERSION"
  ```

- `environment` defines the environment reported to Logfire
  for the appliction.  See
  [this page](https://logfire.pydantic.dev/docs/reference/api/logfire/#logfire.configure(environment))
  for details

  It can be a literal, or else use a configured installation
  environment value.  E.g.:

  ```yaml
  logfire_config:
      ...
      environment: "env:LOGFIRE_ENVIRONMENT"
  ```

- `data_dir` defines the path to local data recorded by Logfire.  See
  [this page](https://logfire.pydantic.dev/docs/reference/api/logfire/#logfire.configure(data_dir))
  for details

  It can be a literal, or else use a configured installation environment
  value.  E.g.:

  ```yaml
  logfire_config:
      ...
      data_dir:ib.Path | str = "env:LOGFIRE_DATA_DIR"
  ```

- `min_level` defines the minimum log level reported to Logfire.  See
  [this page](https://logfire.pydantic.dev/docs/reference/api/logfire/#logfire.configure(min_level)) for details.

  It can be a literal, or else use a configured installation
  environment value.  E.g.:

  ```yaml
  logfire_config:
      ...
      min_level: logfire.LevelName = "env:LOGFIRE_MIN_LEVEL"
  ```

- `base_url` (string or None, None by default) is the URL of the
  Logfire server.  This value would ordinarily only be used when self-hosting
  Logfire, as the library will discover the cloud-hosted URL from the token.

  It can be a literal, or else use a configured installation
  environment value.  E.g.:

  ```yaml
  logfire_config:
      ...
      base_url: "env:LOGFIRE_BASE_URL"
  ```

- `inspect_arguments` (boolean or None, None by default)  See
  [this page](
  https://logfire.pydantic.dev/docs/reference/api/logfire/#logfire.configure(inspect_arguments)) for details.

  ```yaml
  logfire_config:
      ...
      inspect_arguments: true
  ```

- `add_baggage_to_attributes` (boolean, True by default)  See
  [this page](https://logfire.pydantic.dev/docs/reference/api/logfire/#logfire.configure(add_baggage_to_attributes)) for details.

  ```yaml
  logfire_config:
      ...
      add_baggage_to_attributes: false
  ```

- `distributed_tracing` (boolean or None, None by default).  See
  [this page](https://logfire.pydantic.dev/docs/reference/api/logfire/#logfire.configure(distributed_tracing)) for details.

  ```yaml
  logfire_config:
      ...
      distributed_tracing: false
  ```
