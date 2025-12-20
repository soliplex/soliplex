"""Test fixtures for llms.txt federation scripts."""

import sys
from pathlib import Path

import pytest

# Add scripts directory to path for imports
scripts_dir = Path(__file__).parent.parent.parent.parent / "scripts"
sys.path.insert(0, str(scripts_dir))

# Synthetic test data - minimal samples that exercise the logic
SAMPLE_LLMS_MAP = """# Soliplex

# Project Documentation

- [Overview](https://example.com/overview.md)
- [Setup Guide](https://example.com/setup.md)

# Server API Reference

- [API Overview](https://example.com/server.md)

# Client API Reference

- [Overview for SampleWidget](https://example.com/reference/client_api/widget/SampleWidget/overview.md)
- [Overview for AuthService](https://example.com/reference/client_api/auth_service/AuthService/overview.md)
- [Method: doSomething](https://example.com/reference/client_api/widget/SampleWidget/method.md)
"""

SAMPLE_LLMS_FULL = """# Soliplex

# Project Documentation

## Overview

This is the full project overview with detailed content.
Architecture description goes here.

## Setup Guide

Full setup instructions with code examples.

# Server API Reference

## `SampleConfig`

Configuration class for the application.

Source code in `src/soliplex/config.py`

## `SampleModel`

A data model class.

Source code in `src/soliplex/models.py`

## `get_agent`

Agent factory function.

Source code in `src/soliplex/agents.py`

# Client API Reference

## Widget Library

- [SampleWidget](https://example.com/reference/client_api/widget/SampleWidget/overview.md)
- [AuthService](https://example.com/reference/client_api/auth_service/AuthService/overview.md)
"""


@pytest.fixture
def sample_site_dir(tmp_path):
    """Create minimal site directory with synthetic llms files."""
    site = tmp_path / "site"
    site.mkdir()
    (site / "llms.txt").write_text(SAMPLE_LLMS_MAP)
    (site / "llms-full.txt").write_text(SAMPLE_LLMS_FULL)
    return site


@pytest.fixture
def sample_site_with_domains(sample_site_dir):
    """Site directory with pre-split domain files for validation testing."""
    # Create domain map files
    (sample_site_dir / "llms-project.txt").write_text(
        "# Soliplex - Project Documentation\n\n- [Overview](overview.md)\n"
    )
    (sample_site_dir / "llms-server.txt").write_text(
        "# Soliplex - Server API Reference\n\n## Configuration\n- `SampleConfig`\n"
    )
    (sample_site_dir / "llms-client.txt").write_text(
        "# Soliplex - Client API Reference\n\n## UI Components\n- [SampleWidget](widget.md)\n"
    )
    # Create domain content files (larger)
    (sample_site_dir / "llms-project-full.txt").write_text(
        "# Soliplex - Project Documentation\n\n" + "Content " * 1000
    )
    (sample_site_dir / "llms-server-full.txt").write_text(
        "# Soliplex - Server API Reference\n\n" + "Server content " * 2000
    )
    (sample_site_dir / "llms-client-full.txt").write_text(
        "# Soliplex - Client API Reference\n\n" + "Client content " * 5000
    )
    return sample_site_dir


@pytest.fixture(params=["local", "relative", "remote"])
def docs_mode(request):
    """Parametrized fixture for all DOCS_MODE values."""
    return request.param


@pytest.fixture
def local_site_url(sample_site_dir):
    """Local mode site URL (absolute filesystem path)."""
    return str(sample_site_dir) + "/"


@pytest.fixture
def remote_site_url():
    """Remote mode site URL."""
    return "https://soliplex.github.io/soliplex/"
