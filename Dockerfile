# syntax=docker/dockerfile:1
#
# Release images, published to 'ghcr.io/soliplex/<target>' by
# '.github/workflows/image.yaml' (#1439).  See 'docs/docker.md'.
#
# Each target installs the release's own wheel, which the build context
# must provide in 'dist/' alongside two files exported from 'uv.lock':
#
#   uv build --wheel
#   uv export --frozen --no-dev --extra postgres --group tui \
#       --no-emit-project --no-hashes -o dist/constraints.txt
#   uv export --frozen --only-group tui \
#       --no-emit-project --no-hashes -o dist/tui.txt
#
# Every install is constrained to the locked versions, so the images carry
# the dependency set CI tested.  'uv' is mounted for each install, never
# copied:  the images contain neither it nor the packaging inputs.

ARG PYTHON_IMAGE=python:3.13-slim-trixie
ARG UV_IMAGE=ghcr.io/astral-sh/uv:0.12.18

FROM ${UV_IMAGE} AS uv

# ---------- soliplex: the wheel, without extras or groups ----------
FROM ${PYTHON_IMAGE} AS soliplex

ENV VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:$PATH" \
    UV_NO_CACHE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

RUN --mount=from=uv,source=/uv,target=/usr/local/bin/uv \
    --mount=type=bind,source=dist,target=/tmp/dist \
    uv venv --python /usr/local/bin/python3 /app/.venv && \
    uv pip install \
      --constraint /tmp/dist/constraints.txt \
      /tmp/dist/soliplex-*-py3-none-any.whl

CMD ["soliplex-cli", "--help"]

# ---------- soliplex-postgres: plus 'libpq5' and the 'postgres' extra ----
FROM soliplex AS soliplex-postgres

# The 'postgres' extra's pure-Python 'psycopg' loads the system 'libpq',
# so it uses the same system OpenSSL as Python's 'ssl' module.
RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq5 && \
    rm -rf /var/lib/apt/lists/*

RUN --mount=from=uv,source=/uv,target=/usr/local/bin/uv \
    --mount=type=bind,source=dist,target=/tmp/dist \
    wheel=$(echo /tmp/dist/soliplex-*-py3-none-any.whl) && \
    uv pip install \
      --constraint /tmp/dist/constraints.txt \
      "soliplex[postgres] @ file://${wheel}"

# ---------- soliplex-tui: plus the 'tui' dependency group ----------
FROM soliplex AS soliplex-tui

# A dependency group is not part of the wheel's metadata:  install the
# group's locked requirements beside it.
RUN --mount=from=uv,source=/uv,target=/usr/local/bin/uv \
    --mount=type=bind,source=dist,target=/tmp/dist \
    uv pip install \
      --constraint /tmp/dist/constraints.txt \
      --requirement /tmp/dist/tui.txt

CMD ["soliplex-tui", "--help"]
