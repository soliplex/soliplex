# Room Configuration Filesystem Layout

A foom is configured via directory, whose name is the room ID.

Within that directory should be one or two files:

- `room_config.yaml` holds metadata about the room (see below)

- `prompt.txt` (if present) holds the system prompt for conversations
  which are initiated from the room.


Example layout without extermal prompt file:
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

### Optional room elements (UI-related):

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
  tells the UI to allow the user to attach files to a prompt. E.g.,:

  ```yaml
  enable_attachments: true
  ```


### Agent configuration

The `agent` mapping is used to configure the Pydantic AI agent used to
make the room's calls to the LLM.

```yaml
agent:
    model_name: "qwen3:latest"
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

#### RAG / search-related

The `soliplex.tools.search_documents` tool takes a number of configuration
values.  *Exactly one* of the following two elements is required:

- `rag_lancedb_stem` is a string:  it should be the "base name" (without
  path or `.lancedb` suffix) of the LanceDB file containing the RAG document
  data for the tool. This file must exist in the "standard" location
  (typically under the `db/rag/` directory;  see below).

  ```yaml
  rag_lancedb_stem: "<room_id>"
  ```

- `rag_lancedb_override_path` is a string:  it should be a fully-qualified
  pathname, including the suffix, of the LanceDB directory containing the RAG
  document data for the tool. 

  ```yaml
  rag_lancedb_override_path: "/<path-to-rag-databases>/<room_id>.<extension>"
  ```

Other, optional elements for the `search_documents` tool:

- `search_documents_limit` is a positive integer (default `5`), used to
  control the number of results returned by the `search_documents` tool. E.g.:

  ```yaml
  search_documents_limit: 8
  ```

- `return_citations` is a boolean (default `False`), which toggles whether
   the `search_documents` tool returns document citations.  E.g.:

  ```yaml
  return_citations: true
  ```

- `expand_context_radius` is a positive integer (default `1`), used to
  expand to context returned by the `search_documents` tool E.g.:

  ```yaml
  expand_context_radius: 2
  ```

Minimal `search_documents` configuration, with RAG database file found
in the standard location:

```yaml
agent:
  tools:
    - tool_name: "soliplex.tools.search_documents"
      rag_lancedb_stem: "chat"
```

Minimal `search_documents` configuration, with RAG database file found
in an overridden location:

```yaml
agent:
  tools:
    - tool_name: "soliplex.tools.search_documents"
      rag_lancedb_override_path: "/path/to/rag/db/filename.lancedb"
```

Maximal `search_documents` configuration

```yaml
agent:
  tools:
    - tool_name: "soliplex.tools.search_documents"
      rag_lancedb_stem: "chat"
      search_documents_limit: 8
      return_citations: true
      expand_context_radius: 2
```

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

Rooms using the ``search_documents`` tool need to be able to find the
LanceDB database containing the chunks and embeddings extracted by
Haiku-RAG.  At present, there should be a single database per room,
named by convension `<stem>.lancedb`, and stored in the `db/rag/`
subdirectory of the project root.
