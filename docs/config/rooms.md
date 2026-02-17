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
  tells the UI to allow the user to attach files to a prompt. E.g.:

  ```yaml
  enable_attachments: true
  ```

- `agui_feature_names` (list of strings); if set these values are added
  to the feature names defined on the individual tools to create an
  aggregate set for the room.


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

#### The `haiku_chat` agent kind

Rooms can use the `haiku_chat` agent kind to provide conversational RAG
powered by `haiku.rag`.  This agent kind uses its own configuration
instead of the standard `tools` list.

- `rag_lancedb_stem` is a string:  it should be the "base name" (without
  path or `.lancedb` suffix) of the LanceDB file containing the RAG document
  data.  This file must exist in the "standard" location (typically under
  the `db/rag/` directory;  see below).

- `rag_lancedb_override_path` is a string:  as an alternative to
  `rag_lancedb_stem`, it should be a fully-qualified pathname, including
  the suffix, of the LanceDB directory.

- `rag_features` (a list of strings) controls which haiku.rag toolsets
  are enabled.  Available features: `"search"`, `"documents"`, `"qa"`,
  `"analysis"`.

- `preamble` (a string, optional) overrides the agent's default system
  prompt section defining its identity and behavioral rules.

- `background_context` (a string, optional) seeds the conversation with
  domain knowledge, injected as the session's initial context.

Example:

```yaml
agent:
  kind: "haiku_chat"
  rag_lancedb_stem: "rag"
  rag_features: ["search", "documents", "qa"]
  preamble: |
    You are a knowledgeable assistant that answers questions
    using a document knowledge base.
  background_context: |
    This knowledge base contains internal documentation
    about the Soliplex platform.
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

Rooms using the `haiku_chat` agent kind need to be able to find the
LanceDB database containing the chunks and embeddings extracted by
Haiku-RAG.  At present, there should be a single database per room,
named by convention `<stem>.lancedb`, and stored in the `db/rag/`
subdirectory of the project root.
