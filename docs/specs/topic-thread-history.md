# Topic: Thread History & State Restoration

## The Core Challenge
When a user switches devices (or refreshes the browser), **Local State** (Flutter Providers) is lost.
*   **Filters (Frontend Origin):** The "PDF Only" toggle resets to default. The user loses their configuration.
*   **Citations (Backend Origin):** The data backing the `[1]` tooltip is missing. The chat history shows "Report [1]", but the link is dead/unclickable because the `citations` map is empty.

To support multi-device continuity, the **State** must be persisted alongside the **Message History**.

---

## Scenario 1: The "Forensic" Rehydration (Client-Side Logic)
*Relies on existing data structures (Runs/Inputs) without new server storage.*

**Concept:** The backend already stores the `RunAgentInput` (what the client sent) and the events (what the agent sent) for every run. The client "reconstructs" the state by analyzing the history.

### Workflow
1.  **Filters (Frontend -> Backend):**
    *   When loading the thread, the client fetches the **Last Run**.
    *   It inspects `last_run.run_input.state["rag_filters"]`.
    *   The UI "Search Filters" widget initializes itself with these values.
    *   *Result:* User sees their previous filters.
2.  **Citations (Backend -> Frontend):**
    *   The client must fetch **All Past Runs** (or the full event log).
    *   It scans the event streams for `STATE_DELTA` events.
    *   It rebuilds the `citations` map delta-by-delta (replaying the game).
    *   *Result:* Tooltips work again.

*   **Pros:** Zero backend schema changes.
*   **Cons:** Expensive network payload (fetching all runs/events). Complex client logic. Performance degrades with thread length.

---

## Scenario 2: The "Golden Snapshot" (Server-Side Persistence)
*Treats "State" as a first-class citizen of the Thread.*

**Concept:** The `Thread` entity in the database gets a new `current_state` JSON column which represents the *latest agreed-upon state* of the conversation.

### Workflow
1.  **Persistence (Server-Side):**
    *   **Inbound (Filters):** When the client sends `state` in a `run_input`, the server updates/merges this into `thread.current_state`.
    *   **Outbound (Citations):** When the Agent emits a `STATE_DELTA`, the server *also* applies this patch to `thread.current_state`.
2.  **Restoration (Client-Side):**
    *   Device B calls `GET /thread/123`.
    *   Response includes `{"state": { "rag_filters": {...}, "citations": {...} }}`.
    *   Device B calls `stateProvider.init(response.state)`.

*   **Pros:** Instant loading. Simple client logic. Truly persistent "Context".
*   **Cons:** Server must handle JSON merging (or simplistic replacement). State object can grow large if uncontrolled.

---

## Scenario 3: The "Hybrid" (Session vs. Content)
*Distinguishes between "Context" and "Content".*

**Concept:** Split the problem based on the lifecycle of the data.

### Workflow
1.  **Filters (Context):** treated as **Sticky Metadata**.
    *   Stored in `Thread.metadata` (which already exists).
    *   When user changes filters, client calls `POST /thread/123/meta`.
    *   *Restoration:* New Device loads metadata and sets UI.
2.  **Citations (Content):** treated as **Message Attachments**.
    *   Instead of global "State", citation data is embedded in the `Message` object itself (e.g., `Message.attachments` or `Message.data`).
    *   *Restoration:* When loading history, the "Message" comes with its own "Footnotes".

*   **Pros:** Clean semantic separation.
*   **Cons:** Requires refactoring Citations from "Global State" to "Per-Message Data". Breaks the "AG-UI State" paradigm for citations.

---

## Recommendation: Scenario 2 (Golden Snapshot)

For the AG-UI architecture, **Scenario 2** is the most robust alignment with the "State" concept.

1.  **Uniformity:** It handles both directions (Client->Server Filters, Server->Client Citations) with a single mechanism.
2.  **Correctness:** It solves the "Dead Link" citation problem definitively without replaying history.
3.  **Persistence:** It allows the "Filters" to persist as user preference for that specific thread, which is the expected behavior.

### High-Level Requirements

*   **DB:** `Thread` table adds `latest_state: JSONB`.
*   **API:** `GET /thread/{id}` returns this field.
*   **Backend Logic:** `AGUI_Persistence` updates this field:
    *   On `new_run`: Merge `run_input.state`.
    *   On `save_events`: Merge `STATE_DELTA` events.
