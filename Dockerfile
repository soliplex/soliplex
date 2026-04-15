# syntax=docker/dockerfile:1
FROM python:3.13-slim AS base

ARG APP_UID=1000
ARG APP_GID=1000

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_PYTHON=python3.13 \
    SOURCE_DATE_EPOCH=0 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# System packages needed at runtime
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      bubblewrap \
      curl \
      git \
      jq \
      rsync \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd -g ${APP_GID} soliplex && \
    useradd -u ${APP_UID} -g ${APP_GID} -m -s /bin/bash soliplex

# ---------- builder: install dependencies and package ----------
FROM base AS builder

COPY --from=ghcr.io/astral-sh/uv:0.11.6 /uv /uvx /bin/

COPY --link pyproject.toml uv.lock ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY --link src/ ./src/

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# Bootstrap sandbox environments
COPY --link sandbox/environments ./sandbox/environments

RUN --mount=type=cache,target=/root/.cache/uv \
    for env_dir in /app/sandbox/environments/*/; do \
      if [ -f "$env_dir/pyproject.toml" ]; then \
        uv --directory "$env_dir" sync --frozen; \
      fi; \
    done

# ---------- development: full toolchain, expects bind mount ----------
FROM builder AS development

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen

RUN chown -R soliplex:soliplex /app

USER soliplex

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/ok')"]

CMD ["soliplex-cli", "serve", "--host=0.0.0.0", "--reload=both", "/app/installation"]

# ---------- production: minimal, non-root, default target ----------
FROM base AS production

COPY --from=builder /app /app

RUN chown -R soliplex:soliplex /app

USER soliplex

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/ok')"]

CMD ["soliplex-cli", "serve", "--host=0.0.0.0", "/app/installation"]
