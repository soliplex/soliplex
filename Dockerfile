# syntax=docker/dockerfile:1
#
# Release images for downstream deployments to extend, published to
# 'ghcr.io/soliplex/soliplex' (target 'soliplex') and
# 'ghcr.io/soliplex/soliplex-tui' (target 'tui') by
# '.github/workflows/image.yaml'.  See 'docs/docker.md'.
#
# The images create no runtime user and bundle no sandbox environments:
# both are per-deployment choices.

# ---------- base: Python, uv, and runtime system packages ----------
FROM ghcr.io/astral-sh/uv:python3.13-trixie-slim AS base

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# 'libpq5' backs the 'postgres' extra's pure-Python 'psycopg', so it uses
# the same system OpenSSL as Python's 'ssl' module.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      bubblewrap \
      ca-certificates \
      curl \
      git \
      jq \
      libpq5 \
    && rm -rf /var/lib/apt/lists/*

# ---------- builder: install the locked dependencies and project ----------
FROM base AS builder

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    uv sync --frozen --no-dev --extra postgres --no-install-project

COPY pyproject.toml uv.lock ./
COPY src/ ./src/

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --extra postgres --no-editable

# ---------- soliplex: the server image (default target) ----------
FROM base AS soliplex

COPY --from=builder /app/.venv /app/.venv

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/ok')"]

CMD ["soliplex-cli", "serve", "--host=0.0.0.0", "/app/installation"]

# ---------- tui: the server image plus the 'tui' dependency group ----------
FROM soliplex AS tui

# Building the project writes 'src/*.egg-info' and 'build/':  keep both out
# of the layer.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=src,target=src,rw \
    --mount=type=tmpfs,target=build \
    uv sync --frozen --no-dev --extra postgres --group tui --no-editable
