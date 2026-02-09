# Console Logging Configuration

In addition to [logging to Logfire](logfire.md), you can
configure how the Soliplex application emits logs to its standard output,
using a separate YAML file.  E.g.:

```yaml
version: 1
disable_existing_loggers: false
formatters:

  default:
    format: "$asctime|$levelname|$name|$message"
    datefmt: "%Y-%m-%dT%H:%M:%S"
    style: "$"
    validate: true
    defaults:
        some_key: null

handlers:

  console:
    class: "logging.StreamHandler"
    formatter: "default"
    stream: "ext://sys.stdout"

root:
  level: "INFO"
  handlers:
    - "console"
```


See the
[Python docs](https://docs.python.org/3/library/logging.config.html#dictionary-schema-details)
for details on the schema for this file.

To use your file, start the Soliplex server, passing the filename as the
value of the `--log-config` argument, e.g.:

```bash
soliplex-cli serve example/minimal.yaml --log-config example/logging.yaml
```
