FROM python:3.13-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy workspace configuration
COPY pyproject.toml uv.lock* ./

# Copy all apps
COPY apps/ ./apps/

# Install dependencies
RUN uv sync --frozen --no-dev

# Expose port
EXPOSE 8000

# Default command
CMD ["uv", "run", "soliplex-cli", "serve", "--host", "0.0.0.0"]
