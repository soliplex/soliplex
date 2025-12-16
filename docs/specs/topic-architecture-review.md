# Architectural Review: AG-UI State & System Evolution

This document logs critical architectural considerations for the AG-UI system, specifically focusing on State Management, Evolution, and Edge Cases.

## 1. State Evolution & Schema Management
*   **The Challenge:** JSON state blobs persist in the DB, but code changes frequently.
*   **Strategies:**
    *   **Slice Isolation:** Wrap parsing of each state slice (`rag_filters`, `canvas`) in independent `try/catch` blocks. A corruption in one should not crash the whole app.
    *   **Tolerant Parsing:** Use "Postel's Law" (liberal acceptance). Ignore unknown fields. Use defaults for missing fields.
    *   **Abandonment:** For simple chat apps, it is often acceptable to reset invalid state to default rather than writing complex migration scripts.
    *   **Versioning:** Consider explicit `_v: 1` fields if complex migrations are ever needed.

## 2. Concurrency (The "Two Tabs" Problem)
*   **Scenario:** User opens the same thread in two places.
*   **Conflict:** "Last Writer Wins" is the default behavior with HTTP POST.
*   **Mitigation:** Acceptable for single-user scenarios. For multi-user or high-fidelity apps, would require Optimistic Locking (`version` check) or WebSockets.

## 3. Bandwidth & Token Budget (The "Fat State" Problem)
*   **Scenario:** State grows large (e.g., large code snippets in Canvas).
*   **Risk:** Sending 100KB of JSON with *every* chat message spikes latency and data usage.
*   **LLM Risk:** Feeding raw large JSON to the LLM consumes context window and confuses the model.
*   **Mitigation:**
    *   **Prompting:** Backend must summarize state for the LLM (e.g., "Canvas: 3 items" vs raw JSON).
    *   **Reference Storage:** Store large content by ID/URL, not value.

## 4. Security
*   **Principle:** **State is Untrusted User Input.**
*   **Risk:** Injection attacks via state fields.
*   **Rule:** Never use state values for authorization checks or SQL construction.

## 5. Shared Threads & Multi-User Rehydration
**Scenario:** User A shares a link to Thread T with User B.

### Rehydration Analysis
If we adopt the **Golden Snapshot (Scenario 2)** persistence model, rehydration is mostly solved:
*   **Core State (Canvas, Citations):** User B receives the `latest_state` JSON from the DB. They see the exact same content as User A.
*   **Missing State (Local/Ephemeral):**
    *   *UI State:* Scroll position, expanded/collapsed sections, draft input text. (Expected behavior: Reset).
    *   *Identity-Specific Data:* If the state mistakenly included `user_preferences` specific to User A (e.g., "High Contrast Mode"), User B inherits them weirdly.
    *   **Rule:** Shared State must be strictly **Content-Related**, not **Session-Related**.

### Identity & Privacy Risks
*   **PII Leakage:** If User A's `rag_filters` included `author: "me"`, User B's view might be broken or confusing.
*   **Permissions:** If User B is "Read-Only", the Frontend must know to **disable** the widgets that modify state (e.g., gray out the Filter controls). This requires a separate `permissions` flag in the API response, independent of the State blob.

## 6. Recommendations
1.  **Implement "Golden Snapshot" Persistence:** Add `latest_state` to the Thread table.
2.  **Strict "Slice" Parsing:** Update Flutter code to safely parse `rag_filters` separate from `canvas`.
3.  **Prompt Sanitization:** Ensure the Backend "Renderer" summarizes state before giving it to the LLM.
4.  **Audit Logs:** Log state changes for debugging "Why did the agent do that?"
