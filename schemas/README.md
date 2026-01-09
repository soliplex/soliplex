# AG-UI Feature JSON Schemas

This directory contains JSON schemas for AG-UI features defined in the backend.

## About

These schemas are automatically generated from Pydantic models in `src/soliplex/agui/features.py` and define the contract between the Soliplex backend and frontend applications.

## Generating Schemas

To regenerate these schemas after modifying feature models:

```bash
.venv/bin/python scripts/generate_feature_schemas.py
```

## Features

- **filter_documents.json**: Schema for document filtering feature (client-sourced)
- **ask_history.json**: Schema for question/answer history feature (server-sourced)

## Usage

Frontend applications can use these schemas to:
- Generate type-safe client code (e.g., Dart classes)
- Validate AG-UI state structure
- Document the API contract
