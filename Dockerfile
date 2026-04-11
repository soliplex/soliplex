FROM python:3.13.9

WORKDIR /app

# Install system-level build dependencies
RUN \
  --mount=type=cache,target=/root/.cache/pip \
  apt-get update && \
  apt-get install -y \
    curl \
    gpg \
    apt-transport-https \
    git \
    rsync \
    vim \
    jq \
    bubblewrap \
    && \
  pip3 install --upgrade pip uv

COPY pyproject.toml /app/pyproject.toml
COPY src/soliplex /app/src/soliplex

RUN pip3 install -e .

# Bootstrap sandbox environments
COPY sandbox/environments /app/sandbox/environments
RUN for env_dir in /app/sandbox/environments/*/; do \
      if [ -f "$env_dir/pyproject.toml" ]; then \
        cd "$env_dir" && uv sync && cd /app; \
      fi; \
    done

CMD ["/usr/local/bin/soliplex-cli", "serve", "--host=0.0.0.0", "/app/installation"]
