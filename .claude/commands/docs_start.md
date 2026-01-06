Start the MkDocs documentation server and open in browser.

## Instructions

1. First, build fresh documentation:
```bash
source venv/bin/activate && mkdocs build
```

2. Start the mkdocs server in the background:
```bash
source venv/bin/activate && mkdocs serve
```

3. Open the browser to view the docs:
```bash
open http://127.0.0.1:8001/soliplex/
```

Run the server in the background so I can continue working. Confirm when the docs are accessible in the browser.

## Notes

- Docs are served at http://127.0.0.1:8001/soliplex/
- Server auto-reloads when doc files change
- To stop: `pkill -f "mkdocs serve"`