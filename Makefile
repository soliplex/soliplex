# Soliplex Documentation Makefile
#
# Usage: make <target>
#        make help

.PHONY: help docs docs-absolute docs-local docs-relative docs-remote docs-serve \
        docs-validate docs-eval docs-eval-dry docs-eval-nav docs-clean dart-docs client-api-index

# Default target
help:
	@echo "Soliplex Documentation Tasks"
	@echo "============================"
	@echo ""
	@echo "Build Targets:"
	@echo "  docs              Build docs (default: absolute mode for local agents)"
	@echo "  docs-absolute     Build with filesystem paths (/Users/you/site/...)"
	@echo "  docs-local        Build with localhost URLs (http://localhost:8000/...)"
	@echo "  docs-relative     Build with relative paths (portable archives)"
	@echo "  docs-remote       Build with production URLs (soliplex.github.io)"
	@echo "  docs-serve        Run mkdocs dev server on localhost:8000"
	@echo "  docs-clean        Remove built site directory"
	@echo ""
	@echo "Pre-build Targets:"
	@echo "  dart-docs         Generate Dart API markdown from Flutter source"
	@echo "  client-api-index  Generate client API index page"
	@echo "  docs-full         Run dart-docs + client-api-index + docs"
	@echo ""
	@echo "Validation Targets:"
	@echo "  docs-validate     Validate llms.txt federation (file sizes, links)"
	@echo "  docs-validate-json  Same as above, JSON output"
	@echo ""
	@echo "Evaluation Targets:"
	@echo "  docs-eval-dry     Dry run - list eval cases without calling LLM"
	@echo "  docs-eval         Run LLM comprehension eval (requires OPENAI_API_KEY)"
	@echo "  docs-eval-nav     Run navigation mode eval (tests index usage)"
	@echo "  docs-eval-json    Run eval with JSON output"
	@echo ""
	@echo "Environment Variables:"
	@echo "  DOCS_MODE         absolute|local|relative|remote (default: absolute)"
	@echo "  LOCAL_PORT        Port for local mode (default: 8000)"
	@echo "  OPENAI_API_KEY    Required for docs-eval targets"
	@echo "  OLLAMA_URL        Use Ollama instead (e.g., http://127.0.0.1:11434/v1)"
	@echo "  LOGFIRE_TOKEN     Enable Logfire tracing for evals"
	@echo "  PROVIDER          LLM provider: openai (default) or ollama"
	@echo "  MODEL             Model name (default: gpt-4o-mini or llama3.2)"
	@echo "  DOMAIN            Eval domain: project, server, or client"

# === Build Targets ===

docs:
	./scripts/build_docs.sh

docs-absolute:
	DOCS_MODE=absolute ./scripts/build_docs.sh

docs-local:
	DOCS_MODE=local ./scripts/build_docs.sh

docs-relative:
	DOCS_MODE=relative ./scripts/build_docs.sh

docs-remote:
	DOCS_MODE=remote ./scripts/build_docs.sh

docs-serve:
	uv run mkdocs serve

docs-clean:
	rm -rf site/

# === Pre-build Targets ===

dart-docs:
	./scripts/generate_dart_markdown.sh

client-api-index:
	uv run python scripts/generate_client_api_index.py

docs-full: dart-docs client-api-index docs

# === Validation Targets ===

docs-validate:
	uv run python scripts/validate_llms_strategy.py

docs-validate-json:
	uv run python scripts/validate_llms_strategy.py --json

# === Evaluation Targets ===

# Build eval args from environment variables
EVAL_ARGS :=
ifdef PROVIDER
  EVAL_ARGS += --provider $(PROVIDER)
endif
ifdef MODEL
  EVAL_ARGS += --model $(MODEL)
endif
ifdef DOMAIN
  EVAL_ARGS += --domain $(DOMAIN)
endif

docs-eval-dry:
	uv run python scripts/eval_comprehension.py --dry-run $(EVAL_ARGS)

docs-eval:
	uv run python scripts/eval_comprehension.py $(EVAL_ARGS)

docs-eval-nav:
	uv run python scripts/eval_comprehension.py --mode navigation $(EVAL_ARGS)

docs-eval-json:
	uv run python scripts/eval_comprehension.py --json $(EVAL_ARGS)
