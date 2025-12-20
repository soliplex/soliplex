# Debugging Guide

How to diagnose and resolve common issues.

## Common Issues

### OLLAMA_BASE_URL Not Set

**Error:** Connection refused to Ollama

**Solution:**
```bash
# Set environment variable
export OLLAMA_BASE_URL=http://localhost:11434

# Or in installation.yaml
environment:
  - name: "OLLAMA_BASE_URL"
    value: "http://localhost:11434"
```

### GPU Not Detected (macOS ARM64)

**Issue:** Ollama running under Rosetta, not using GPU

**Solution:**
```bash
# Check architecture
file $(which ollama)
# Should say: arm64, not x86_64

# Reinstall native version
brew uninstall ollama
arch -arm64 brew install ollama
```

### Auth Token Expired

**Error:** 401 Unauthorized

**Solution:**
1. Clear browser storage
2. Re-authenticate via login
3. Check token refresh is working

### RAG Database Not Found

**Error:** `RAG DB file not found: /path/to/db.lancedb`

**Solution:**
1. Verify database exists: `ls -la db/rag/`
2. Check `rag_lancedb_stem` matches database name
3. For override paths, check path is relative to config file

### MCP Connection Failed

**Error:** MCP client cannot connect

**Solution:**
1. Verify MCP server is running
2. Check URL and headers are correct
3. For stdio, verify command is in PATH
4. Check `allowed_tools` matches actual tool names

## Debug Logging

### Enable Debug Mode

```yaml
environment:
  - name: "LOG_LEVEL"
    value: "DEBUG"
```

Or via CLI:
```bash
LOG_LEVEL=DEBUG soliplex-cli serve installation.yaml
```

### Log Output

Logs are written to stdout. Capture with:

```bash
soliplex-cli serve installation.yaml 2>&1 | tee debug.log
```

### Specific Component Logging

```python
import logging

# Enable SQL query logging
logging.getLogger('sqlalchemy.engine').setLevel(logging.DEBUG)

# Enable HTTP request logging
logging.getLogger('httpx').setLevel(logging.DEBUG)
```

## SSE Stream Debugging

### View Raw SSE Events

```bash
curl -N \
    -H "Authorization: Bearer $TOKEN" \
    -H "Accept: text/event-stream" \
    "http://localhost:8000/api/v1/rooms/research/agui/$THREAD/$RUN"
```

### Expected Events

```
event: RUN_STARTED
data: {"type": "RUN_STARTED", "run_id": "..."}

event: TEXT_MESSAGE_START
data: {"type": "TEXT_MESSAGE_START", "message_id": "..."}

event: TEXT_MESSAGE_CONTENT
data: {"type": "TEXT_MESSAGE_CONTENT", "delta": "Hello"}

event: TEXT_MESSAGE_END
data: {"type": "TEXT_MESSAGE_END"}

event: RUN_FINISHED
data: {"type": "RUN_FINISHED"}
```

## Configuration Validation

### Check Configuration

```bash
soliplex-cli check-config installation.yaml
```

### List Secrets

```bash
soliplex-cli list-secrets installation.yaml
```

Expected output:
```
- OPENAI_API_KEY      MISSING
- URL_SAFE_TOKEN_SECRET    OK
```

### List Environment

```bash
soliplex-cli list-environment installation.yaml
```

### List Rooms

```bash
soliplex-cli list-rooms installation.yaml
```

## Database Debugging

### SQLite

```bash
# Open database
sqlite3 data/threads.db

# List tables
.tables

# Query threads
SELECT * FROM threads LIMIT 5;
```

### PostgreSQL

```bash
psql -h localhost -U soliplex -d soliplex

# List tables
\dt

# Query threads
SELECT * FROM threads LIMIT 5;
```

## LLM Debugging

### Test Ollama Connection

```bash
curl http://localhost:11434/api/tags
```

### Test Model

```bash
curl http://localhost:11434/api/generate \
    -d '{"model": "gpt-oss:latest", "prompt": "Hello"}'
```

### Check Model is Loaded

```bash
ollama ps
```

## Flutter Debugging

### Browser Console

1. Open browser dev tools (F12)
2. Check Console tab for errors
3. Check Network tab for failed requests

### Flutter DevTools

```bash
flutter run -d chrome --web-port 59001
# Open Flutter DevTools URL shown in output
```

### Common Flutter Issues

| Issue | Solution |
|-------|----------|
| CORS errors | Check backend allows origin |
| WebSocket fails | Use SSE instead |
| Token not sent | Check auth provider |

## Network Debugging

### Check Backend is Running

```bash
curl http://localhost:8000/api/v1/installation
```

### Check Authentication

```bash
# Get token (dev mode)
curl http://localhost:8000/login

# Use token
curl -H "Authorization: Bearer $TOKEN" \
    http://localhost:8000/api/v1/rooms
```

### Check Firewall

```bash
# Linux
sudo iptables -L

# macOS
sudo pfctl -s rules
```

## Performance Debugging

### Slow Responses

1. Check Ollama GPU usage: `nvidia-smi` or `ollama ps`
2. Check model size vs available memory
3. Check network latency to LLM provider
4. Enable Logfire for detailed timing

### Memory Issues

```bash
# Check process memory
ps aux | grep soliplex

# Docker stats
docker stats
```

## Getting Help

1. Check this troubleshooting guide
2. Search existing GitHub issues
3. Enable debug logging and collect logs
4. Create a new issue with:
   - Soliplex version
   - Configuration (redact secrets)
   - Error messages
   - Debug logs
