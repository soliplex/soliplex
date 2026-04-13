# Prerequisites and Installation Checklist

This guide provides a complete checklist for setting up Soliplex from scratch.

## System Requirements

### Software Prerequisites

- [ ] **Python 3.12+** - Required for backend server
- [ ] **pip** - Python package installer (usually included with Python)
- [ ] **Git** - For cloning the repository
- [ ] **Docker & Docker Compose** (Optional) - For containerized deployment

### LLM Provider (Choose One)

- [ ] **Ollama** (Recommended for local development)
  - Install from: <https://ollama.com/>
  - Verify: `ollama --version`

  OR

- [ ] **OpenAI API Access**
  - Create account at: <https://platform.openai.com/>
  - Generate API key at: <https://platform.openai.com/api-keys>

### Optional Components

- [ ] **Flutter SDK** (For frontend development)
  - Version: 3.35+
  - Install from: <https://flutter.dev/docs/get-started/install>
  - Verify: `flutter --version`

- [ ] **Dart SDK** (Usually included with Flutter)
  - Version: 3.10.0+
  - Verify: `dart --version`

- [ ] **PostgreSQL** (Optional, for production databases)
  - For development, SQLite (included) is sufficient

## Installation Steps

Follow these steps in order for a successful setup.

### Step 1: Install Python 3.13

#### Windows

```bash
# Download from python.org
# Or use winget
winget install Python.Python.3.13
```

#### macOS

```bash
# Using Homebrew
brew install python@3.13
```

#### Linux

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3.13 python3.13-venv python3.13-dev

# Fedora
sudo dnf install python3.13
```

Verify installation:

```bash
python3.13 --version
```

### Step 2: Install and Configure Ollama (if using Ollama)

1. **Install Ollama**

   ```bash
   # Linux
   curl -fsSL https://ollama.com/install.sh | sh

   # macOS
   brew install ollama

   # Windows: Download from https://ollama.com/download
   ```

2. **Start Ollama service**

   ```bash
   # Linux/macOS
   ollama serve

   # Windows: Ollama runs as a service automatically
   ```

3. **Pull required models**

   ```bash
   # Chat model (choose one)
   ollama pull qwen2.5:latest
   # OR
   ollama pull llama3.2:latest
   # OR
   ollama pull mistral:latest

   # Embedding model (required for RAG)
   ollama pull qwen3-embedding:4b
   ```

4. **Verify models**

   ```bash
   ollama list
   ```

5. **Note your Ollama URL**
   - Local installation: `http://localhost:11434`
   - Remote installation: `http://your-server:11434`
   - Docker accessing host: `http://host.docker.internal:11434`

### Step 3: Clone Soliplex Repository

```bash
git clone https://github.com/soliplex/soliplex.git
cd soliplex
```

### Step 4: Set Up Python Virtual Environment

```bash
# Create virtual environment
python3.13 -m venv venv

# Activate virtual environment
# Linux/macOS:
source venv/bin/activate

# Windows:
venv\Scripts\activate
```

Your prompt should now show `(venv)` prefix.

### Step 5: Install Python Dependencies

```bash
# Upgrade pip
pip install --upgrade pip setuptools

# Install Soliplex in editable mode
pip install -e .

# Verify installation
soliplex-cli --help
```

### Step 6: Install RAG Indexing Dependencies

Soliplex requires `haiku.rag` (full version) for document ingestion:

#### Option 1: Install haiku-rag locally

```bash
pip install haiku-rag
```

#### Option 2: Use docling-serve Docker container

```bash
docker run -p 5001:5001 -d \
  -e DOCLING_SERVE_ENABLE_UI=1 \
  quay.io/docling-project/docling-serve
```

If using Option 2, configure `example/haiku.rag.yaml` to use remote processing.

### Step 7: Configure Environment Variables

See the `Environment Variables` section in the [README](README.md) for
an explanation of when to configure Soliplex using OS environment variables.

1. **Copy example environment file**

   ```bash
   cp .env.example .env
   ```

2. **Edit .env file**

   ```bash
   # Linux/macOS
   nano .env

   # Windows
   notepad .env
   ```

3. **Set required variables**

   **For Ollama:**

   ```bash
   OLLAMA_BASE_URL=http://localhost:11434
   ```

   **For OpenAI:**

   ```bash
   OPENAI_API_KEY=sk-proj-your-key-here
   ```

4. **Load environment variables**

   ```bash
   # Linux/macOS
   source .env

   # Windows (PowerShell)
   Get-Content .env | ForEach-Object {
     if ($_ -match '^([^=]+)=(.*)$') {
       [Environment]::SetEnvironmentVariable($matches[1], $matches[2])
     }
   }
   ```

### Step 8: Choose Configuration Profile

Soliplex provides several example configurations:

| Configuration | LLM Provider | Features | Best For |
|--------------|--------------|----------|----------|
| `example/minimal.yaml` | Ollama | Basic rooms, no external APIs | Local development |
| `example/minimal-openai.yaml` | OpenAI | Basic rooms, no external APIs | OpenAI users |
| `example/installation.yaml` | Ollama | Full features + MCP tools | Advanced features |
| `example/installation-openai.yaml` | OpenAI | Full features + MCP tools | Production with OpenAI |

**Recommendation for first-time users**: Start with `minimal.yaml` or `minimal-openai.yaml`.

### Step 9: Initialize RAG Database

The RAG database MUST be initialized before starting the server.

1. **Create database directory**

   ```bash
   mkdir -p db/rag
   ```

2. **Initialize database**

   ```bash
   haiku-rag --config example/haiku.rag.yaml init --db db/rag/rag.lancedb
   ```

3. **Index documentation**

   ```bash
   # Index all documentation
   haiku-rag --config example/haiku.rag.yaml \
     add-src --db db/rag/rag.lancedb docs/

   # You should see:
   # 17 documents added successfully.
   ```

4. **Verify database**

   ```bash
   ls -la db/rag/rag.lancedb/
   ```

### Step 10: Validate Configuration

Check for any missing requirements:

```bash
soliplex-cli check-config example/minimal.yaml
```

This command will report:
- Missing secrets
- Missing environment variables
- Configuration errors

Fix any reported issues before proceeding.

### Step 11: List Available Rooms

Verify your room configuration:

```bash
soliplex-cli list-rooms example/minimal.yaml
```

You should see rooms like:
- `chat` - Conversational RAG with search and document retrieval
- `search` - Search the knowledge base and answer questions
- `joker` - Entertainment/joke generation
- `faux` - Test room

### Step 12: Start Backend Server

```bash
soliplex-cli serve example/minimal.yaml --no-auth-mode
```

Expected output:

```text
INFO:     Started server process [xxxxx]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

The `--no-auth-mode` flag disables authentication for development.

### Step 13: Verify Backend API

In a new terminal, test the API:

```bash
# Test health endpoint
curl http://localhost:8000/health

# List rooms
curl http://localhost:8000/api/v1/rooms

# View OpenAPI docs
# Open browser: http://localhost:8000/docs
```

### Step 14: Install Frontend (Optional)

If you want to use the web UI:

1. **Install Flutter**

   ```bash
   # Follow instructions at https://flutter.dev/docs/get-started/install
   ```

2. **Navigate to Flutter directory**

   ```bash
   cd src/flutter
   ```

3. **Install dependencies**

   ```bash
   flutter pub get
   ```

4. **Run web application**

   ```bash
   flutter run -d chrome --web-port 59001
   ```

5. **Access frontend**
   - Open browser: <http://localhost:59001>
   - Select "localhost" from dropdown
   - Start chatting!

### Step 15: Try TUI (Optional)

For a terminal-based interface:

```bash
# Make sure backend is running with --no-auth-mode
soliplex-tui

# Or specify custom URL
soliplex-tui --url http://localhost:8000
```

## Quick Start Commands Summary

For reference, here's the complete command sequence:

```bash
# Setup
git clone https://github.com/soliplex/soliplex.git
cd soliplex
python3.13 -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install --upgrade pip setuptools
pip install -e .
pip install haiku-rag

# Configure
cp .env.example .env
# Edit .env with your settings
source .env

# Initialize RAG
mkdir -p db/rag
haiku-rag --config example/haiku.rag.yaml init --db db/rag/rag.lancedb
haiku-rag --config example/haiku.rag.yaml add-src --db db/rag/rag.lancedb docs/

# Verify
soliplex-cli check-config example/minimal.yaml
soliplex-cli list-rooms example/minimal.yaml

# Run
soliplex-cli serve example/minimal.yaml --no-auth-mode
```

## Docker Quick Start

If you prefer Docker:

```bash
# Setup
git clone https://github.com/soliplex/soliplex.git
cd soliplex
cp .env.example .env
# Edit .env with your settings

# Initialize RAG database (on host)
python3.13 -m venv venv
source venv/bin/activate
pip install haiku-rag
export OLLAMA_BASE_URL=http://localhost:11434
mkdir -p db/rag
haiku-rag --config example/haiku.rag.yaml init --db db/rag/rag.lancedb
haiku-rag --config example/haiku.rag.yaml add-src --db db/rag/rag.lancedb docs/
deactivate

# Run with Docker
docker-compose up
```

## Troubleshooting

### Python 3.13 not found

- Ensure Python 3.13 is installed and in your PATH
- Try `python3.13 --version` to verify

### Ollama connection refused

- Ensure Ollama service is running: `ollama serve`
- Verify URL is correct in .env file
- Check firewall settings

### RAG database errors

- Ensure database is initialized before starting server
- Check file permissions on db/ directory
- Verify `OLLAMA_BASE_URL` is accessible

### Module not found errors

- Ensure virtual environment is activated
- Reinstall dependencies: `pip install -e .`
- Check Python version: `python --version`

### Port already in use

- Backend (8000): Change with `--port` flag
- Frontend (59001): Change with `--web-port` flag
- Check for other processes: `lsof -i :8000` (Linux/macOS)

## Next Steps

After successful installation:

1. **Explore Configuration**: Review [installation.md](config/installation.md)
2. **Set Up Rooms**: Configure custom rooms in [rooms.md](config/rooms.md)
3. **Configure Agents**: Set up AI agents in [agents.md](config/agents.md)
4. **Enable Authentication**: Configure OIDC in [oidc_providers.md](config/oidc_providers.md)
5. **Deploy with Docker**: Follow [docker.md](docker.md)

## Getting Help

- **Documentation**: <https://soliplex.github.io/>
- **Issues**: <https://github.com/soliplex/soliplex/issues>
- **API Docs**: <http://localhost:8000/docs> (when server is running)
