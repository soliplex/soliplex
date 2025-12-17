Start the Soliplex backend server for local development.

Run from the project root:

```bash
cd /Users/jaeminjo/enfold/afsoc-rag/src/soliplex
source venv/bin/activate
LOGFIRE_TOKEN=pylf_v1_us_Sh08ndsT5jDZfhk7S3099gN1Mg3mQRvT4bqv9HRhpYB2 OLLAMA_BASE_URL=http://localhost:11434 soliplex-cli serve example/minimal.yaml --no-auth-mode
```

The server runs on <http://localhost:8000> by default.
