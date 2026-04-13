# Soliplex Overview

## Why Soliplex?

**Soliplex** (from *solus* "alone" + *plex* "interwoven") is a full-stack RAG/AI system designed for deployments where connectivity, compliance, and customization constraints rule out typical SaaS solutions.

### Elevator Pitch

Soliplex is a thin configuration and authentication layer around [pydantic-ai](https://ai.pydantic.dev/) that ships with a security-hardened Flutter frontend. You get typed, modern Python on the backend with minimal framework overhead, and a native mobile/desktop client built for environments with strict security and network isolation requirements. Rooms let you organize agents, LLMs, and knowledge bases into distinct workspaces—like IRC channels for your AI.

### When to Use Soliplex

- **Strict security requirements**: Your deployment needs hardened cryptography, secure credential storage, or validated security controls that browser-based apps can't provide
- **Air-gapped or disconnected environments**: You need the full stack to run without internet access
- **Self-hosted mandate**: You can't use hosted LLM APIs or managed RAG services
- **Multi-domain organization**: You need isolated "rooms" mapping to different business processes, teams, or data sources
- **Building on pydantic-ai**: You want AI-generated code and community tooling to work with minimal adaptation
- **Whitelabel delivery**: Consultants or integrators shipping branded AI solutions to multiple customers

### When NOT to Use Soliplex

- **You want a hosted solution**: Soliplex is self-hosted only
- **You need visual flow builders**: No drag-and-drop agent orchestration (n8n-style)
- **You want heavy abstractions**: Soliplex doesn't wrap pydantic-ai in framework layers—you write standard Python
- **You're not using Python**: The backend is Python; if you need Node/Go/Rust, look elsewhere
- **Single-use chatbot**: If you only need one simple chat endpoint, Soliplex's room/installation model may be overkill

### How It Differs from Alternatives

| Concern | LangChain / LlamaIndex | Vercel AI SDK | Soliplex |
|---------|------------------------|---------------|----------|
| Language | Python | TypeScript | Python (backend), Dart (frontend) |
| Typing | Mixed | Good | Strong (pydantic-ai) |
| Framework weight | Heavy | Medium | Minimal (configuration + wiring) |
| Native mobile/desktop | No | No | Yes (Flutter) |
| Hardened client security | DIY | No | Native crypto, secure storage |
| Air-gapped deployment | Difficult | No | First-class |
| Communication protocol | Various | AI SDK | [AG-UI](https://docs.ag-ui.com/) |

### What's Included

- **Backend**: FastAPI server with pydantic-ai agent management, OIDC auth, MCP support
- **Frontend**: Flutter app with encrypted storage, native OIDC, whitelabel support
- **RAG**: Integration with [haiku-rag](https://github.com/ggozad/haiku-rag) and LanceDB (optional, swappable)
- **TUI**: Terminal client for quick testing

### What's NOT Included

- Hosted LLM inference (bring your own: OpenAI, Ollama, Google, etc.)
- Managed vector database (LanceDB runs embedded or you provide your own)
- Visual agent builder UI
- Multi-tenant SaaS infrastructure

---

## What Is Soliplex?

Soliplex is an AI-powered Retrieval-Augmented Generation (RAG)
system designed to provide intelligent document search and question-answering
capabilities.

## Architecture

The system consists of three main components:

### 1. Backend Server (`src/soliplex/`)

- **Technology**: FastAPI with Python 3.12+
- **Purpose**: Handles API requests, RAG processing, and AI model integration
- **Features**:
  - OpenAI API integration
  - Document indexing and retrieval
  - Authentication and authorization
  - Real-time WebSocket communication

### 2. Frontend Client (`src/flutter/`)

- **Technology**: Flutter web application
- **Purpose**: Provides user interface for chat and document interaction
- **Features**:
  - Material Design UI
  - Real-time chat interface
  - State management with Riverpod
  - Responsive web design

### 3. Configuration System

- **OIDC Authentication**: Keycloak integration for secure access
- **Room Configuration**: Chat environments and settings
- **Model Configuration**: LLM provider and model settings

## Key Features

- **RAG Capabilities**: Combines document retrieval with AI generation
- **Multiple AI Models**: Support for OpenAI and local models
- **Secure Authentication**: OIDC-based user management
- **Real-time Chat**: WebSocket-powered interactive communication
- **Document Management**: Upload, index, and search through documents
