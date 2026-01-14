# 5-Minute Quickstart

Get Soliplex running locally with minimal configuration.

## Prerequisites

Before starting, ensure you have:

- **Python 3.13+** - Check with `python3 --version`
- **Ollama** - Install from [ollama.com](https://ollama.com)
- **Git** - Any recent version

## Step 1: Clone and Install

```bash
# Clone the repository
git clone https://github.com/soliplex/soliplex.git
cd soliplex

# Create virtual environment
python3.13 -m venv venv
source venv/bin/activate

# Install Soliplex
pip install -e .
```

## Step 2: Pull an LLM Model

```bash
# Start Ollama (if not already running)
ollama serve &

# Pull a model (gpt-oss is the default for minimal config)
ollama pull gpt-oss
```

!!! tip "Model Options"
    You can use any Ollama model. Update `model_name` in the config if using a different one.

## Step 3: Start the Backend

```bash
# Set Ollama URL and start server
OLLAMA_BASE_URL=http://127.0.0.1:11434 \
  soliplex-cli serve example/minimal.yaml --no-auth-mode
```

You should see:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
```

## Step 4: Use a Client

Choose one of these options:

### Option A: TUI (Terminal UI)

```bash
# Install TUI dependencies
pip install -e ".[tui]"

# Run the TUI client
soliplex-tui --url http://localhost:8000
```

### Option B: Flutter Web App

The Flutter frontend is maintained separately. To use it:

```bash
# Clone the Flutter repo
git clone https://github.com/soliplex/flutter ../flutter
cd ../flutter
flutter pub get
flutter run -d chrome --web-port 59001 --dart-define=DEFAULT_SERVER_URL=http://localhost:8000
```

## Step 5: Chat!

**TUI:**

1. Select a room from the list
2. Type a message and press Enter

**Flutter:**

1. Open http://localhost:59001 in your browser
2. Enter `http://localhost:8000` as the server URL
3. Open the navigation drawer (☰) and select a room
4. Type a message and press Enter

## What's Running

| Service | URL | Purpose |
|---------|-----|---------|
| Backend | http://localhost:8000 | API server |
| Ollama | http://localhost:11434 | LLM inference |
| Flutter (optional) | http://localhost:59001 | Web UI |

## Stopping Services

```bash
# Stop TUI/Flutter: Ctrl+C in client terminal
# Stop Backend: Ctrl+C in backend terminal
# Stop Ollama:
pkill ollama
```

## Next Steps

- [Full Installation](installation.md) - Detailed setup with all options
- [First Chat](first-chat.md) - Understand the chat interface
- [Room Configuration](../admin-guide/configuration/rooms.md) - Customize chat rooms

## Troubleshooting

### "OLLAMA_BASE_URL not set"

Make sure to include the environment variable:
```bash
OLLAMA_BASE_URL=http://127.0.0.1:11434 soliplex-cli serve ...
```

### "Model not found"

Pull the model first:
```bash
ollama pull gpt-oss
```

### Slow responses

Check if Ollama is using GPU:
```bash
ollama ps
```

If showing 100% CPU, see [Troubleshooting GPU Issues](../troubleshooting/index.md#slow-llm-inference-gpu-not-detected).
