# Docker Deployment

To generate a full-service `compose` stack, use
[`soliplex-template`](https://github.com/soliplex/soliplex-template)
(v0.16 or later). It can also run a `soliplex` checkout in dev mode: see
the [tutorial](https://soliplex.github.io/soliplex-template/getting-started/tutorials/backend-dev-mode/).

The `soliplex` repo provides no local `compose` support. Instead, each
release publishes base images for deployments to extend.

## Published images

Each published release pushes two images to the GitHub Container Registry:

| Image | Contents |
| --- | --- |
| `ghcr.io/soliplex/soliplex` | The server: `soliplex-cli` |
| `ghcr.io/soliplex/soliplex-tui` | The server image, plus the TUI (`soliplex-tui`, `soliplex-tui-serve`) |

Both are built for `linux/amd64` and `linux/arm64` from the release's
tagged checkout. They install `soliplex` with the repository's `uv.lock`, so
they carry the same dependency set as the release's CI run.

The TUI image is one extra layer on top of the server image. A host which
pulls both downloads the shared layers only once.

### Tags

Tags follow the project version published to PyPI:

| Tag | Moves? | Example |
| --- | --- | --- |
| `<major>.<minor>.<patch>` | no | `0.85.1`; `0.85.0` for the `0.85` release |
| `<major>.<minor>` | yes, to each patch release | `0.85` |
| `latest` | yes, to the highest released version | |

A patch release on an older maintenance branch (e.g. `0.82.5` after `0.85`
is out) moves only its own `<major>.<minor>` tag, not `latest`.

### Contents

- Python 3.13 and `uv`, from `ghcr.io/astral-sh/uv:python3.13-trixie-slim`
- A virtual environment at `/app/.venv`, first on `PATH`, with `soliplex`
  and its `postgres` extra installed
- `psycopg` over the system `libpq5`, so PostgreSQL connections use the
  same system OpenSSL as Python's `ssl` module
- `bubblewrap` (for the `bwrap` sandbox), `git`, `jq`, `curl`, and
  `ca-certificates`
- `EXPOSE 8000`, a `HEALTHCHECK` against `/api/ok`, and a default command
  of `soliplex-cli serve --host=0.0.0.0 /app/installation`

The images do *not* provide:

- **A runtime user.** They run as `root`, and create no user or group.
  Create your own, with your deployment's UID / GID.
- **Sandbox environments.** Build the ones your rooms need with the
  bundled `uv`.
- **An installation.** Copy or mount your configuration at
  `/app/installation`, or override the command to point elsewhere.

## Extending the image

Reference a version in `FROM`:

```dockerfile
FROM ghcr.io/soliplex/soliplex:0.85

ARG PUID=1000
ARG PGID=1000
RUN groupadd -g ${PGID} soliplex && \
    useradd -u ${PUID} -g ${PGID} -m soliplex

COPY --chown=soliplex:soliplex installation/ /app/installation/

USER soliplex
```

Pick the tag for the updates you want:

- A moving `<major>.<minor>` tag picks up that minor release's bug fixes.
  Rebuild with `docker compose build --pull` (or `docker build --pull`) to
  fetch the newest image behind the tag.
- An exact `<major>.<minor>.<patch>` tag rebuilds reproducibly.
