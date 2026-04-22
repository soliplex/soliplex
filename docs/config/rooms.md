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

- `enable_attachments` (a boolean, default `False`), which, if true,
  tells the UI to allow the user to attach files to a prompt. E.g.:

  ```yaml
  enable_attachments: true
  ```

- `agui_feature_names` (list of strings); if set these values are added
  to the feature names defined on the room's agent, tools, and skills
  to create an aggregate set for the room.

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

### Skill Configuration

- `installation_skill_names` (a list of strings, default empty);  if set,
  names the installation skills which are enabled for the room.

- `skill_configs` (a list of mappings, default empty); if set, configue
  skills locally to the room.

E.g.:

  ```yaml
  skills:
    installation_skill_names:
        - "bare-bones"           # a filesytem skill
        - "image-generation"     # an entrypoint skill

    skill_configs:

        - skill_name: "rag"
          kind: "haiku.rag.skill.rag"
          rag_lancedb_stem: "rag"
          tool_names:
            - "search"
            - "ask"
            - "get_document"
            - "list_documents"
            - "research"

        - skill_name: "rlm"
          kind: "haiku.rag.skill.rag"
          rag_lancedb_stem: "rag"
  ```

#### Default Skill Configuration Kinds

Soliplex provides two such skill configuration classes by default:
one of kind `haiku.rag.skill.rag` and one of kind
`haiku.rag.skill.rlm`.  Both of these configurations have options for
configuring the RAG database and RAG client:

- One of the following (exactly one must be provided):

  - `rag_lancedb_stem`: a string, the "base name" (without path or
    `.lancedb` suffix) of the LanceDB file containing the RAG document
    data.  This file must exist in the standard location (typically
    under the `db/rag/` directory; see [rooms](rooms.md) for details).

  - `rag_lancedb_override_path`: a string, a fully-qualified pathname,
    including the suffix, of the LanceDB directory.

- `haiku_rag_config`: a path to the `haiku.rag.yaml` file used to configure
  the RAG client.  If not absolute, this path is resolved relative to
  the directory containing the room configuration file.  If passed,
  values from this file are overlaid on the the installation configuration's
  `haiku_rag_config`.

Skill configurations with the `kind` of `"haiku.rag.skill.rag"` have these
additional options:

- `tool_names` (a list of strings, from among this list:  `"search"`,
  `"ask"`, `"list_documents"`, `"get_document"`, and `"research"`.
  Defaults to `["search", "ask", "list_documents", "get_document"]`.

  Available tools:

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

- `rag_features` (a list of strings) controls which haiku.rag toolsets
  are enabled.  A deprecated alternative to `tool_names`:  each "features"
  maps to one or more of the tools enumerated above.

  Available features:

  - `"search"` — equivalent to the `search` tool above.

  - `"documents"` — equivalent to the `list_documents` and `get_document`
    tools above.

  - `"qa"` — equivalent to the `ask` tool above.

  - `"analysis"` — formerly equivalent to the `haiku.rag.skills.rml`
    skill below.  This feature is no longer supported.

The `haiku.rag.skills.rlm` skill gives the agent an `analyze` tool that
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

Rooms using the `haiku_chat` agent kind need to be able to find the
LanceDB database containing the chunks and embeddings extracted by
Haiku-RAG.  At present, there should be a single database per room,
named by convention `<stem>.lancedb`, and stored in the `db/rag/`
subdirectory of the project root.
