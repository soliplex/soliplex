# ADR-001: Static Generative UI via Tool Calls

**Date:** 2026-04-13  
**Status:** Accepted

---

## Context

The Soliplex demo needed a way to render interactive UI components — forms,
charts, and similar widgets — directly inside a chat conversation. The first
prototype used a purely client-side approach: the LLM emitted custom fenced
Markdown blocks (e.g. `:::form … :::`) containing JSON, and the Flutter
frontend parsed those blocks into widgets.

While that worked for a proof of concept, a few problems surfaced as the demo
grew:

- **Hallucination risk.** With the constrained `gpt-oss:20b` model in our
  environment, free-form JSON embedded in Markdown is fragile. The model
  frequently produced malformed JSON, mismatched closing delimiters, or mixed
  prose with structured data inside the same block.
- **Coupling of concerns.** Using Markdown as a "logical" layer meant the LLM
  had to reason simultaneously about formatting (prose), rendering (block
  type), and data (JSON schema) in a single token stream. Separating these
  concerns is harder to prompt-engineer and harder to validate.
- **No schema enforcement.** Fenced blocks carry no type-level contract; any
  validation happened inside the Flutter renderer, after the fact.
- **Scalability.** Adding a new component required updating the Markdown parser,
  the block-builder registry, and the system prompt — with no single source of
  truth for the component's data shape.

---

## Decision

We adopted a **static generative UI pipeline** built on AG-UI tool calls:

1. **The Flutter frontend owns the UI components** (forms, charts, …) as
   ordinary Flutter widgets.
2. **The Python backend defines the corresponding "tools"** that represent
   those components, using Pydantic models for the schema.
3. **The LLM decides which tool to call** — it does not generate JSON or
   Markdown for UI; it simply selects a tool and fills in its arguments.

The pipeline runs as follows:

```
User message
    │
    ▼
LLM reasons about intent
    │
    ▼
LLM emits tool call (AG-UI TOOL_CALL_START / TOOL_CALL_ARGS / TOOL_CALL_END)
    │
    ▼
Backend executes tool — validates args via Pydantic, serialises to JSON
    │
    ▼
Backend emits TOOL_CALL_RESULT carrying the JSON spec
    │
    ▼
Flutter receives ServerToolCallCompleted with result
    │
    ▼
Flutter renders matching widget (FormRenderer / StockChartWidget)
```

Markdown remains plain conversational glue. It never carries structured data.

---

## Component granularity

We explicitly chose **coarse, dynamic components** over fine-grained design
primitives.

### Rejected alternative: granular primitives

```python
class UIContainer(BaseModel):
    direction: str        # "row" | "column"
    children: list[str]  # IDs of nested components

class TextInput(BaseModel):
    label: str
    placeholder: str
    width: str           # "50%"

class UIButton(BaseModel):
    text: str
    variant: str         # "primary" | "outline"
```

Building a single form would require the LLM to call 4–6 tools in the correct
order and manage `children` ID references without error. Even for capable
models this is brittle; for a 20b model it is essentially unreliable.

### Chosen approach: coarse dynamic components

```python
class FormField(BaseModel):
    label: str
    field_type: Literal["text", "email", "number", "checkbox", "dropdown"]
    required: bool = True
    placeholder: Optional[str] = None
    options: Optional[list[str]] = None   # for dropdown

class DynamicForm(BaseModel):
    title: str
    fields: list[FormField]
    submit_label: str = "Submit"
```

A complete, interactive form is produced by a **single tool call**. The LLM
fills in a flat list of field descriptors; the Flutter widget handles layout,
validation, and submission internally. The same principle applies to the stock
chart:

```python
class StockBar(BaseModel):
    label: str
    value: float

class StockChart(BaseModel):
    title: str
    symbol: str
    bars: list[StockBar]
    currency: str = "USD"
```

This trade-off sacrifices per-pixel layout control for reliability: the LLM
only needs to understand _what_ to render, not _how_ to compose it.

---

## Why AG-UI tool calls as the transport

Soliplex already uses the AG-UI protocol as its core streaming layer. Tool
calls are a first-class AG-UI concept:

- `TOOL_CALL_START` — LLM signals intent to call a tool
- `TOOL_CALL_ARGS` — arguments streamed incrementally as the LLM generates them
- `TOOL_CALL_END` — arguments complete
- `TOOL_CALL_RESULT` — backend executes the tool and sends the result

Using this existing mechanism means:

- No new protocol surface is needed.
- The backend validates and serialises the tool arguments through Pydantic
  before they reach the client — no client-side JSON parsing of raw LLM output.
- The `TOOL_CALL_RESULT` content (the tool's return value) is what the Flutter
  client renders. The LLM's raw argument tokens are never used directly by the
  UI — they pass through server-side validation first.
- Tool calls are stored in the thread run history alongside text messages,
  so the conversation is fully replayable.

---

## Tool result as the rendering contract

A subtle but important detail: the Flutter widget renders from the **tool
result**, not from the tool call arguments.

```
LLM argument tokens (untrusted) → Pydantic validation → model.model_dump_json()
                                                               │
                                                               ▼
                                                    TOOL_CALL_RESULT.content
                                                               │
                                                               ▼
                                                    Flutter widget renders
```

This means the server always has the final say on what the widget receives. If
the LLM hallucinated a field that doesn't exist in the Pydantic schema, it will
be rejected before reaching the client. The tool return value is the canonical,
validated spec.

---

## Structured prompting

Because the 20b model is prone to hedging — generating prose descriptions of
the widget before calling the tool — the room configuration includes:

- An explicit instruction to call tools **immediately**, without preamble
- Few-shot examples showing the exact tool call for each widget type
- A rule that Markdown tables and prose descriptions are forbidden for data that
  belongs in a widget

This is enforced in `example/rooms/demo/room_config.yaml` under `system_prompt`.

---

## Consequences

**Benefits:**
- The LLM cannot produce a malformed widget spec; Pydantic rejects it at the
  tool boundary.
- Adding a new component requires: one Pydantic model + tool function on the
  backend, one Flutter widget + a `case` in `_GenUiBubble`, and one entry in
  the room config. No parser changes.
- Markdown stays clean — it is never parsed for structure.
- Tool calls are logged and replayable in the AG-UI thread history.

**Limitations:**
- Component flexibility is bounded by the pre-defined schema. Layout
  customisation beyond what the Pydantic model exposes requires a code change.
- Each new widget type requires a backend deployment. A fully dynamic approach
  (e.g. server-driven UI over JSON schema) would avoid this, but at significant
  complexity cost for a 20b model.
- The LLM still needs to choose the right tool. With only two tools and clear
  few-shot examples this is reliable, but could degrade as the tool palette
  grows without careful prompt hygiene.

---

## Alternatives considered

| Approach | Reason rejected |
|---|---|
| Fenced Markdown blocks (`:::form`) | Fragile JSON generation; no server-side validation; mixes concerns in the token stream |
| Fine-grained UI primitives (rows, columns, text inputs) | Requires multi-step tool orchestration that exceeds the 20b model's reliable capability |
| Server-driven UI over a generic JSON schema | Powerful but complex to prompt-engineer; no schema safety at the boundary |
| Chainlit / MSFT Agent Framework components | Would require adopting a new framework on top of the existing AG-UI infrastructure; evaluated but out of scope for this demo |
