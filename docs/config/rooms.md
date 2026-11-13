# Room Configuration Filesystem Layout

A room is configured via a directory, whose name is the room ID.

**NOTE:** directories whose names start with '.' are ignored.

Within that directory should be one or two files:

- `room_config.yaml` holds metadata about the room (see below)

- `prompt.txt` (if present) holds the system prompt for conversations
  which are initiated from the room.

Example layout without external prompt file:

```yaml
simple/
    room_config.yaml

```

```yaml
chat/
    prompt.txt
    room_config.yaml
```

## Room Configuration File Schema

### Required room elements

The `room_config.yaml`  file should be a mapping, with at least
the following required elements:

- `id` (a string) should match the name of the room's directory.
  `soliplex-cli audit rooms` reports a room whose `id` does not match as
  a finding.

- `name` (a string) is the "title" of the room, as would be shown in a list.

- `description` (a string) tells the purpose of the room:  it might show up
  as the "lede" graph (below the `name`) in a list of rooms.

- `agent` (a mapping, see next section)

A minimal room configuration must include the above elements, e.g.:

  ```yaml
  id: "chat"
  name: "Chatting Darkly"
  description: "Scanning for conversations"
  agent:
    system_prompt: |
        You are an..... #
  ```

### Optional room elements (UI-related)

- `welcome_message` (a string), for the UI to display when the user
  enters a room.  E.g.:

  ```yaml
  welcome_message: >
      Welcome to the room.  We hope you find it useful

      Please review the suggestions below for ideas on the kinds
      of questions for which this room is intended.
  ```

- `suggestions` (a list of strings) contains possible "starter questions"
  for the room, which the UI might display as shortcuts when the user
  enters the room.  E.g.:

  ```yaml
  suggestions:
    - "How high is up?"
    - "Why is the sky blue?"
  ```

- `agui_feature_names` (list of strings); if set these values are added
  to the feature names defined on the room's agent, tools, and skills
  to create an aggregate set for the room.  Each name must resolve to a
  registered AG-UI feature; see [AG-UI Features](agui.md).

- `logo_image` (a string, default unset) is a path to an image file that
  the UI can display as the room's logo.  The path is resolved against
  the room's configuration directory, and must resolve (following any
  symlinks) to a file inside it:  an absolute path elsewhere, or one
  which escapes the directory via `..`, is refused.  The image is
  served via the `/v1/rooms/{room_id}/bg_image` endpoint, which returns
  404 for a refused path.  E.g.:

  ```yaml
  logo_image: "./logo.png"
  ```

- `_order` (a string, default unset) overrides the sort key used when
  listing rooms.  When unset, rooms are sorted by their `id`.  This is
  an advanced escape hatch -- note the leading underscore in the YAML
  key, which is deliberate to mark it as an internal override rather
  than a normal user-facing option.  E.g., to make a room appear first
  in a list regardless of its `id`:

  ```yaml
  _order: "000-welcome"
  ```

### Agent configuration

The `agent` mapping is used to configure the Pydantic AI agent used to
make the room's calls to the LLM.

```yaml
agent:
    model_name: "gpt-oss:latest"
    system_prompt: "./prompt.txt"
```

Please see [this page](agents.md) for a full description of the options
for configuring an agent.

### Tool Configurations

- `tools` should be a list of mappings, with at least the key
  `tool_name`, whose value is a dotted name identifying a Python function
   (or callable) which can serve as a "tool" for the LLM.  E.g.:

   ```yaml
   tools:
       - tool_name: "soliplex.tools.get_current_datetime"
       - tool_name: "soliplex.tools.get_current_user"
   ```

  Each tool mapping can contain additional elements, which are used to
  configure the tool's behavior.

### MCP Client Toolsets

- `mcp_client_toolsets` should be a mapping of toolset name to a toolset
  configuration.  Each configuration selects a transport via its `kind`:

  - `"stdio"` runs an MCP server as a subprocess, configured with
    `command`, `args`, and `env`.

  - `"http"` or `"sse"` connect to a remote MCP server, configured with
    `url`, `headers`, and `query_params`.

  Any configuration may also set `allowed_tools` (a list of strings) to
  restrict which of the server's tools are exposed.  E.g.:

  ```yaml
  mcp_client_toolsets:
    google_maps:
      kind: "stdio"
      command: "npx"
      args:
        - "-y"
        - "@modelcontextprotocol/server-google-maps"
      env:
        GOOGLE_MAPS_API_KEY: "secret:GOOGLE_MAPS_API_KEY"
  ```

  String values in these fields can interpolate installation secrets and
  environment variables; see [Installation Secret / Environment
  Interpolation](installation.md#installation-secret-environment-interpolation).

### Skill Configuration

- `installation_skill_names` (a list, default empty);  if set, names the
  installation skills which are enabled for the room.  Each entry is a
  skill name, or a mapping of `name` and `defer_loading`.

- `skill_configs` (a list of mappings, default empty); if set, configure
  native capabilities locally for the room.

E.g.:

  ```yaml
  skills:
    installation_skill_names:
        - "bare-bones"           # a filesystem skill

        - name: "stanzas"        # loaded up front, not on demand
          defer_loading: false

    skill_configs:

        - kind: "haiku.rag.skills.rag"
          rag_lancedb_stem: "rag"
  ```

#### Deferred Loading

A deferred skill's tools and instructions stay hidden until the model asks
for them through its `load_capability` tool, which is offered a catalogue
of every deferred capability's id and description.  That id is the
capability's own and need not match the skill name which configured it:
the `haiku.rag.skills.rag` skill is named `rag`, and its capability's id
is `haiku-rag`.  An undeferred skill's tools and instructions are in front
of the model from the first request.

Each entry sets `defer_loading` to choose between the two.  The default
differs by kind:

| Kind | Default |
| --- | --- |
| `haiku.rag.skills.rag` | `false` |
| `bwrap_sandbox` | `false` |
| `entrypoint` | `true` |
| filesystem skills, named in `installation_skill_names` | `true` |

Defer a skill to keep its instructions out of a room whose agent rarely
needs them;  the cost is a model request spent loading it when it does.
Rooms configuring several instruction-heavy skills are what deferral is
for.

The evidence kinds below take no `defer_loading`:  they contribute no
tools or instructions, so there is nothing to load, and a deferred
capability's hooks do not fire until it is loaded.

#### Evidence Skill Configuration Kinds

Two further kinds take no configuration:  naming one is the whole switch.

- `haiku.rag.skills.evidence_compaction`:  on each request, replaces
  earlier questions' evidence with a capsule of the evidence that was
  cited, re-attaching cited page images;  every other earlier evidence
  return becomes a short receipt.  Requests only -- stored history is
  untouched.

- `haiku.rag.skills.citation_policy`:  requires every answer to register
  the evidence that grounds it, or to declare that nothing does.  An
  answer which ends a question without declaring is redirected once to
  cite, at the cost of an extra model request.  Publishes a
  `citation_policy` state namespace, recording as a violation any question
  which could not be asked to cite.

Their effects are not symmetric.  **Compaction without the citation policy
loses evidence:**  the capsule is built only from what was cited, so for
any earlier question the model did not cite for, that question's evidence
is replaced by receipts and nothing takes its place -- worse than not
compacting.  Configure the citation policy alongside compaction, or
configure neither.  The citation policy without compaction is safe:
citations are required and recorded, and no history is rewritten.

A room which configures neither resends every earlier turn's full search
results on every request.

#### Default Skill Configuration Kinds

Soliplex provides one such skill configuration class by default, of kind
`haiku.rag.skills.rag`.  It has options for configuring the RAG database
and RAG client:

- At most one of the following.  A configuration providing none of them
  reads the databases its `haiku.rag.yaml` places in `lancedb.databases`,
  which is how a room reads a database that is not a local directory.

  - `rag_lancedb_stem`: a string, the "base name" (without path or
    `.lancedb` suffix) of the LanceDB file containing the RAG document
    data.  This file must exist in the standard location (typically
    under the `db/rag/` directory; see [rooms](rooms.md) for details).

  - `rag_lancedb_override_path`: a string, a pathname, including the
    suffix, of the LanceDB directory.

  - `rag_databases`: a list of mappings, to search several databases at
    once.  Each entry carries exactly one of `rag_lancedb_stem` or
    `rag_lancedb_override_path`, resolved the same way as above, plus an
    optional `name`.  An entry naming none is named for whichever option
    placed it, so `rag_lancedb_stem: "papers"` and
    `rag_lancedb_override_path: "../wiki.lancedb"` are `papers` and
    `wiki`.  Names must be unique within the list.

    ```yaml
    skills:
      skill_configs:
        - kind: "haiku.rag.skills.rag"
          rag_databases:
            - name: "papers"
              rag_lancedb_stem: "papers"
            - name: "wiki"
              rag_lancedb_override_path: "../wiki.lancedb"
    ```

    The name is how a database identifies itself outside the
    configuration: it is what the agent sees as the collection a result
    came from, what the room's search, document and chunk endpoints
    return as `database`, and what audit records name.  The location
    stays in the configuration.

    `rag_lancedb_stem` and `rag_lancedb_override_path` written directly
    on the skill or tool are shorthand for a one-entry `rag_databases`,
    kept for configurations written before the list existed.  They are
    read into that list as the config loads, so a config written either
    way behaves the same from there on, and is exported as the list.

    All the databases in a list must have been written with the same
    embedding model, since one query is embedded once for all of them.

  Naming a database here while the `haiku.rag` configuration read by the
  room already places one in `lancedb.databases` is two placements for
  one room, and the room fails when it is used.  The configuration may
  be the room's own `haiku.rag.yaml` or the installation's, since the
  room reads the two merged.  Name every database in one place: move the
  room's own into `lancedb.databases`, or drop whichever side is the
  duplicate.  A configuration carrying the older `lancedb.uri` fails to
  load instead, with the replacement spelled out.  `soliplex-cli audit`
  reports either ahead of time.

- `haiku_rag_config`: a path to the `haiku.rag.yaml` file used to configure
  the RAG client.  If not absolute, this path is resolved relative to
  the directory containing the room configuration file.  If passed,
  values from this file are overlaid on the the installation configuration's
  `haiku_rag_config`.

Skill configurations with the `kind` of `"haiku.rag.skills.rag"` give the
agent three tools:

- `search` — semantic search over the configured databases, returning
  ranked chunks with the ids a citation quotes.  Picture chunks arrive as
  images when the room's agent declares `multimodal: true`.

- `execute_code` — Python over the corpus, in an interpreter with
  `search` and `list_documents` available inside it and every document
  mounted read-only under `/documents/`.  Suited to counts, aggregation
  and structural reading a search cannot express.  Variables persist
  between calls, and the code has no network.

- `cite` — register the chunk ids grounding the answer, or an empty list
  where none do.

The per-question budgets and the sandbox's limits come from the room's
`haiku.rag` configuration: `qa.max_searches`, `qa.max_executions`,
`sandbox.code_timeout` and `sandbox.max_output_chars`.

### AG-UI SSE Delivery

- `sse_delivery_config_name` (a string, optional); names one of the
  installation's `sse_delivery` profiles (see
  [Installation Configuration](installation.md#ag-ui-sse-delivery)) as
  the default delivery profile for this room's threads. If unset, the
  room uses the installation's `default` profile; with no installation
  stanza at all, runs use `strategy: "message"`. The name is validated
  when the configuration loads: naming a profile the installation does
  not declare is an error.

E.g., to keep whole-message delivery in one room of an installation
whose default profile delivers bounded deltas:

  ```yaml
  sse_delivery_config_name: "whole-message"
  ```

### Quotas

- `quotas` (a mapping, optional) limits what the room may consume. Its
  one key, for now, is:

  - `room_uploads_bytes` (a non-negative integer, optional): the most
    bytes the room's uploaded files may occupy, in its directory under
    the installation's
    [`rooms_upload_path`](installation.md#upload-paths). Unset (or
    `quotas` absent, `null`, or `{}`) means no limit; `0` refuses every
    new upload.

  ```yaml
  quotas:
    room_uploads_bytes: 500000000
  ```

  The value may instead be a single `env:NAME` marker, resolved from the
  installation environment, so that each deployment can set its own
  quota without editing the room. Declare the name in the installation's
  `environment` section (see [Environment](environment.md)), and supply
  its value there, in `.env`, or in the OS environment:

  ```yaml
  # installation.yaml
  environment:
    - "RESEARCH_ROOM_UPLOAD_QUOTA"
  ```

  ```yaml
  # rooms/research/room_config.yaml
  quotas:
    room_uploads_bytes: "env:RESEARCH_ROOM_UPLOAD_QUOTA"
  ```

  Unlike the [Logfire fields](installation.md#fields-which-interpolate-only-environment-variables),
  a name with no value is an error, not "no limit": a typo must never
  lift the quota silently. The resolved value must be plain digits
  (`500000000`, not `500MB`), and only a whole `env:` marker is accepted
  (no `secret:` marker, nor one embedded in other text).

  An invalid quota fails when the configuration loads: an unknown key
  (`Invalid 'quotas' in ...: unknown key(s): ['room_uploads_byte']`), or a
  value which is negative, not an integer, or not a whole `env:` marker.
  An `env:` value which will not resolve stops the server at startup,
  and makes a room-config reload fail, naming the room's config file;
  `soliplex-cli audit rooms` reports it too.

What counts against `room_uploads_bytes`:

- The regular files in the room's uploads directory.
- **Uploads in progress**, at their full size from the moment they
  start. Each upload is written through a hidden
  `.soliplex-upload-<id>` reservation file, then renamed into place.
  Reservations, and any `.nfs*` files the NFS client leaves behind, are
  never listed, downloaded, or shown to the room's agent, but they occupy
  storage, so they count.
- **Not** symlinks an operator places in the room to share a file: they
  store none of its bytes. Linked files are listed, but not counted.

So the uploads listing's `total_size_bytes` can differ from the sum of
the listed files' sizes, either way.

At the limit:

- An upload which would take the room past its quota is refused with
  `507 Insufficient Storage`, and nothing is written. Replacing an
  existing file counts only the difference in size.
- Lowering a quota below the room's current usage keeps the existing
  files, but refuses new uploads until enough are deleted. Deleting is
  always allowed.
- Uploads to a room are checked one at a time, in a step which normally
  takes milliseconds. If that step cannot start within 30 seconds (the
  storage is stalled), the upload is refused with `503`, and a
  `Retry-After` header.

**Note:** the quota is exact only when **one active soliplex server
process** writes to the uploads tree. With `serve --workers N` (N > 1),
or several replicas or containers sharing the same `rooms_upload_path`
(for example on EFS), it is a *soft* limit, and usage can go slightly
over it:

- uploads starting at the same moment in different processes can each
  pass the check;
- on a network filesystem, another server may see a new upload's
  reservation only after a short delay;
- two uploads replacing the same filename at once are each credited with
  the file they replace.

`soliplex-cli audit rooms` prints a `NOTE:` for each room over its quota.
The note does not fail the audit, so that an audit used to gate, say,
adding a room never fails because of another room's usage; run it on a
schedule, *without* `--quiet`, to watch for overages (see
[`audit rooms`](../server/cli.md#audit-rooms)). Each room's quota and
usage are also in the API's uploads listing, `GET /v1/uploads/{room_id}`
(`quota_bytes`, `total_size_bytes`, and `available_bytes`).

### Quiz-related elements

- `quizzes` is a list of mappings (default `()`):  each mapping defines a
  quiz which can be run in the room (see [this page](quizzes.md) for
  details of the quiz dataset).

  ```yaml
  quizzes:
    - id: "test_quiz"
      title: "Test Quiz"
      question_file: "/path/to/questions.json"
      randomize: false
      max_questions: 100
  ```

## Location of RAG database files

Rooms need to be able to find the LanceDB database containing the chunks
and embeddings extracted by Haiku-RAG.  A database is named by convention
`<stem>.lancedb`, and stored in the `db/rag/` subdirectory of the project
root.

A room's RAG skill or tool reads one such database, or several named ones
through `rag_databases` (see above), in which case a search covers them
all and each result reports the database it came from.
