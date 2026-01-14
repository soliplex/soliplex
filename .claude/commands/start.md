Start all local development services (Ollama, Soliplex backend, Flutter).

Run all three commands in parallel in the background:

1. Start Ollama LLM server:
```bash
/opt/homebrew/bin/ollama serve
```

2. Start Soliplex backend:
```bash
source venv/bin/activate && OLLAMA_BASE_URL=http://127.0.0.1:11434 soliplex-cli serve example/minimal.yaml --no-auth-mode
```

3. Start Flutter web app (from sibling repo):
```bash
cd ../flutter && flutter run -d chrome --web-port 59001 --dart-define=DEFAULT_SERVER_URL=http://localhost:8000
```

Run all three in the background so I can continue working. Wait a few seconds after starting each to check their output and confirm they started successfully. Summarize the status of all services when done.

**Note:** Flutter repo must be cloned at `../flutter` relative to this repo.
