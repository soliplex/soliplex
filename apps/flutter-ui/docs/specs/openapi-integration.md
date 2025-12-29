# OpenAPI Integration Specification

**Status:** Draft
**Owner:** @runyaga
**Created:** 2025-12-15

## Context

The Flutter frontend currently manually defines data models (`Document`, `Room`, etc.) that mirror the Python backend's Pydantic models. This leads to:
1.  **Duplication**: Logic and schema are defined twice.
2.  **Desynchronization**: Frontend breaks when backend changes (e.g., `documents` vs `document_set`).
3.  **Manual Labor**: Boilerplate code for `fromJson`/`toJson`.

The backend exposes an OpenAPI specification at `/openapi.json` (via FastAPI). We should leverage this to automate client generation.

## Goals

1.  **Automate Model Generation**: Generate Dart classes from OpenAPI schemas.
2.  **Type Safety**: Ensure frontend code is strongly typed against the actual backend API.
3.  **Efficiency**: Reduce manual coding of API services.

## Proposed Workflow

1.  **Fetch Schema**: A script fetches `openapi.json` from the backend (local or staging).
2.  **Generate Client**: Use `openapi-generator-cli` (or a Dart-specific package like `openapi_generator`) to generate Dart code.
3.  **Integrate**: Use the generated models/API clients in the app logic.

## Tooling Options

### Option A: openapi-generator-cli (Official)
-   **Pros**: Industry standard, robust, supports many languages.
-   **Cons**: Requires Java, output can be verbose/heavy (dio/http dependencies).

### Option B: swagger_dart_code_generator (Dart Package)
-   **Pros**: Dart-native, builds `chopper` or `dio` clients, customizable.
-   **Cons**: Might lag behind official spec.

### Recommendation: Option A (with 'dart-dio' or 'dart' generator)

We can generate a standalone package (e.g., `packages/soliplex_api`) inside the monorepo and depend on it.

## Implementation Steps

1.  **Setup**: Add `openapi-generator-cli` to dev dependencies or scripts.
2.  **Scripting**: Create `scripts/generate_api_client.sh`.
    ```bash
    curl http://localhost:8000/openapi.json -o openapi.json
    openapi-generator-cli generate -i openapi.json -g dart -o packages/soliplex_api ...
    ```
3.  **Refactoring**:
    -   Replace manual `Document` model with generated `RAGDocument`.
    -   Replace `fetchDocuments` logic with generated API call.
    -   Ideally, replace `RoomsNotifier` manual calls with API client calls.

## Phased Adoption

1.  **Phase 1**: Generate models only. Use them in existing services (replacing manual `fromJson`).
2.  **Phase 2**: Generate API clients. Replace manual `NetworkTransportLayer` calls with generated client methods (injecting our auth/transport logic if needed, or configuring the generated client).

## Immediate Next Steps

-   Proof of Concept: Generate the client locally and verify the `RoomDocuments` schema matches our findings.
