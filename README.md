# Soliplex

An AI-powered Retrieval-Augmented Generation (RAG) system with a modern web interface.

## Features

- **RAG-Powered Search**: Semantic document retrieval using LanceDB vector database
- **Multi-Room Architecture**: Independent chat environments with separate configurations and knowledge bases
- **Multiple LLM Providers**: OpenAI, Ollama, and compatible APIs
- **AI Agent System**: Function calling and tool integration for AI agents
- **OIDC Authentication**: Enterprise SSO with Keycloak integration
- **Model Context Protocol (MCP)**: Extended AI capabilities through MCP client or exposing Room as MCP server
- **Real-time Communication**: WebSocket-based conversation streams
- **Quiz System**: Custom quizzes with LLM-based evaluation
- **Observability**: Logfire integration for monitoring

## Architecture

### Backend (`/src/soliplex/`)
**Python 3.13+ / FastAPI**

- **Core**: FastAPI application with async support
- **RAG Engine**: Haiku RAG (0.12.1+) with LanceDB vector storage
- **AI Integration**: Pydantic AI (1.0.11+) for agent management
- **Authentication**: Python-Keycloak with OIDC/JWT support
- **MCP**: FastMCP (2.12.3+) server and client implementations
- **Configuration**: YAML-based configuration system

Key modules:
- `views/` - API endpoints (auth, completions, conversations, rooms, quizzes)
- `agents.py` - AI agent configuration and management
- `convos.py` - Conversation persistence and retrieval
- `tools.py` - Tool definitions for AI agents
- `mcp_server.py` / `mcp_client.py` - Model Context Protocol integration
- `tui/` - Terminal user interface

### Frontend (`/src/flutter/`)
**Flutter 3.35+ / Dart 3.10.0+**

- **Framework**: Flutter web with Material Design
- **State Management**: Riverpod (2.6.1)
- **Navigation**: Go Router (16.0.0)
- **Authentication**: Flutter AppAuth (9.0.1) for OIDC
- **Real-time**: WebSocket communication
- **Secure Storage**: Flutter Secure Storage for credentials

Key files:
- `main.dart` - Application entry point
- `soliplex_client.dart` - Backend API client
- `oidc_client.dart` - OIDC authentication client
- `controllers.dart` - Riverpod state management
- `configure.dart` - Configuration UI

## Quick Start

### Backend

```bash
# Install
python3.13 -m venv venv
source venv/bin/activate
pip install -e .

# Run
soliplex-cli serve example --no-auth-mode
```

### Frontend

```bash
cd src/flutter
flutter pub get
flutter run -d chrome --web-port 59001
```

## Configuration

YAML-based configuration with:
- **Installation** (`installation.yaml`) - Main config referencing agents, rooms, and OIDC providers
- **Rooms** (`rooms/*.yaml`) - Individual chat room configurations with RAG settings
- **Agents** (`completions/*.yaml`) - LLM provider and model configurations
- **OIDC** (`oidc/*.yaml`) - Authentication provider settings

See `example/` directory for sample configurations.

## License

MIT License - Copyright (c) 2025 Enfold Systems, Inc.
