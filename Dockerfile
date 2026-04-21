FROM python:3.13-slim AS builder

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

COPY pyproject.toml /app/pyproject.toml

# Bootstrap sandbox environments
COPY --link sandbox/environments ./sandbox/environments

RUN --mount=type=cache,target=/root/.cache/uv \
    for env_dir in /app/sandbox/environments/*/; do \
      if [ -f "$env_dir/pyproject.toml" ]; then \
        uv --directory "$env_dir" sync --frozen; \
      fi; \
    done

COPY src/soliplex /app/src/soliplex

FROM python:3.13-slim AS runtime

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      curl \
      jq \
      bash \
      && rm -rf /var/lib/apt/lists/*

COPY --from=builder /app /app

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --user -e . --group dev

ENV PATH="/root/.local/bin:$PATH"

COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

EXPOSE 8000 5678

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["soliplex-cli", "serve", "--host=0.0.0.0", "/app/installation"]
