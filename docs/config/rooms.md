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
  the UI can display as the room's logo.  Relative paths are resolved
  against the room's configuration directory.  The image is served via
  the `/v1/rooms/{room_id}/image` endpoint.  E.g.:

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

        - kind: "haiku.rag.skills.analysis"
          rag_lancedb_stem: "notes"
  ```

  Configure at most one of these two kinds per corpus.  Analysis searches
  and cites as well as running code, so pairing it with the RAG skill over
  the same database gives the agent two near-identical search tools, splits
  its citations across the two records, and gives one question two search
  budgets to spend.  Two kinds over *different* databases is fine, as
  above.

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
| `haiku.rag.skills.analysis` | `false` |
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

Soliplex provides two such skill configuration classes by default:
one of kind `haiku.rag.skills.rag` and one of kind
`haiku.rag.skills.analysis`.  Both of these configurations have options for
configuring the RAG database and RAG client:

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
    once.  Each entry carries a `name`, plus exactly one of
    `rag_lancedb_stem` or `rag_lancedb_override_path`, resolved the same
    way as above.  Names must be unique within the list.

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
agent the following RAG tools:

- `"search"` — semantic document search with multi-query expansion.
  Gives the agent a `search` tool that returns ranked passages with
  citations.

- `"list_documents"` — list the documents in the RAG database.

- `"get_document"` — return the content of a single document in the
  RAG database.

- `"ask"` — question-answering via a research graph.  Gives the agent
  an `ask` tool that searches, synthesizes an answer with citations,
  and caches results for similar follow-up questions.

- `"research"` — deep research via a research graph. Gives the agent
  a `research` tool that performs a more elaborate search, analysis,
  and synthesis. Slower than the `ask` tool, and more expensive in
  terms of token budget, but potentially produces a higher-quality
  result.

The `haiku.rag.skills.analysis` skill gives the agent an `analyze` tool that
iteratively writes and executes Python code in a Docker sandbox with
access to `haiku.rag` functions (`search`, `list_documents`, `get_document`,
`llm`, etc.).  Suited for aggregation, multi-document comparison, and
structured data extraction.  Requires Docker.  This skill does not offer
any additional options.

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
