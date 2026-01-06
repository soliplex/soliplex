# Your First Chat

Now that Soliplex is running, let's explore the chat interface and send your first message.

## Connecting to the Server

### 1. Open the Flutter App

Navigate to http://localhost:59001 in your browser.

### 2. Enter Server URL

When prompted, enter the backend URL:

```
http://localhost:8000
```

!!! note "Port Numbers"
    - **59001** - Flutter web app (what you're viewing)
    - **8000** - Backend API (what you connect to)

### 3. Authentication

In development mode (`--no-auth-mode`), you'll be logged in automatically. In production, you'll see OIDC provider options.

## The Chat Interface

### Layout Overview

```
┌──────────────────────────────────────────────────────────────┐
│ ☰ │  Thread History  │      Chat Area        │  Context     │
│   │  ─────────────── │                       │  ──────────  │
│   │  + [New thread]  │  ┌─────────────────┐  │  State       │
│   │  Current Session │  │ AI Response     │  │  Events      │
│   │  Thread 1        │  │ ...             │  │  ...         │
│   │  Thread 2        │  └─────────────────┘  │              │
│   │                  │                       │              │
│   │                  │  ┌─────────────────┐  │              │
│   │                  │  │ Type message... │  │              │
│   │                  │  └─────────────────┘  │              │
└──────────────────────────────────────────────────────────────┘
       ↑                         ↑                    ↑
  Navigation drawer         Main chat         Debug/context
  (☰ opens room list)
```

### Key Elements

| Element | Purpose |
|---------|---------|
| **Navigation (☰)** | Open drawer to select server and room |
| **Thread History** | Access previous conversations, create new threads |
| **Chat Area** | View message history and responses |
| **Context Pane** | View AG-UI state and tool events (development) |
| **Input Box** | Type and send messages |

## Sending Your First Message

### 1. Select a Room

Open the navigation drawer (☰) and click on a room name. Each room has different:

- **AI Model** - Which LLM responds
- **Tools** - What actions it can perform
- **System Prompt** - How it behaves

### 2. Type a Message

Click in the input box at the bottom and type your question:

```
Hello! What can you help me with?
```

### 3. Send

Press **Enter** or click the Send button.

### 4. Wait for Response

The AI will respond with streaming text. You'll see the response appear incrementally.

## Understanding Responses

### Text Responses

Most responses are plain text or markdown:

```
I can help you with:
- Answering questions
- Searching documents (if RAG is enabled)
- Performing various tasks using tools
```

### Code Blocks

Code is rendered with syntax highlighting:

```python
def hello():
    print("Hello, World!")
```

### Tool Calls

When the AI uses a tool, you'll see a compact indicator that can be expanded:

```
Using search_documents... ✓
```

Click to expand and see tool details. Multiple tool calls are grouped together.

### Citations

If using RAG tools, citations appear in a collapsible section below the response:

```
▶ 3 sources
```

Click to expand and see source documents, page numbers, and content previews. Click page badges to view the original document with highlighted text.

## Working with Threads

### Starting a New Thread

Click the + button (with "New thread" tooltip) in the thread list header to start a fresh conversation.

### Continuing a Thread

Select an existing thread from the list to continue that conversation. The AI remembers the context.

### Thread Persistence

Threads are saved to the configured database. With file-based SQLite (e.g., `sqlite:///threads.db`), you can close the browser and return later. The default `minimal.yaml` uses in-memory SQLite, so threads won't persist across server restarts.

## Exploring Rooms

### Default Rooms

| Room | Purpose |
|------|---------|
| **haiku** | Search documents using Haiku-RAG |
| **joker** | Joke generator (testing agent delegation) |
| **research** | Generate research reports using Haiku-RAG |

### Room Capabilities

Each room may have different tools available:

- `get_current_datetime` - Get current date/time
- `get_current_user` - Get current user profile
- `search_documents` - RAG vector search
- `research_report` - Multi-document analysis with synthesis

## Tips for Better Results

!!! tip "Be Specific"
    "Explain how agents are configured in Soliplex" gets better results than "tell me about agents"

!!! tip "Use Context"
    Reference earlier parts of the conversation: "Going back to what you said about tools..."

!!! tip "Check Sources"
    When citations appear, click to verify the source material

## Next Steps

- [User Guide](../user-guide/index.md) - Learn more features
- [Room Configuration](../admin-guide/configuration/rooms.md) - Customize rooms
- [RAG Setup](../developer-guide/rag/database.md) - Add document search
