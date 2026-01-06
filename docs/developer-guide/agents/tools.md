# Tools

Tools extend agent capabilities by allowing them to execute functions. This document covers built-in tools and creating custom tools.

## Built-in Tools

### get_current_datetime

Returns the current date and time in ISO format.

```python
async def get_current_datetime() -> str:
    """Get the current date and time in ISO format."""
    return datetime.datetime.now(datetime.UTC).isoformat()
```

**Configuration:**
```yaml
tools:
  - tool_name: "soliplex.tools.get_current_datetime"
    allow_mcp: true
```

**Requirements:** None (bare function)

---

### get_current_user

Returns information about the authenticated user.

```python
async def get_current_user(
    ctx: pydantic_ai.RunContext[agents.AgentDependencies],
) -> models.UserProfile:
    """Return information from the current user's profile."""
    return ctx.deps.user
```

**Configuration:**
```yaml
tools:
  - tool_name: "soliplex.tools.get_current_user"
```

**Requirements:** `FASTAPI_CONTEXT` - needs RunContext

**Note:** This tool requires FastAPI context and cannot be exposed via MCP.

---

### search_documents

Searches the RAG database for relevant documents.

```python
async def search_documents(
    query: str,
    tool_config: config.SearchDocumentsToolConfig = None,
) -> list[rag_store_models_chunk.SearchResult]:
    """Search the document knowledge base for relevant information."""
```

**Configuration:**
```yaml
tools:
  - tool_name: "soliplex.tools.search_documents"
    rag_lancedb_stem: "rag"
    search_documents_limit: 10
    allow_mcp: true
```

**Requirements:** `TOOL_CONFIG` - needs SearchDocumentsToolConfig

---

### research_report

Performs deep research using a graph-based workflow.

```python
async def research_report(
    ctx: pydantic_ai.RunContext[agents.AgentDependencies],
    question: str,
) -> rag_research.ResearchReport:
    """Perform research against document knowledge base."""
```

**Configuration:**
```yaml
tools:
  - tool_name: "soliplex.tools.research_report"
    rag_lancedb_stem: "rag"
    allow_mcp: true
```

**Requirements:** `FASTAPI_CONTEXT` - needs RunContext

---

### ask_with_rich_citations

Answers questions with inline citations from documents. This tool integrates with AG-UI state management to track document filtering and citation history.

```python
async def ask_with_rich_citations(
    ctx: pydantic_ai.RunContext[agents.AgentDependencies],
    question: str,
) -> str:
    """Answer questions using document knowledge base with citations."""
```

**Configuration:**
```yaml
tools:
  - tool_name: "soliplex.tools.ask_with_rich_citations"
    rag_lancedb_stem: "rag"
```

**Requirements:** `FASTAPI_CONTEXT` - needs RunContext with AGUI state

**State Management:**

This tool uses AG-UI state features to:

1. **Read `filter_documents`** - If the client sends document IDs to filter, the tool restricts its search to those documents only
2. **Update `ask_history`** - After answering, the tool emits a `STATE_DELTA` event with the question, response, and citations

```python
# Internal state model used by the tool
class AWRC_AGUI_State(pydantic.BaseModel):
    filter_documents: FilterDocuments | None = None  # Client-provided filter
    ask_history: AskedAndAnswered | None = None      # Updated by tool
```

The state flow:
1. Client sends `filter_documents` in `RunAgentInput.state`
2. Tool reads filter from `ctx.deps.state`
3. Tool performs filtered search and generates response
4. Tool emits `STATE_DELTA` with updated `ask_history`
5. Client receives delta and updates local state

---

### agui_state

Returns the current AG-UI client state.

```python
async def agui_state(
    ctx: pydantic_ai.RunContext[agents.AgentDependencies],
) -> agui.AGUI_State:
    """Return the AGUI state."""
    return ctx.deps.state
```

**Configuration:**
```yaml
tools:
  - tool_name: "soliplex.tools.agui_state"
```

**Requirements:** `FASTAPI_CONTEXT` - needs RunContext

---

## Tool Configuration Classes

### Base ToolConfig

```python
@dataclasses.dataclass
class ToolConfig:
    tool_name: str       # Python import path
    allow_mcp: bool = False  # Expose via MCP
```

### NoToolConfig Exception

Tools that require configuration raise `NoToolConfig` when called without it:

```python
class NoToolConfig(ValueError):
    """Raised when a tool is called without required configuration."""
    pass
```

This typically occurs when:
- A tool requiring `TOOL_CONFIG` is called without configuration
- The tool config lookup fails in `ctx.deps.tool_configs`

### Tool Config Lookup Pattern

Some tools look up their configuration from `ctx.deps.tool_configs` rather than receiving it as a parameter:

```python
async def research_report(ctx: RunContext[AgentDependencies], question: str):
    # Look up config by tool name (matches the 'kind' field)
    tool_config = ctx.deps.tool_configs.get("research_report")
    if tool_config is None:
        raise NoToolConfig()
    # Use tool_config...
```

This pattern is used by:
- `research_report`
- `ask_with_rich_citations`

**How it works:**

1. Tool configs are defined in the room's `tools` YAML section
2. During agent creation, configs are parsed into typed `ToolConfig` subclasses
3. The configs are stored in a dict keyed by their `kind` field
4. This dict is passed to the agent as `AgentDependencies.tool_configs`
5. Tools access their config via `ctx.deps.tool_configs.get("kind_name")`

### _RAGToolBase

RAG tools inherit from `_RAGToolBase` which provides database path resolution and haiku-rag configuration:

```python
@dataclasses.dataclass
class _RAGToolBase:
    rag_lancedb_stem: str = None           # Database name in RAG_LANCE_DB_PATH
    rag_lancedb_override_path: str = None  # Explicit database path

    @property
    def haiku_rag_config(self) -> HaikuRagConfig:
        """Resolved at runtime from installation + room config."""
        # Merges installation-level haiku.rag.yaml with room-level overrides
        return self._installation_config.get_haiku_rag_config(
            room_config_path=self._config_path
        )
```

**Path Resolution:**

- `rag_lancedb_stem: "knowledge"` → `{RAG_LANCE_DB_PATH}/knowledge.lancedb`
- `rag_lancedb_override_path: "./custom.lancedb"` → Resolved relative to config file

The `haiku_rag_config` property automatically merges the installation's base `haiku.rag.yaml` with any room-level overrides.

### SearchDocumentsToolConfig

```python
@dataclasses.dataclass
class SearchDocumentsToolConfig(ToolConfig, _RAGToolBase):
    kind: str = "search_documents"
    tool_name: str = "soliplex.tools.search_documents"
    search_documents_limit: int = 5  # Default: 5
```

### AG-UI Feature Registration

Tools can register AG-UI state features using `agui_feature_names`. This declares which state sections the tool reads from or writes to:

```python
@dataclasses.dataclass
class AskWithRichCitationsToolConfig(ToolConfig, _RAGToolBase):
    kind: str = "ask_with_rich_citations"
    tool_name: str = "soliplex.tools.ask_with_rich_citations"
    agui_feature_names: tuple[str, ...] = ("filter_documents", "ask_history")
```

When a tool declares features:
1. The system registers the feature schemas with AG-UI
2. The client can send/receive state for those features
3. The tool can emit `STATE_DELTA` events to update feature state

**Built-in features:**

| Feature | Description | Source |
|---------|-------------|--------|
| `filter_documents` | Document IDs to filter search results | CLIENT |
| `ask_history` | Question/answer history with citations | SERVER |

### Custom Tool Config Pattern

When creating custom tool configs that need extra initialization, override `get_extra_parameters()`:

```python
@dataclasses.dataclass
class CustomToolConfig(ToolConfig):
    api_key_secret: str = None
    custom_option: str = "default"

    def get_extra_parameters(self) -> dict[str, typing.Any]:
        """Return extra parameters to inject into the tool function."""
        return {
            "api_key": self._installation_config.get_secret(self.api_key_secret),
            "option": self.custom_option,
        }
```

The returned dict is merged with tool function kwargs when the tool is called.

## Creating Custom Tools

### Simple Tool

```python
# mypackage/tools.py

async def calculate_tip(
    bill_amount: float,
    tip_percentage: float = 18.0,
) -> float:
    """Calculate tip amount for a bill."""
    return bill_amount * (tip_percentage / 100)
```

**Configuration:**
```yaml
tools:
  - tool_name: "mypackage.tools.calculate_tip"
```

### Tool with Context

Access agent dependencies via RunContext:

```python
from pydantic_ai import RunContext
from soliplex import agents

async def personalized_greeting(
    ctx: RunContext[agents.AgentDependencies],
) -> str:
    """Get a personalized greeting for the user."""
    user = ctx.deps.user
    return f"Hello, {user.given_name}!"
```

### Tool with Configuration

Create a custom tool config class:

```python
import dataclasses
from soliplex import config

@dataclasses.dataclass
class WeatherToolConfig(config.ToolConfig):
    api_key_secret: str = None
    units: str = "metric"

async def get_weather(
    city: str,
    tool_config: WeatherToolConfig = None,
) -> dict:
    """Get current weather for a city."""
    api_key = tool_config._installation_config.get_secret(
        tool_config.api_key_secret
    )
    # Make API call...
    return {"city": city, "temp": 22, "units": tool_config.units}
```

**Configuration:**
```yaml
tools:
  - tool_name: "mypackage.tools.get_weather"
    api_key_secret: "secret:WEATHER_API_KEY"
    units: "imperial"
```

## Tool Requirements

Tools are classified by their requirements:

| Requirement | Description | MCP Compatible |
|-------------|-------------|----------------|
| `BARE` | No parameters needed | Yes |
| `TOOL_CONFIG` | Needs ToolConfig | Yes |
| `FASTAPI_CONTEXT` | Needs RunContext | No |

## Room Tool Configuration

### Basic Configuration

```yaml
# rooms/myroom/room_config.yaml
tools:
  - tool_name: "soliplex.tools.get_current_datetime"
  - tool_name: "soliplex.tools.search_documents"
    rag_lancedb_stem: "rag"
    search_documents_limit: 10
```

### MCP Exposure

```yaml
tools:
  - tool_name: "soliplex.tools.search_documents"
    rag_lancedb_stem: "rag"
    allow_mcp: true  # Expose via MCP server
```

## Best Practices

1. **Keep tools focused** - One tool, one purpose
2. **Handle errors gracefully** - Return error messages, don't raise
3. **Document parameters** - Use clear docstrings
4. **Consider MCP** - Use `allow_mcp: true` for shareable tools
5. **Test thoroughly** - Tools are called by LLMs, edge cases matter

## Source Code

- Tool implementations: `src/soliplex/tools.py`
- Tool configuration: `src/soliplex/config.py`
