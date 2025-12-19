## Subsystem Analysis

We have analyzed the four key subsystems involved in the AG-UI integration. See the detailed internal documentation for "how it works TODAY":

1.  [Backend Agent State](docs/internals/backend-agent-state.md): How `pydantic-ai` dependencies are configured and where the state injection happens.
2.  [Backend API & Protocol](docs/internals/backend-api-protocol.md): The REST endpoints and SSE streaming architecture.
3.  [Frontend Thread Manager](docs/internals/frontend-thread-manager.md): The Dart `Thread` class that orchestrates the event loop.
4.  [Frontend State Provider](docs/internals/frontend-state-provider.md): How the "Canvas" state is modeled, serialized, and shared.

### Phase 1: The "Loose Contract" (Fix & Document)
**Goal:** Establish immediate reliability by fixing known protocol breaches and documenting the implicit "JSON blob" structure.

**Description:**
Currently, the system crashes if the client sends state because the backend's `AgentDependencies` fails the `StateHandler` protocol.
1.  **Backend Fix:** Update `AgentDependencies` in `src/soliplex/agents.py` to be a `dataclass` with a required `state: dict` field. This enables the `pydantic-ai` integration to actually work.
2.  **Schema Documentation:** Create `docs/specs/agui_state_schema.md` defining the expected JSON structure (e.g., `{ "canvas": [{ "id": "...", "type": "..." }] }`).
3.  **Client:** Continue sending `Map<String, dynamic>`, but developers now have a reference document to avoid typos.

*   **PROs:**
    *   **Speed:** Can be implemented in hours.
    *   **Low Friction:** No new build steps or heavy refactoring.
    *   **Immediate Fix:** Solves the critical "UserError" crash mentioned in docs.
*   **CONs:**
    *   **Fragile:** "Stringly typed." A typo in a key name (`cnavas` vs `canvas`) won't be caught until runtime.
    *   **Manual Sync:** If backend changes expectations, docs must be manually updated (drift is inevitable).
*   **Value (Reliability/DX):** **Reliability +1** (stops crashes). **DX +1** (documented expectations vs guessing).

---

### Phase 2: The "Typed Contract" (Code Generation)
**Goal:** Eliminate runtime errors and manual synchronization by generating code from a shared source of truth.

**Description:**
Instead of `Map<String, dynamic>`, we define the State structure formally.
1.  **Source of Truth:** Define the State in Python using Pydantic models (e.g., `src/soliplex/agui/schema.py`).
2.  **Code Gen:** Use a tool (custom script or `pydantic-to-dart` generator) to generate Dart `freezed` classes (e.g., `lib/infrastructure/agui/dtos/state.dart`).
3.  **Validation:** The backend explicitly validates incoming state against the Pydantic model before the agent sees it. The frontend uses the generated Dart classes to build the state.

*   **PROs:**
    *   **Type Safety:** Compile-time errors if fields are missing or mismatched.
    *   **Auto-complete:** IDEs (VS Code/IntelliJ) can autocomplete state fields on both ends.
    *   **Versioning:** Easier to detect breaking changes during PR reviews (the generated code changes).
*   **CONs:**
    *   **Complexity:** Adds a build step (running the generator).
    *   **Rigidity:** Changing the state structure requires updating the schema and regenerating code.
*   **Value (Reliability/DX):** **Reliability +3** (malformed state is impossible). **DX +3** (Intellisense, confidence in refactoring).

---

### Phase 3: The "Capabilities Protocol" (Dynamic Discovery)
**Goal:** Allow the frontend to dynamically adapt to the backend's capabilities, answering "what state(s) are available?" at runtime.

**Description:**
This addresses the core question of "knowing what interaction/states are available."
1.  **Room Manifest:** When the client enters a Room (or calls `GET /agui/{thread_id}/meta`), the server returns a `Capabilities` object:
    ```json
    {
      "supported_states": ["canvas", "chat", "terminal"],
      "input_modes": ["text", "voice"],
      "widgets": ["GraphWidget", "CodeBlockWidget"]
    }
    ```
2.  **Dynamic UI:** The Flutter client reads this manifest. If `canvas` is missing from `supported_states`, the Canvas tab is hidden. If `terminal` is present, a Terminal panel is mounted.
3.  **State Slice Pattern:** The global "State" is broken into slices. The protocol only syncs the slices declared in the manifest.

*   **PROs:**
    *   **Decoupling:** One frontend app can serve many different "Agent Types" (e.g., a "Designer Agent" with a Canvas vs. a "Coder Agent" with a Terminal) without code changes.
    *   **Clarity:** The client *knows* exactly what the backend supports for this specific thread.
    *   **Future-Proof:** New capabilities can be added to the backend without breaking older clients (they just ignore what they don't understand).
*   **CONs:**
    *   **High Complexity:** Requires a robust "Module/Plugin" architecture in the frontend to dynamically load UI components.
    *   **Overhead:** More initial handshake logic.
*   **Value (Reliability/DX):** **Reliability +5** (Client never attempts unsupported actions). **DX +4** (Clear "Feature Flag" system for developing new Agent capabilities).

### Recommendation
Start with **Phase 1** immediately to unblock `StateHandler` usage. Move to **Phase 2** rapidly to sanitize the development process. **Phase 3** is a long-term architectural goal for when you have multiple distinct Agent types.