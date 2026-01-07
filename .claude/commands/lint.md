Run all linting and formatting for the project with auto-fix enabled.

## Python (src/ and scripts/)

Run these commands in sequence:
```bash
source venv/bin/activate && ruff format src/ scripts/ && ruff check --fix src/ scripts/
```

## Flutter (src/flutter/)

Run these commands in sequence:
```bash
cd src/flutter && dart format lib test && flutter analyze
```

## Instructions

1. Run Python linting first, then Flutter linting
2. Report any issues that couldn't be auto-fixed
3. If there are unfixable issues, help me resolve them
4. Summarize what was formatted/fixed when complete