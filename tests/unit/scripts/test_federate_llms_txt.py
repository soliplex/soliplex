"""Tests for federate_llms_txt.py."""

from federate_llms_txt import categorize_server_item
from federate_llms_txt import clean_map_content
from federate_llms_txt import localize_urls
from federate_llms_txt import restructure_server_map
from federate_llms_txt import split_file
from llms_constants import CLIENT_CATEGORY_ORDER
from llms_constants import DEFAULT_CATEGORY
from llms_constants import MAP_NOISE_PATTERNS
from llms_constants import PATTERNS
from llms_constants import SERVER_CATEGORY_ORDER
from llms_constants import SERVER_SOURCE_CATEGORIES
from llms_constants import TEST_PATTERNS


class TestCategorizeServerItem:
    """Tests for server API categorization."""

    def test_config_file_categorized(self):
        """Items from config.py go to Configuration."""
        category = categorize_server_item(
            "SampleConfig", "src/soliplex/config.py"
        )
        assert category == "Configuration"

    def test_models_file_categorized(self):
        """Items from models.py go to Models & Data."""
        category = categorize_server_item(
            "SampleModel", "src/soliplex/models.py"
        )
        assert category == "Models & Data"

    def test_agents_file_categorized(self):
        """Items from agents.py go to Agents."""
        category = categorize_server_item(
            "get_agent", "src/soliplex/agents.py"
        )
        assert category == "Agents"

    def test_tools_file_categorized(self):
        """Items from tools.py go to Tools."""
        category = categorize_server_item(
            "search_documents", "src/soliplex/tools.py"
        )
        assert category == "Tools"

    def test_cli_file_categorized(self):
        """Items from cli.py go to CLI Commands."""
        category = categorize_server_item("serve", "src/soliplex/cli.py")
        assert category == "CLI Commands"

    def test_views_directory_categorized(self):
        """Items from views/ go to API Endpoints."""
        category = categorize_server_item(
            "RoomView", "src/soliplex/views/rooms.py"
        )
        assert category == "API Endpoints"

    def test_agui_file_categorized(self):
        """Items with agui in path (not under views/) go to AG-UI Protocol."""
        # views/ matches first, so agui under views/ goes to API Endpoints
        category = categorize_server_item(
            "AGUIEvent", "src/soliplex/agui/events.py"
        )
        assert category == "AG-UI Protocol"

    def test_unknown_source_defaults(self):
        """Unknown source files get default category."""
        category = categorize_server_item("Mystery", "src/soliplex/unknown.py")
        assert category == DEFAULT_CATEGORY

    def test_none_source_defaults(self):
        """None source gets default category."""
        category = categorize_server_item("Orphan", None)
        assert category == DEFAULT_CATEGORY


class TestRestructureServerMap:
    """Tests for server map restructuring."""

    def test_extracts_items_from_content(self):
        """Correctly extracts class/function names."""
        content = """
# Server API

## `ConfigClass`

Some description.

Source code in `src/soliplex/config.py`

## `ModelClass`

Another description.

Source code in `src/soliplex/models.py`
"""
        result = restructure_server_map(content)

        assert "## Configuration" in result
        assert "`ConfigClass`" in result
        assert "## Models & Data" in result
        assert "`ModelClass`" in result

    def test_includes_navigation_header(self):
        """Output includes navigation guidance."""
        content = "## `SampleClass`\nSource code in `src/soliplex/config.py`"
        result = restructure_server_map(content)

        assert "llms-server-full.txt" in result

    def test_categories_sorted_correctly(self):
        """Categories appear in defined order."""
        content = """
## `ZConfig`
Source code in `src/soliplex/config.py`

## `AModel`
Source code in `src/soliplex/models.py`
"""
        result = restructure_server_map(content)
        lines = result.split("\n")

        config_idx = next(
            i for i, line in enumerate(lines) if "Configuration" in line
        )
        model_idx = next(
            i for i, line in enumerate(lines) if "Models & Data" in line
        )

        # Configuration should come before Models in SERVER_CATEGORY_ORDER
        assert config_idx < model_idx


class TestCleanMapContent:
    """Tests for map content cleaning."""

    def test_filters_noise_for_other_sections(self):
        """Generic sections filter noise patterns."""
        content = """
- [Valid Link](https://example.com)
- [Method: noisy](https://example.com)
"""
        result = clean_map_content(content, "Project Documentation")

        assert "Valid Link" in result
        assert "Method:" not in result


class TestLocalizeUrls:
    """Tests for URL localization."""

    def test_remote_mode_unchanged(self):
        """Remote mode (non-/) URLs are not modified."""
        content = "Visit https://soliplex.github.io/soliplex/page.html"
        result = localize_urls(content, "/site", "https://remote.com/")

        assert result == content

    def test_absolute_mode_replaces_urls(self):
        """Absolute mode replaces remote URLs with filesystem paths."""
        content = "Visit https://soliplex.github.io/soliplex/page.html"
        result = localize_urls(content, "/site", "/Users/me/site/")

        assert "https://soliplex.github.io/soliplex/" not in result
        assert "/Users/me/site/" in result

    def test_local_mode_unchanged(self):
        """Local mode (localhost URLs) does not trigger localization."""
        content = "Visit https://soliplex.github.io/soliplex/page.html"
        result = localize_urls(content, "/site", "http://localhost:8000/")

        # localhost URLs don't start with "/" so they pass through unchanged
        assert result == content

    def test_preserves_other_urls(self):
        """URLs not matching remote pattern are preserved."""
        content = "See https://other-site.com/docs and https://soliplex.github.io/soliplex/api"
        result = localize_urls(content, "/site", "/local/")

        assert "https://other-site.com/docs" in result
        assert "https://soliplex.github.io/soliplex/" not in result


class TestPatternConstants:
    """Tests for pattern constants used in federation."""

    def test_item_header_pattern(self):
        """Item header pattern matches class/function headers."""
        import re

        pattern = re.compile(PATTERNS["item_header"])

        assert pattern.match("## `ClassName`")
        assert pattern.match("## `function_name(")
        assert not pattern.match("# Not a match")

    def test_source_file_pattern(self):
        """Source file pattern extracts file paths."""
        import re

        pattern = re.compile(PATTERNS["source_file"])
        text = "Source code in `src/soliplex/config.py`"
        match = pattern.search(text)

        assert match is not None
        assert match.group(1) == "src/soliplex/config.py"

    def test_client_api_url_pattern(self):
        """Client API URL pattern extracts directory name."""
        import re

        pattern = re.compile(PATTERNS["client_api_url"])
        url = "(https://example.com/reference/client_api/my_widget/MyWidget/overview.md)"
        match = pattern.search(url)

        assert match is not None
        assert match.group(1) == "my_widget"

    def test_remote_url_pattern(self):
        """Remote URL pattern matches soliplex github pages URL."""
        import re

        pattern = re.compile(PATTERNS["remote_url"])

        assert pattern.search("https://soliplex.github.io/soliplex/docs")
        assert not pattern.search("https://other.github.io/other/docs")


class TestCategoryOrders:
    """Tests for category ordering constants."""

    def test_server_order_has_all_source_categories(self):
        """All server source categories are in the order list."""
        source_categories = set(SERVER_SOURCE_CATEGORIES.values())
        order_set = set(SERVER_CATEGORY_ORDER)

        # All categories from source mapping should be in order
        # (except default category which is handled separately)
        for cat in source_categories:
            assert cat in order_set, (
                f"{cat} missing from SERVER_CATEGORY_ORDER"
            )

    def test_client_order_has_default_category(self):
        """Client order includes the default category."""
        assert DEFAULT_CATEGORY in CLIENT_CATEGORY_ORDER

    def test_server_order_has_default_category(self):
        """Server order includes the default category."""
        assert DEFAULT_CATEGORY in SERVER_CATEGORY_ORDER


class TestNoiseAndTestPatterns:
    """Tests for filtering pattern constants."""

    def test_noise_patterns_are_strings(self):
        """All noise patterns are strings for simple 'in' check."""
        for pattern in MAP_NOISE_PATTERNS:
            assert isinstance(pattern, str)

    def test_test_patterns_are_strings(self):
        """All test patterns are strings for simple 'in' check."""
        for pattern in TEST_PATTERNS:
            assert isinstance(pattern, str)

    def test_noise_patterns_include_common_api_details(self):
        """Noise patterns cover Method, Property, Constructor."""
        assert "Method:" in MAP_NOISE_PATTERNS
        assert "Property:" in MAP_NOISE_PATTERNS
        assert "Constructor:" in MAP_NOISE_PATTERNS

    def test_test_patterns_cover_common_test_indicators(self):
        """Test patterns cover _test, test/, and Test."""
        assert "_test" in TEST_PATTERNS
        assert "test/" in TEST_PATTERNS
        assert "Test" in TEST_PATTERNS


class TestSplitFile:
    """Tests for split_file function."""

    def test_ignores_headers_inside_code_blocks(self, tmp_path):
        """Section headers inside markdown code blocks should be ignored.

        This is a regression test for the bug where llms-client-full.txt
        was only 10KB because split_file matched an example header inside
        a code block instead of the real Client API Reference section.
        """
        # Create test file with header in code block AND a real header
        content = """\
# Project Documentation

Here is an example of what the generated index.md looks like:

```markdown
# Client API Reference

## Libraries

- [example_widget](example_widget/overview.md)
```

Some more project documentation here.

# Client API Reference

This is the REAL client API documentation.

- [RealWidget](https://example.com/reference/client_api/widget/RealWidget/overview.md)
- [AnotherWidget](https://example.com/reference/client_api/widget/AnotherWidget/overview.md)

Lots more content here that should be in the full file.
This represents the actual 1.5MB of Dart documentation.
"""
        source_file = tmp_path / "llms-full.txt"
        source_file.write_text(content)

        sections = {
            "Project Documentation": "llms-project.txt",
            "Client API Reference": "llms-client.txt",
        }

        split_file(str(source_file), sections, is_map=False)

        # Read the generated client file
        client_file = tmp_path / "llms-client.txt"
        assert client_file.exists(), "Client file should be created"

        client_content = client_file.read_text()

        # The client file should contain the REAL content, not the example
        assert "This is the REAL client API documentation" in client_content
        assert "RealWidget" in client_content
        assert "Lots more content here" in client_content

        # It should NOT contain the example content or project docs
        assert "example_widget" not in client_content
        assert "Some more project documentation" not in client_content

    def test_server_map_ignores_headers_inside_code_blocks(self, tmp_path):
        """Server map generation should skip headers inside code blocks.

        This is a regression test for the bug where llms-server.txt was
        nearly empty because clean_map_content found an example header
        inside a code block instead of the real Server API section.

        The actual bug: llms-full.txt has '# Server API' inside a code block,
        followed immediately by '### Client API'. clean_map_content() finds
        the code block header first, then finds '# Client API' as the end
        marker, extracting only ~34 bytes of example content.
        """
        # Create llms.txt (map source) with minimal server section
        map_content = """\
# Project Documentation

Some project docs.

# Server API Reference

- [Server API](reference/server_api.md)

# Client API Reference

- [Client API](reference/client_api/index.md)
"""
        map_file = tmp_path / "llms.txt"
        map_file.write_text(map_content)

        # Create llms-full.txt matching the real structure:
        # 1. Code block with '# Server API' example
        # 2. Followed by '### Client API' (matches '# Client API' search)
        # 3. Later: real '# Server API' section with actual content
        full_content = """\
# Project Documentation

Here is the handler file:

```markdown
# Server API

::: soliplex
```

### Client API (Dart/Flutter)

More project documentation.

# Server API Reference

# Server API

## `RealClass`

This is real server API documentation.

Source code in `src/soliplex/config.py`

## `AnotherClass`

More real content.

Source code in `src/soliplex/models.py`

# Client API Reference

Client stuff here.
"""
        full_file = tmp_path / "llms-full.txt"
        full_file.write_text(full_content)

        sections = {
            "Project Documentation": "llms-project.txt",
            "Server API Reference": "llms-server.txt",
            "Client API Reference": "llms-client.txt",
        }

        split_file(str(map_file), sections, is_map=True)

        # Read the generated server map
        server_map = tmp_path / "llms-server.txt"
        assert server_map.exists(), "Server map should be created"

        server_content = server_map.read_text()

        # The server map should contain categorized items from REAL content
        assert "RealClass" in server_content, (
            f"Missing RealClass in: {server_content}"
        )
        assert "AnotherClass" in server_content
        assert "Configuration" in server_content or "Models" in server_content

        # It should NOT contain the example mkdocstrings directive
        assert "::: soliplex" not in server_content
