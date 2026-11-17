# A2UI Surfaces

A room's agent can show the user an [A2UI](https://a2ui.org/) surface: a
card, a list, a form, rendered by the client with its own widgets. Soliplex
sends surfaces and receives the user's actions over the existing AG-UI run
endpoints, in the shapes `@ag-ui/a2ui-middleware` uses, so an A2UI renderer
written for AG-UI reads them unchanged. The surfaces use A2UI protocol 1.0
and its basic catalog.

The protocol helpers and the generation capability live in the
[`soliplex-a2ui`](https://github.com/ggozad/soliplex-a2ui) package.

## Wire format

- **Server to client.** A surface arrives as an `ACTIVITY_SNAPSHOT` event
  with `activityType: "a2ui-surface"`, `messageId:
  "a2ui-surface-<tool call id>"`, `replace: true`, and
  `content: {"a2ui_operations": [...]}` holding the surface's A2UI
  messages (`createSurface`, `updateComponents`, `updateDataModel`). The
  event is stored with the run's other events.
- **Client to server.** A user action starts the next run, with the action
  in `forwardedProps`:

  ```json
  {"a2uiAction": {"userAction": {
    "name": "bookMeeting",
    "surfaceId": "surface_call_1",
    "sourceComponentId": "submitButton",
    "timestamp": "2026-11-12T11:55:54.653Z",
    "context": {"title": "A2UI review"}
  }}}
  ```

  Soliplex appends it to the run's messages as a user message whose content
  is `A2UI user action:` followed by the action as JSON, and whose `name`
  is `a2ui_action_context_` followed by a hash of the run id. A client can
  recognise action messages by that name and hide them. Any JSON object
  under `userAction` is forwarded; its fields are not checked.

## Generated surfaces

The `A2UICapability` agent capability, registered by default, gives the
room's agent a `generate_a2ui(description, data)` tool:

```yaml
agent:
  template_id: "default_chat"
  capabilities:
    - name: "A2UICapability"
```

- The agent describes the surface in words and passes the values it shows
  as `data`.
- A separate generating agent writes the components. Only it receives the
  catalog (about 29 KB), so the room agent's requests do not grow.
- The surface's data model is `data` exactly as the agent passed it, and
  components bind to it with `{"@path": ...}`.
- Every surface passes `a2ui-core`'s strict validation before it is shown:
  known components with valid properties, unique ids, a `root` component,
  resolvable child references, no cycles. An invalid layout is retried;
  when the retries run out, nothing is shown and the agent is told why.
- The generating agent runs on the room agent's model and counts towards
  the run's usage and usage limits.

`kwargs` accepts `max_retries` (default 3) and `model`, a pydantic-ai model
name to generate with instead of the room agent's model.

A generated surface costs at least one extra model request with the
catalog, and takes noticeably longer than a text answer.

## Surfaces from a tool

A tool can build a surface itself and return it in `ToolReturn.metadata`:

```python
import pydantic_ai
import soliplex_a2ui


async def show_form(ctx: pydantic_ai.RunContext) -> pydantic_ai.ToolReturn:
    operations = [...]  # A2UI 1.0 messages for one surface
    return pydantic_ai.ToolReturn(
        return_value="Showed the form.",
        metadata=[soliplex_a2ui.surface_event(ctx.tool_call_id, operations)],
    )
```

`soliplex.examples.a2ui_name_form` is a complete example.

## Example rooms

- `example/rooms/a2ui`: a tool-built name form, and the agent greeting the
  user by the submitted name.
- `example/rooms/a2ui_generate`: generated cards, tables and forms.

## Clients

The soliplex Flutter frontend does not render A2UI surfaces yet. The
`soliplex-a2ui` repository has a single-page test client,
`harness/index.html`, which renders a room's surfaces with `@a2ui/lit` and
sends the user's actions back; see its README.
