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
┌─────────────────────────────────────────────────┐
│  Room Selector    │     Chat Messages           │
│  ───────────────  │                             │
│  > haiku          │  [Thread History]           │
│    joker          │                             │
│    research       │  ┌─────────────────────┐    │
│                   │  │ AI Response         │    │
│  Thread List      │  │ ...                 │    │
│  ───────────────  │  └─────────────────────┘    │
│    Thread 1       │                             │
│    Thread 2       │  ┌─────────────────────┐    │
│                   │  │ Type a message...   │    │
│                   │  └─────────────────────┘    │
└─────────────────────────────────────────────────┘
```

### Key Elements

| Element | Purpose |
|---------|---------|
| **Room Selector** | Switch between different chat rooms |
| **Thread List** | Access previous conversations |
| **Chat Area** | View message history and responses |
| **Input Box** | Type and send messages |

## Sending Your First Message

### 1. Select a Room

Click on a room name in the sidebar. Each room has different:

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

When the AI uses a tool, you'll see:

```
🔧 Using: search_documents
   Query: "RAG configuration"

📄 Found 3 results...
```

### Citations

If using RAG tools, you may see citations:

> According to the documentation [1], the configuration file...
>
> [1] installation.md, line 42

## Working with Threads

### Starting a New Thread

Click "New Chat" or the + button to start a fresh conversation.

### Continuing a Thread

Select an existing thread from the list to continue that conversation. The AI remembers the context.

### Thread Persistence

Threads are saved automatically. You can close the browser and return later.

## Exploring Rooms

### Default Rooms

| Room | Purpose |
|------|---------|
| **haiku** | General chat with RAG search |
| **joker** | Entertainment - generates jokes |
| **research** | Deep research with reports |

### Room Capabilities

Each room may have different tools available:

- `get_current_datetime` - Current time
- `search_documents` - RAG search
- `research_report` - Multi-document analysis
- External MCP tools

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
