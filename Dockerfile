FROM python:3.13-slim AS builder

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      gcc \
      git \
      curl \
      libffi-dev \
      build-essential \
      && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml /app/pyproject.toml

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip && \
    pip install --user -e .

COPY src/soliplex /app/src/soliplex

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --user -e . --group dev

FROM python:3.13-slim AS runtime

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      curl \
      jq \
      && rm -rf /var/lib/apt/lists/*

COPY --from=builder /root/.local /root/.local
ENV PATH="/root/.local/bin:$PATH"

COPY src/soliplex /app/src/soliplex
COPY pyproject.toml /app/pyproject.toml

EXPOSE 8000 5678

CMD ["soliplex-cli", "serve", "--host=0.0.0.0", "/app/installation"]
