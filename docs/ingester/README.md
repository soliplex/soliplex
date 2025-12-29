# Soliplex Ingester Documentation

This project is designed to provide a robust system to load documents from various sources into RAG systems.  The default configuration is intended to provide populated databases for the [Soliplex](https://github.com/soliplex/soliplex) RAG (Retrieval Augmented Generation) system but it can be customized to support other storage systems and language models.

Document ingestion can be a time consuming and error prone process.  Soliplex ingester aims to provide a robust, scalable and observable pathway from source systems to one or more vector databases. It provides a user interface and REST endpoints to follow the progress of documents and supports restarting failed processes.

This ingester has been tested with workflows containing hundreds of documents and with pdf files containing over one thousand pages (on appropriate hardware) so scalability and reliability paramount.

Soliplex ingester has been designed alongside [agents](https://github.com/soliplex/ingester-agents) that are able do load data from filesystems and source control management systems, but other tools can be used as well.

## Documentation Index

### Getting Started

- **[Getting Started Guide](docs/GETTING_STARTED.md)** - Quick start tutorial for new users
  - Installation and setup
  - First batch processing
  - Basic operations
  - Common patterns

### Core Documentation

- **[Architecture Overview](docs/ARCHITECTURE.md)** - System design and components
  - Component overview
  - Technology stack
  - Scalability considerations

- **[API Reference](docs/API.md)** - Complete REST API documentation
  - All endpoints with examples
  - Request/response formats
  - Data models
  - Error handling

- **[Workflow System](docs/WORKFLOWS.md)** - Workflow concepts and configuration
  - Workflow step types
  - Configuration files
  - Execution model
  - Custom step handlers
  - Retry logic
  - Monitoring and troubleshooting

- **[Database Schema](docs/DATABASE.md)** - Data models and relationships
  - All database tables
  - Field descriptions
  - Relationships and constraints
  - Query examples
  - Migration guide

- **[Configuration Guide](docs/CONFIGURATION.md)** - Environment variables and settings
  - All configuration options
  - Environment-specific configs
  - Performance tuning
  - Secrets management
  - Troubleshooting

- **[CLI Reference](docs/CLI.md)** - Command-line interface guide
  - All CLI commands
  - Usage examples
  - Deployment patterns
  - Systemd integration

## Quick Links

### For New Users
1. Start with [Getting Started](docs/GETTING_STARTED.md)
2. Review [Architecture](docs/ARCHITECTURE.md) to understand the system
3. Explore [API Reference](docs/API.md) for integration

### For Developers
1. Read [Architecture](docs/ARCHITECTURE.md) for system design
2. Study [Workflows](docs/WORKFLOWS.md) to understand processing
3. Check [Database](docs/DATABASE.md) for data models
4. Review [Configuration](docs/CONFIGURATION.md) for environment setup

### For Operations
1. Review [Configuration](docs/CONFIGURATION.md) for deployment settings
2. Use [CLI Reference](docs/CLI.md) for management commands
3. Monitor using [API Reference](docs/API.md) stats endpoints
4. Troubleshoot with [Workflows](docs/WORKFLOWS.md) debugging section

## Document Summaries

### GETTING_STARTED.md
Step-by-step guide to:
- Install Soliplex Ingester
- Configure the system
- Create your first batch
- Ingest and process documents
- Monitor progress
- Deploy to production

**Audience:** New users, evaluators
**Time to complete:** 15-30 minutes

---

### ARCHITECTURE.md
Technical overview covering:
- System components (API server, workers, storage)
- Workflow execution model
- Data flow and processing pipeline
- Storage backends (database, files, vectors)
- Scalability and performance
- Extension points

**Audience:** Developers, architects
**Time to read:** 15-20 minutes

---

### API.md
Complete REST API reference including:
- Document ingestion endpoints
- Batch management APIs
- Workflow control and monitoring
- Parameter set configuration
- Data models and schemas
- Error handling

**Audience:** API consumers, integrators
**Format:** Reference documentation

---

### WORKFLOWS.md
In-depth workflow documentation:
- Workflow concepts and terminology
- Step types (ingest, parse, chunk, embed, store)
- YAML configuration format
- Lifecycle events
- Worker processing model
- Custom handler development
- Retry and error handling
- Performance tuning
- Troubleshooting guide

**Audience:** Power users, developers
**Time to read:** 25-30 minutes

---

### DATABASE.md
Database schema reference covering:
- All table definitions
- Field types and constraints
- Relationships and foreign keys
- Enums and constants
- Migration procedures
- Query examples
- Indexing recommendations
- Backup and maintenance

**Audience:** Database administrators, developers
**Format:** Reference documentation

---

### CONFIGURATION.md
Comprehensive configuration guide:
- All environment variables
- Default values and types
- Configuration validation
- Environment-specific configs
- Performance tuning parameters
- Worker settings
- Storage configuration
- Secrets management
- Docker and Kubernetes examples
- Troubleshooting

**Audience:** DevOps, system administrators
**Format:** Reference + guide

---

### CLI.md
Command-line tool reference:
- All CLI commands with options
- Usage examples
- Deployment patterns
- Systemd service files
- Docker usage
- Signal handling
- Platform notes
- Troubleshooting

**Audience:** System administrators, developers
**Format:** Reference documentation

---




### Configuration Examples

Check `config/` directory for:
- `workflows/*.yaml` - Example workflow definitions
- `params/*.yaml` - Example parameter sets

Check `docker/` directory for how to use docker compose to provision support services.

## Documentation Maintenance

### Contributing to Docs

When updating documentation:

1. **Keep it accurate** - Test all examples before committing
2. **Stay consistent** - Follow existing formatting and style
3. **Be comprehensive** - Cover edge cases and gotchas
4. **Add examples** - Show, don't just tell
5. **Update index** - Modify this README when adding docs

### Documentation Standards

- **Format:** Markdown with GitHub-flavored syntax
- **Code blocks:** Always specify language for syntax highlighting
- **Examples:** Include both curl and Python/script examples where applicable
- **Cross-references:** Link to related sections and documents
- **Versioning:** Note breaking changes and version requirements

### Feedback

Found an error or unclear section? Please:
- Open an issue describing the problem
- Suggest improvements via pull request
- Ask questions in discussions

## Version Information

- **Version:** 0.1.0
- **Python:** 3.12+


## License

See LICENSE file in project root.

---

## Getting Help

### Documentation Issues
- Found a mistake? Open an issue
- Need clarification? Start a discussion
- Have suggestions? Submit a pull request




### Related Documentation
- **HaikuRAG:** https://github.com/ggozad/haiku.rag
- **Docling:** https://docling-project.github.io/docling/
- **LanceDB:** https://lancedb.com/docs/
- **Soliplex:** https://github.com/soliplex/soliplex

---

## Quick Reference Card

```bash
# Installation
pip install -e .

# Configuration
si-cli validate-settings

# Database
si-cli db-init

# Server
si-cli serve --reload                    # Development
si-cli serve --host 0.0.0.0 --workers 4  # Production

# Workers
si-cli worker                            # Start worker

# Inspection
si-cli list-workflows                    # List workflows
si-cli dump-workflow batch               # View workflow
si-cli list-param-sets                   # List parameters
si-cli validate-haiku 1                  # Validate batch

# API
curl http://localhost:8000/docs          # Swagger UI
curl http://localhost:8000/api/v1/batch/ # List batches
curl http://localhost:8000/api/v1/document/ingest-document/ # load document into database

```

---
