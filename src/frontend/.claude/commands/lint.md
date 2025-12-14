Run code quality checks.

Python backend:
```bash
cd /Users/jaeminjo/enfold/afsoc-rag/src/soliplex
source venv/bin/activate
ruff check src/soliplex/
ruff format --check src/soliplex/
```

Flutter (soliplex_flutter):
```bash
cd /Users/jaeminjo/enfold/afsoc-rag/src/soliplex/src/soliplex_flutter
flutter analyze
flutter format --set-exit-if-changed .
```
