# Docker Deployment

To generate a full-service `compose` stack, use
[`soliplex-template`](https://github.com/soliplex/soliplex-template)
(v0.16 or later). It can also run a `soliplex` checkout in dev mode: see
the [tutorial](https://soliplex.github.io/soliplex-template/getting-started/tutorials/backend-dev-mode/).

The `soliplex` repo provides no local `compose` support. Instead, each
release publishes images for deployments to extend.

## Published images

Each published release pushes three images to the GitHub Container
Registry:

| Image | Contents |
| --- | --- |
| `ghcr.io/soliplex/soliplex` | `soliplex`, without extras or groups |
| `ghcr.io/soliplex/soliplex-postgres` | The base image, plus the system `libpq5` and the `postgres` extra |
| `ghcr.io/soliplex/soliplex-tui` | The base image, plus the `tui` dependency group (`soliplex-tui`, `soliplex-tui-serve`) |

All three are built for `linux/amd64` and `linux/arm64`. Each installs the
release's own wheel, the one uploaded to PyPI. Every dependency is
constrained to the version in the release's `uv.lock`, so the images carry
the dependency set the release's CI tested.

The `postgres` and `tui` images are each one or two layers on top of the
base image, so a host which pulls more than one downloads the shared
layers only once.

### Tags

Tags follow the project version published to PyPI:

| Tag | Moves? | Example |
| --- | --- | --- |
| `<major>.<minor>.<patch>` | no | `0.86.1`; `0.86.0` for the `0.86` release |
| `<major>.<minor>` | yes, to each patch release | `0.86` |
| `latest` | yes, to the highest released version | |

A patch release on an older maintenance branch (e.g. `0.82.5` after `0.86`
is out) moves only its own `<major>.<minor>` tag, not `latest`.

### Contents

- Python 3.13, from the official `python:3.13-slim-trixie` image
- A virtual environment at `/app/.venv`, first on `PATH`
  (`VIRTUAL_ENV` is set), and `/app` as the working directory
- A default command printing the image's CLI help: `soliplex-cli --help`,
  or `soliplex-tui --help` for the TUI image
- In `soliplex-postgres`, `psycopg`'s pure-Python implementation over the
  system `libpq5`, so PostgreSQL connections use the same system OpenSSL
  as Python's `ssl` module

The images do *not* provide:

- **`uv`, or the packaging inputs** (`pyproject.toml`, `uv.lock`). To add
  packages, install them into `/app/.venv` with the image's `pip`, or
  mount `uv` from its own image for one `RUN` (see below).
- **A runtime user.** They run as `root`, and create no user or group.
  Create your own, with your deployment's UID / GID.
- **Optional system packages**, such as `bubblewrap` for the `bwrap`
  sandbox skill. Install those your rooms need.
- **An installation.** Copy or mount your configuration, and set the
  command to serve it.

## Extending the image

Reference a version in `FROM`:

```dockerfile
FROM ghcr.io/soliplex/soliplex-postgres:0.86

ARG PUID=1000
ARG PGID=1000
RUN groupadd -g ${PGID} soliplex && \
    useradd -u ${PUID} -g ${PGID} -m soliplex

# Extra Python packages, installed without leaving 'uv' in the image.
RUN --mount=from=ghcr.io/astral-sh/uv:0.12.18,source=/uv,target=/bin/uv \
    uv pip install --no-cache my-soliplex-tools

COPY --chown=soliplex:soliplex installation/ /app/installation/

USER soliplex
EXPOSE 8000
CMD ["soliplex-cli", "serve", "--host=0.0.0.0", "/app/installation"]
```

Pick the tag for the updates you want:

- A moving `<major>.<minor>` tag picks up that minor release's bug fixes.
  Rebuild with `docker compose build --pull` (or `docker build --pull`) to
  fetch the newest image behind the tag.
- An exact `<major>.<minor>.<patch>` tag rebuilds reproducibly.

## Building the images locally

The `Dockerfile` installs a wheel, not the checkout. From a checkout, build
the wheel and export the locked requirements into `dist/` first, then
build a target and smoke-test it:

```bash
uv build --wheel
uv export --frozen --no-dev --extra postgres --group tui \
    --no-emit-project --no-hashes -o dist/constraints.txt
uv export --frozen --only-group tui \
    --no-emit-project --no-hashes -o dist/tui.txt
docker build --target soliplex-postgres -t soliplex-postgres:local .
scripts/smoke_image.sh soliplex-postgres soliplex-postgres:local
```

Leave only one wheel in `dist/`.
