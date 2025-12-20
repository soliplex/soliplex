# Admin Guide

This guide covers configuration, deployment, and administration of Soliplex installations.

## Overview

Soliplex uses a YAML-based configuration system that supports:

- **Hierarchical configuration** - Installation → Rooms → Agents
- **Secret management** - Environment variables, files, or auto-generation
- **Multiple authentication providers** - OIDC with various providers
- **Flexible deployment** - Development, Docker, or production

## Sections

- **[Configuration](configuration/index.md)** - YAML configuration for installations, rooms, agents, and RAG
- **[Deployment](deployment/index.md)** - Docker, production setup, and monitoring
- **[Authentication](authentication/index.md)** - OIDC providers and authentication patterns

## Configuration Hierarchy

```
installation.yaml          # Main configuration file
├── secrets                # API keys, tokens
├── environment            # Environment variables
├── agent_configs          # Global agent definitions
├── room_paths             # References to room configs
│   └── rooms/*/room_config.yaml
├── completion_paths       # References to completion configs
│   └── completions/*/completion_config.yaml
└── oidc_paths             # Directories containing oidc/config.yaml
    └── oidc/config.yaml
```

## Quick Reference

### Start Server

```bash
# Development mode (no authentication)
soliplex-cli serve example/minimal.yaml --no-auth-mode

# Production mode
soliplex-cli serve /path/to/installation.yaml
```

### Validate Configuration

```bash
soliplex-cli check-config example/installation.yaml
```

### List Rooms

```bash
soliplex-cli list-rooms example/installation.yaml
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OLLAMA_BASE_URL` | Yes* | Ollama server URL (e.g., `http://127.0.0.1:11434`) |
| `OPENAI_API_KEY` | No | OpenAI API key for cloud models |
| `INSTALLATION_PATH` | No | Override installation config path |
| `RAG_LANCE_DB_PATH` | No | Override RAG database path |

*Required when using Ollama as LLM provider

## Security Considerations

**Warning - Production Deployment:**
- Never use `--no-auth-mode` in production
- Configure OIDC authentication
- Use proper secret management
- Enable HTTPS via reverse proxy