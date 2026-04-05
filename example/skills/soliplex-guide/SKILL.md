---
name: soliplex-guide
description: Understand the Soliplex platform — rooms, tools, AG-UI protocol, and how to interact with users effectively
---

# Soliplex Platform Guide

You are running inside **Soliplex**, an AI-powered platform with multi-room
chat environments, document search (RAG), and support for multiple agent backends.

## When to Use This Skill

Refer to this when:
- A user asks about Soliplex features or how something works
- You need to understand what tools and capabilities are available
- You want to provide context-aware responses about the platform

## Platform Architecture

Soliplex has three layers:

1. **Flutter Frontend** — the user's interface. Shows conversations, tool calls,
   thinking indicators, and thread history. Communicates via AG-UI protocol.

2. **Soliplex Backend** (FastAPI) — manages rooms, authentication, thread
   persistence, and agent routing. Each room has its own agent configuration.

3. **Agent Backends** — the AI that processes messages. Can be:
   - **pydantic-ai** — Soliplex's native agent with RAG and haiku-skills
   - **Hermes Agent** — NousResearch's self-improving agent with 30+ tools,
     74 skills, and persistent memory

## Rooms

Each room is an independent chat environment with its own:
- Agent configuration (model, tools, system prompt)
- Conversation threads (persisted to database)
- Tool access (configured per room)

Users can have multiple threads per room. Each thread maintains its own
conversation history.

## Available Tool Types

Depending on the room configuration, you may have access to:

### Soliplex Native Tools
- **RAG search** — search documents in the knowledge base
- **File uploads** — list and read uploaded files
- **Current datetime** — get the current time
- **User profile** — get info about the current user

### Hermes Tools (if in a Hermes or hybrid room)
- **web_search** — search the web via Tavily
- **web_extract** — extract content from URLs
- **terminal** — execute shell commands
- **read_file / write_file / search_files** — file operations
- **execute_code** — run code in a sandbox
- **memory** — save and recall facts across sessions
- **skills** — access 74 specialized skill procedures
- **cronjob** — schedule recurring tasks
- **delegate_task** — spawn sub-agents for parallel work
- **vision** — analyze images (if API key configured)
- **browser** — automated web browsing (if configured)

### Client-Side Tools (if provided by the frontend)
- These are tools that run in the user's browser
- Common examples: confirm_action, open_url, copy_to_clipboard
- When you call these, the conversation pauses until the user responds

## How Conversations Work

1. User sends a message in a room
2. The message arrives with the full conversation history
3. You process it, optionally calling tools
4. Your response streams back to the user token-by-token
5. Tool calls appear as expandable cards in the UI
6. The conversation is saved for the user to return to later

## State Management

Each conversation thread has persistent state that survives page refreshes:
- **Thread state** — stored by Soliplex in the database
- **Hermes memory** — if using Hermes, facts saved via the memory tool
  persist across ALL conversations (not just the current thread)
- **Hermes skills** — skills the agent creates are available in future conversations

## Best Practices

### Be Tool-Aware
- Check what tools are available before attempting to use one
- If a tool call fails, explain what happened and suggest alternatives
- Don't assume tools exist — the room config determines what's available

### Be Context-Aware
- You may be in a room focused on a specific topic (research, coding, etc.)
- The system prompt tells you your role — follow it
- If you have RAG access, search documents before giving general answers

### Handle Errors Gracefully
- If a tool times out, say so and offer to retry
- If you can't reach an external service, explain the limitation
- Never pretend to have information you don't have

### Respect the User's Environment
- Files you create live inside the agent container, not on the user's machine
- Terminal commands execute in a sandboxed environment
- Don't attempt destructive operations without confirmation
- If client-side confirmation tools are available, use them for dangerous actions

## Quick Reference

| Action | How |
|--------|-----|
| Search documents | Use RAG search tool (if available) |
| Search the web | Use web_search or hermes_tool("web_search", ...) |
| Run a command | Use terminal or hermes_tool("terminal", ...) |
| Remember something | Use memory tool (if available) |
| Check the time | Use get_current_datetime or terminal("date") |
| Complex research | Use run_hermes_task (if in hybrid room) |
| Ask for confirmation | Use client-side confirm_action tool (if registered) |
