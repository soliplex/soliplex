# Soliplex Documentation

Soliplex is a multi-component AI platform that combines a FastAPI backend, Flutter frontend, and powerful RAG capabilities to create intelligent chat experiences powered by local or cloud LLMs.

## Quick Links

- **[Getting Started](getting-started/quickstart.md)** - Get Soliplex running locally in 5 minutes
- **[User Guide](user-guide/index.md)** - Learn how to use Soliplex chat rooms and features
- **[Admin Guide](admin-guide/index.md)** - Configure, deploy, and manage Soliplex
- **[Developer Guide](developer-guide/index.md)** - Understand the architecture and extend Soliplex

## What is Soliplex?

Soliplex provides a complete platform for building AI-powered applications:

- **Multi-LLM Support** - Use Ollama for local inference or OpenAI for cloud-based models
- **RAG Integration** - Built-in document retrieval with LanceDB vector storage
- **MCP Protocol** - Expose and consume tools via the Model Context Protocol
- **AG-UI Streaming** - Real-time streaming responses with rich event types
- **Cross-Platform** - Flutter app runs on web, mobile, and desktop

## Architecture Overview

```
┌─────────────────┐     ┌─────────────────────────────────────────┐
│   Flutter App   │────▶│           FastAPI Backend               │
│(Web/Mobile/Desk)│ SSE │                                         │
└─────────────────┘     │  ┌─────────────┐    ┌───────────────┐  │
                        │  │ Pydantic AI │───▶│ LLM Provider  │  │
                        │  │   Agents    │    │ (Ollama/OpenAI)│  │
                        │  └─────────────┘    └───────────────┘  │
                        │         │                               │
                        │  ┌──────▼──────┐    ┌───────────────┐  │
                        │  │    Tools    │───▶│   RAG Store   │  │
                        │  │             │    │   (LanceDB)   │  │
                        │  └─────────────┘    └───────────────┘  │
                        └─────────────────────────────────────────┘
```

## Key Concepts

| Concept | Description |
|---------|-------------|
| **Room** | A chat environment with specific LLM, tools, and RAG configuration |
| **Agent** | A Pydantic AI agent that handles conversations and tool execution |
| **Thread** | A conversation session containing multiple runs |
| **Run** | A single request-response cycle within a thread |
| **Tool** | A function the agent can call (e.g., search documents, get time) |

## Version

This documentation covers Soliplex v0.27+.

## Getting Help

- **Issues**: [GitHub Issues](https://github.com/soliplex/soliplex/issues)
- **Discussions**: [GitHub Discussions](https://github.com/soliplex/soliplex/discussions)