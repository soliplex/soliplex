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
    && \
  pip3 install --upgrade pip

COPY pyproject.toml /app/pyproject.toml
COPY src/soliplex /app/src/soliplex

RUN pip3 install -e .

CMD ["/usr/local/bin/soliplex-cli", "serve", "--host=0.0.0.0", "/app/installation"]
