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
) -> list[SearchResult]:
    """Search the document knowledge base."""
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

Answers questions with inline citations from documents.

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

---

## Tool Configuration Classes

### Base ToolConfig

```python
@dataclasses.dataclass
class ToolConfig:
    tool_name: str       # Python import path
    allow_mcp: bool = False  # Expose via MCP
```

### SearchDocumentsToolConfig

```python
@dataclasses.dataclass
class SearchDocumentsToolConfig(ToolConfig):
    rag_lancedb_stem: str = None
    rag_lancedb_override_path: str = None
    search_documents_limit: int = 5
    haiku_rag_config: dict = None
```

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
