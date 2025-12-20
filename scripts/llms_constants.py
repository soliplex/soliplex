"""Shared constants for llms.txt federation and validation scripts.

This module centralizes all configuration, patterns, and mappings used by:
- federate_llms_txt.py (MkDocs post-build hook)
- validate_llms_strategy.py (Federation validation)
"""

# Domain configurations with validation thresholds
# threshold = max ratio of map size to content size
DOMAINS = {
    "project": {
        "map": "llms-project.txt",
        "content": "llms-project-full.txt",
        "threshold": 0.10,  # <10% (mostly links)
    },
    "server": {
        "map": "llms-server.txt",
        "content": "llms-server-full.txt",
        "threshold": 0.05,  # <5% (categorized index)
    },
    "client": {
        "map": "llms-client.txt",
        "content": "llms-client-full.txt",
        "threshold": 0.20,  # <20% (curated semantic index)
    },
}

# Section mappings: header name -> output filename
SECTIONS = {
    "Project Documentation": "llms-project.txt",
    "Server API Reference": "llms-server.txt",
    "Client API Reference": "llms-client.txt",
}

# Regex patterns (named for clarity and testability)
PATTERNS = {
    # Markdown link: [text](url)
    "markdown_link": r"\[([^\]]+)\]\(([^)]+)\)",
    # Server API item header: ## `ClassName` or ## `func_name(`
    "item_header": r"^## `([^`(]+)",
    # Source code reference: Source code in `path/to/file.py`
    "source_file": r"Source code in `([^`]+)`",
    # Remote URL to replace in local mode
    "remote_url": r"https://soliplex\.github\.io/soliplex/",
    # Client API URL structure: .../reference/client_api/{directory}/{class}/...
    "client_api_url": r"\(.*?/reference/client_api/([^/]+)/",
}

# Server API categorization by source file
SERVER_SOURCE_CATEGORIES = {
    "config.py": "Configuration",
    "models.py": "Models & Data",
    "cli.py": "CLI Commands",
    "tools.py": "Tools",
    "convos.py": "Conversations",
    "agents.py": "Agents",
    "views/": "API Endpoints",
    "agui": "AG-UI Protocol",
}

# Server category sort order
SERVER_CATEGORY_ORDER = [
    "Configuration",
    "Models & Data",
    "Agents",
    "Tools",
    "Conversations",
    "CLI Commands",
    "AG-UI Protocol",
    "API Endpoints",
    "Utilities & Misc",
]

# Client API categorization keywords
CLIENT_PATH_KEYWORDS = {
    # High-priority explicit mappings
    "agui_events": "AG-UI Protocol",
    "widget_registry": "Core Architecture",
    # Service/state patterns
    "service": "Services & State",
    "notifier": "Services & State",
    "manager": "Services & State",
    # Model patterns
    "model": "Models & Data",
    "entity": "Models & Data",
    "types": "Models & Data",
    # Network patterns
    "network": "Network & API",
    "transport": "Network & API",
    "client": "Network & API",
    "api": "Network & API",
    # UI patterns
    "widget": "UI Components",
    "screen": "UI Components",
    "dialog": "UI Components",
    "view": "UI Components",
    "layout": "UI Components",
    "card": "UI Components",
    "chip": "UI Components",
    "drawer": "UI Components",
    # Auth patterns
    "auth": "Authentication",
    "oidc": "Authentication",
}

# Client category sort order
CLIENT_CATEGORY_ORDER = [
    "Core Architecture",
    "AG-UI Protocol",
    "Services & State",
    "Models & Data",
    "Network & API",
    "Authentication",
    "UI Components",
    "Utilities & Misc",
]

# Noise patterns to filter from map content
MAP_NOISE_PATTERNS = [
    "Method:",
    "Property:",
    "Constructor:",
    "Operator:",
    "Static Method:",
]

# Test patterns to exclude from client map
TEST_PATTERNS = ["_test", "test/", "Test"]

DEFAULT_CATEGORY = "Utilities & Misc"
