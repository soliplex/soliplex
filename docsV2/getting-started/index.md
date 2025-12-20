# Getting Started

Welcome to Soliplex! This guide will help you get up and running quickly.

## Prerequisites

Before you begin, ensure you have the following installed:

| Requirement | Version | Purpose |
|-------------|---------|---------|
| **Python** | 3.13+ | Backend server |
| **Flutter** | 3.x | Frontend application |
| **Ollama** | Latest | Local LLM inference |
| **Git** | Any | Clone the repository |

## Choose Your Path

- **[Quickstart](quickstart.md)** - Get Soliplex running with minimal configuration (5 minutes)
- **[Full Installation](installation.md)** - Complete setup with all configuration options
- **[Your First Chat](first-chat.md)** - Send your first message and explore features

## System Requirements

### Hardware

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| **RAM** | 8 GB | 16+ GB |
| **Storage** | 10 GB | 50+ GB (for LLM models) |
| **GPU** | None (CPU only) | Apple Silicon or NVIDIA GPU |

**Tip for Apple Silicon Users:** Soliplex works best with native ARM64 binaries. If you're using an M1/M2/M3 Mac, ensure Homebrew and Ollama are installed as ARM64 versions for optimal performance.

### Network

- Port 8000: Backend API server
- Port 59001: Flutter web app (development)
- Port 11434: Ollama server

## What's Next?

After completing the quickstart, explore:

- [Rooms Configuration](../admin-guide/configuration/rooms.md) - Set up chat environments
- [Agent Configuration](../admin-guide/configuration/agents.md) - Configure LLM models
- [RAG Setup](../developer-guide/rag/database.md) - Add document search capabilities