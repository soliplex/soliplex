# Room Configuration

Rooms are chat environments with specific agents, tools, and configurations.

## Directory Structure

```
rooms/
└── research/
    ├── room_config.yaml    # Room configuration
    ├── prompt.txt          # System prompt (optional)
    └── haiku.rag.yaml      # RAG config override (optional)
```

Directories starting with `.` are ignored.

A room can include `haiku.rag.yaml` to override the installation's RAG configuration. See [RAG](rag.md).

## Quick Start

```yaml
# rooms/research/room_config.yaml
id: "research"
name: "Research Assistant"
description: "AI-powered document research"

agent:
  model_name: "gpt-oss:latest"
  system_prompt: "./prompt.txt"
```

## Configuration Reference

### id (required)

Unique room identifier. Should match the directory name.

```yaml
id: "research"
```

### name (required)

Display name for the room:

```yaml
name: "Research Assistant"
```

### description (required)

Brief description shown in room listings:

```yaml
description: "Search and analyze documents with AI"
```

### agent (required)

Agent configuration. See [Agents](agents.md).

```yaml
agent:
  model_name: "gpt-oss:latest"
  system_prompt: "You are a research assistant."
```

Or reference a global agent:

```yaml
agent:
  template_id: "research_agent"
```

### tools

List of tools available to the agent:

```yaml
tools:
  - tool_name: "soliplex.tools.get_current_datetime"

  - tool_name: "soliplex.tools.search_documents"
    rag_lancedb_stem: "knowledge"
    search_documents_limit: 10
    allow_mcp: true
```

See [Tools](../../developer-guide/agents/tools.md) for details.

### mcp_client_toolsets

External MCP servers to connect. Supports two transport types: stdio and HTTP.

#### Stdio Transport

Run MCP server as a subprocess:

```yaml
mcp_client_toolsets:
  filesystem:
    kind: "stdio"
    command: "npx"
    args: ["-y", "@anthropic-ai/mcp-server-filesystem", "./workspace"]
    env:
      API_KEY: "secret:MCP_API_KEY"
    allowed_tools:
      - "read_file"
      - "list_directory"
```

| Field | Description |
|-------|-------------|
| `kind` | `"stdio"` for subprocess transport |
| `command` | Executable to run |
| `args` | Command arguments |
| `env` | Environment variables (supports `secret:` interpolation) |
| `allowed_tools` | Whitelist of tools to expose (optional, all if omitted) |

#### HTTP Transport

Connect to remote MCP server over HTTP:

```yaml
mcp_client_toolsets:
  remote:
    kind: "http"
    url: "https://mcp.example.com/v1"
    headers:
      Authorization: "Bearer secret:MCP_TOKEN"
    query_params:
      api_key: "secret:MCP_API_KEY"
    allowed_tools:
      - "search"
```

| Field | Description |
|-------|-------------|
| `kind` | `"http"` for HTTP transport |
| `url` | MCP server URL |
| `headers` | HTTP headers (supports `secret:` interpolation) |
| `query_params` | URL query parameters (supports `secret:` interpolation) |
| `allowed_tools` | Whitelist of tools to expose (optional, all if omitted) |

See [MCP Client](../../developer-guide/mcp/client.md) for details.

### allow_mcp

Enable MCP server for this room. Default: `false`

```yaml
allow_mcp: true
```

### welcome_message

Message displayed when user enters the room:

```yaml
welcome_message: |
  Welcome to the Research Assistant!

  Ask questions about your documents and I'll help you find answers.
```

### suggestions

Starter questions for the UI:

```yaml
suggestions:
  - "What documents do you have?"
  - "Summarize the main topics"
  - "Find information about..."
```

### enable_attachments

Allow file attachments. Default: `false`

```yaml
enable_attachments: true
```

### logo_image

Room logo image file:

```yaml
logo_image: "./logo.png"
```

### _order

Sort order for room listings. Accessed via `sort_key` property. Values are strings with lexicographic sorting.

```yaml
_order: "10"  # String-based sorting (lexicographic)
```

To ensure numeric ordering, use zero-padded strings (e.g., `"01"`, `"02"`, `"10"`).

### quizzes

Quiz configurations for the room:

```yaml
quizzes:
  - id: "intro_quiz"
    title: "Introduction Quiz"
    question_file: "./quizzes/intro.json"
    max_questions: 10
```

See [Quizzes](quizzes.md) for details.

## Tool Configuration

### search_documents

RAG document search:

```yaml
tools:
  - tool_name: "soliplex.tools.search_documents"
    rag_lancedb_stem: "knowledge"       # Database in db/rag/
    search_documents_limit: 10          # Max results
    allow_mcp: true                     # Expose via MCP
```

Or with explicit path:

```yaml
tools:
  - tool_name: "soliplex.tools.search_documents"
    rag_lancedb_override_path: "/data/rag/custom.lancedb"
```

### research_report

Deep research with graph workflow:

```yaml
tools:
  - tool_name: "soliplex.tools.research_report"
    rag_lancedb_stem: "knowledge"
    allow_mcp: true
```

### ask_with_rich_citations

Q&A with inline citations:

```yaml
tools:
  - tool_name: "soliplex.tools.ask_with_rich_citations"
    rag_lancedb_stem: "knowledge"
```

### Built-in Tools

```yaml
tools:
  - tool_name: "soliplex.tools.get_current_datetime"
  - tool_name: "soliplex.tools.get_current_user"
```

## Complete Example

```yaml
# rooms/research/room_config.yaml
id: "research"
name: "Research Assistant"
description: "AI-powered document research with citations"
_order: "01"

agent:
  model_name: "gpt-oss:latest"
  system_prompt: "./prompt.txt"
  model_settings:
    temperature: 0.3

tools:
  - tool_name: "soliplex.tools.get_current_datetime"

  - tool_name: "soliplex.tools.search_documents"
    rag_lancedb_stem: "knowledge"
    search_documents_limit: 10
    allow_mcp: true

  - tool_name: "soliplex.tools.ask_with_rich_citations"
    rag_lancedb_stem: "knowledge"

welcome_message: |
  Welcome to the Research Assistant!

  I can help you search and analyze documents. Try:
  - Asking questions about document content
  - Requesting summaries or comparisons
  - Finding specific information

suggestions:
  - "What topics are covered in the documents?"
  - "Summarize the key findings"
  - "Compare the approaches described"

enable_attachments: false
allow_mcp: true

mcp_client_toolsets:
  filesystem:
    kind: "stdio"
    command: "npx"
    args: ["-y", "@anthropic-ai/mcp-server-filesystem", "./workspace"]
    env:
      WORKSPACE_PATH: "./workspace"
    allowed_tools:
      - "read_file"
      - "list_directory"
```

## Multiple Rooms

Create multiple room directories:

```
rooms/
├── research/
│   ├── room_config.yaml
│   └── prompt.txt
├── chat/
│   └── room_config.yaml
└── code/
    ├── room_config.yaml
    └── prompt.txt
```

Each room can have different agents, tools, and configurations.

## Room Resolution

When multiple `room_paths` are configured, earlier paths take precedence:

```yaml
# installation.yaml
room_paths:
  - "./custom_rooms"   # Wins for conflicts
  - "./default_rooms"
```

## Source Code

- Room configuration: `src/soliplex/config.py`
- Room API: `src/soliplex/views/rooms.py`
