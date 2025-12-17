Run code quality checks.

Python backend:

```bash
cd /Users/jaeminjo/enfold/afsoc-rag/src/soliplex
source venv/bin/activate
ruff format --check src/soliplex/
ruff check src/soliplex/
```

Flutter (soliplex_flutter):

```bash
cd /Users/jaeminjo/enfold/afsoc-rag/src/soliplex/src/soliplex_flutter
flutter format --set-exit-if-changed .
flutter analyze
```
