# Troubleshooting

This guide helps you diagnose and resolve common issues with Soliplex.

## Common Issues

### OLLAMA_BASE_URL Not Set

**Symptom**: Server fails to start with `MissingEnvVar: Environment variable 'OLLAMA_BASE_URL' cannot be resolved`

**Solution**: Set the environment variable before starting the server:

```bash
OLLAMA_BASE_URL=http://127.0.0.1:11434 soliplex-cli serve example/minimal.yaml --no-auth-mode
```

Or export it in your shell configuration:

```bash
export OLLAMA_BASE_URL=http://127.0.0.1:11434
```

---

### Slow LLM Inference / GPU Not Detected

**Symptom**: Responses are extremely slow (1-5 tokens/sec instead of 50+)

**Cause**: Ollama may be running as an x86_64 binary under Rosetta on Apple Silicon

**Diagnosis**:
```bash
# Check if Ollama is using GPU
ollama ps
# If "Processor" shows 100% CPU instead of GPU, this is the issue

# Check binary architecture
file $(which ollama)
# Should show "arm64" on Apple Silicon
```

**Solution** (Apple Silicon):
```bash
# Install ARM64 version via Homebrew
/opt/homebrew/bin/brew install ollama

# Verify it's ARM64
file /opt/homebrew/bin/ollama
# Should show: Mach-O 64-bit executable arm64
```

---

### Authentication Token Expired

**Symptom**: API requests return 401 Unauthorized after a period of time

**Solution**:
1. Re-authenticate through the OIDC flow
2. Check `MCP_TOKEN_MAX_AGE` if using MCP tokens
3. Verify OIDC provider token expiration settings

---

### RAG Database Not Found

**Symptom**: Document search returns no results or errors

**Diagnosis**:
```bash
# Check if database exists
ls -la db/rag/

# Verify configuration
grep -r "rag_lancedb" example/minimal.yaml
```

**Solution**:
1. Ensure `RAG_LANCE_DB_PATH` points to correct location
2. Ingest documents using haiku-rag CLI
3. Check room-level RAG configuration

---

### MCP Connection Failures

**Symptom**: External MCP tools unavailable or timing out

**Diagnosis**:
- **Stdio MCP**: Check if command exists and has correct permissions
- **HTTP MCP**: Verify network connectivity and authentication

```bash
# Test stdio MCP command
npx -y @modelcontextprotocol/server-google-maps
```

---

### Flutter App Can't Connect to Backend

**Symptom**: Flutter app shows connection errors

**Checklist**:
1. Backend is running on port 8000
2. Correct URL entered in Flutter app (http://localhost:8000, not 59001)
3. No CORS issues (check browser console)
4. Backend started with `--no-auth-mode` for development

---

## Debug Logging

Enable verbose logging:

```bash
# Set log level
LOG_LEVEL=DEBUG soliplex-cli serve example/minimal.yaml --no-auth-mode
```

See [Debugging Guide](debugging.md) for more details.

## FAQ

### Can I use multiple LLM providers?

Yes. Configure different agents with different `provider_type` settings (ollama or openai).

### How do I add documents to RAG?

Use the haiku-rag CLI to ingest documents into LanceDB. See [RAG Database](../developer-guide/rag/database.md).

### What ports does Soliplex use?

| Port | Service |
|------|---------|
| 8000 | Backend API |
| 59001 | Flutter dev server |
| 11434 | Ollama |

### How do I reset my conversation history?

Thread data is stored in SQLite. For development, restart with a fresh database or use the delete thread API.

## Getting More Help

- Check [GitHub Issues](https://github.com/soliplex/soliplex/issues)
- Search existing discussions
- File a new issue with:
  - Soliplex version
  - OS and architecture
  - Relevant configuration (redact secrets)
  - Error messages and logs
