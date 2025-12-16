# Use Case: RAG Query with Filtering

**Goal:** Allow a user to apply specific filters (e.g., "date range", "document type", "source") to their RAG query via a UI widget, ensuring these filters are respected by the backend agent.

**Actors:**
*   **User:** Interacts with the Flutter UI.
*   **Frontend (Flutter):** Manages the "Filter Widget" state and the AG-UI conversation.
*   **Backend (Python):** The Agent executing the RAG query.

## Interaction Steps

1.  **Filter Selection (Frontend)**
    *   The user opens a "Search Filters" widget in the UI.
    *   The user selects criteria (e.g., `type="pdf"`, `year="2024"`).
    *   **Internal Action:** The Frontend updates its local `SearchFilterState`.
    *   **Implicit Contract:** The state is serialized to JSON:
        ```json
        {
          "rag_filters": {
            "file_types": ["pdf"],
            "date_range": { "start": "2024-01-01", "end": "2024-12-31" }
          }
        }
        ```

2.  **Query Submission (Frontend -> Backend)**
    *   The user types a question (e.g., "What are the Q3 earnings?") and hits "Send".
    *   **Action:** The Frontend initiates a new AG-UI Run.
    *   **Payload:**
        *   `messages`: `[{"role": "user", "content": "What are the Q3 earnings?"}]`
        *   `state`: The serialized JSON from Step 1 (`{ "rag_filters": ... }`).

3.  **State Injection (Backend)**
    *   The Backend receives the `RunAgentInput`.
    *   The `rag_filters` dictionary is injected into `ctx.deps.state`.

4.  **Agent Execution (Backend)**
    *   The Agent analyzes the user prompt ("Q3 earnings") and decides to call the retrieval tool.
    *   **Action:** The Agent calls `retriever.search(query="Q3 earnings")`.
    *   **Enforcement:** Inside the tool implementation, the code reads `ctx.deps.state.get("rag_filters")` and applies the constraints (e.g., `type="pdf"`) directly to the database query.
    *   *Note:* The LLM does not need to be aware of the specific filters to enforce them; the tool handles this deterministically.

5.  **Response Generation (Backend -> Frontend)**
    *   The Agent generates a response based on the filtered documents.
    *   The response streams back to the user.

## Contract Requirements
*   **State Key:** `rag_filters` (Must be agreed upon by both sides).
*   **Schema:** The backend tool *must* support the exact structure of the filters sent by the frontend (or perform validation/adaptation).
*   **Persistence:** If the user changes filters *during* a conversation, the next message sent must include the *updated* state. The backend does not persist state across runs; the client is the source of truth.
