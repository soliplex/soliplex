# Stop Backend

Stop the Soliplex backend server running on port 8000.

```bash
pkill -f "soliplex-cli serve" || lsof -ti:8000 | xargs kill -9 2>/dev/null || echo "No backend process found"
```
