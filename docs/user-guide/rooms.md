# Chat Rooms

Rooms are chat environments with specialized AI assistants.

## Selecting a Room

1. Open the Soliplex app
2. Open the navigation drawer (☰)
3. Choose a room from the list
4. Start chatting!

Each room has:
- **Name** - The room title
- **Description** - What the room is for
- **Suggestions** - Starter questions to try

## Sending Messages

Type your message in the input area and press Enter or click Send.

**Tips:**
- Be specific with your questions
- Provide context when needed
- Ask follow-up questions to dig deeper

## Message Types

### Text Responses

The AI responds with formatted text, including:
- Markdown formatting
- Code blocks with syntax highlighting
- Lists and tables

### Tool Calls

When the AI uses tools (like searching documents), you'll see:
- Collapsible "Used N tools" summary
- Progress spinner while executing
- Individual tool status (running, completed, error)

Click to expand and see each tool's name and status.

### Citations

For RAG-enabled rooms, responses include:
- Collapsible citations section below the message
- Document title and page numbers (for PDFs)
- Expandable content excerpts

See [Document Search](rag-search.md) for details.

## Conversation Threads

### Starting a New Thread

Click the **+** button in the threads panel to start a fresh conversation.

### Thread History

- Previous threads are saved
- Access from the threads panel (three-column layout)
- Continue where you left off

### Thread Metadata

- Title (optional, shows thread ID if not set)
- Created date
- Last updated date

## Room Features

### RAG Search

Rooms with document search can:
- Find relevant information in documents
- Provide citations with source excerpts
- Answer questions from your knowledge base

### Suggestions

Starter questions appear when entering a room. Click to use as your first message.

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Enter` | Send message |
| `Shift+Enter` | New line |
| `Alt+/` | Show shortcuts |

See [Keyboard Shortcuts](keyboard-shortcuts.md) for the complete list.

## Tips for Effective Chat

1. **Be specific** - Clear questions get better answers
2. **Provide context** - Help the AI understand your needs
3. **Use follow-ups** - Build on previous responses
4. **Check citations** - Expand to verify sources
5. **Try suggestions** - Room suggestions are tailored to the room's purpose

## Troubleshooting

### Slow Responses

- Large language models take time to process
- Tool calls add processing time
- Check your network connection

### No Response

- Verify you're connected to the server
- Check authentication status
- Try refreshing the page

### No Citations

- Not all rooms have RAG enabled
- The AI may answer from general knowledge
- Check room capabilities in the room info panel
