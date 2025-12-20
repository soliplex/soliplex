"""Tests for federate_llms_txt.py."""

import pytest

from llms_constants import (
    CLIENT_CATEGORY_ORDER,
    CLIENT_PATH_KEYWORDS,
    DEFAULT_CATEGORY,
    MAP_NOISE_PATTERNS,
    PATTERNS,
    SERVER_CATEGORY_ORDER,
    SERVER_SOURCE_CATEGORIES,
    TEST_PATTERNS,
)
from federate_llms_txt import (
    categorize_path,
    categorize_server_item,
    clean_map_content,
    localize_urls,
    restructure_client_map,
    restructure_server_map,
)


class TestCategorizeServerItem:
    """Tests for server API categorization."""

    def test_config_file_categorized(self):
        """Items from config.py go to Configuration."""
        category = categorize_server_item("SampleConfig", "src/soliplex/config.py")
        assert category == "Configuration"

    def test_models_file_categorized(self):
        """Items from models.py go to Models & Data."""
        category = categorize_server_item("SampleModel", "src/soliplex/models.py")
        assert category == "Models & Data"

    def test_agents_file_categorized(self):
        """Items from agents.py go to Agents."""
        category = categorize_server_item("get_agent", "src/soliplex/agents.py")
        assert category == "Agents"

    def test_tools_file_categorized(self):
        """Items from tools.py go to Tools."""
        category = categorize_server_item("search_documents", "src/soliplex/tools.py")
        assert category == "Tools"

    def test_cli_file_categorized(self):
        """Items from cli.py go to CLI Commands."""
        category = categorize_server_item("serve", "src/soliplex/cli.py")
        assert category == "CLI Commands"

    def test_views_directory_categorized(self):
        """Items from views/ go to API Endpoints."""
        category = categorize_server_item("RoomView", "src/soliplex/views/rooms.py")
        assert category == "API Endpoints"

    def test_agui_file_categorized(self):
        """Items with agui in path (not under views/) go to AG-UI Protocol."""
        # Note: views/ matches first, so agui under views/ goes to API Endpoints
        category = categorize_server_item("AGUIEvent", "src/soliplex/agui/events.py")
        assert category == "AG-UI Protocol"

    def test_unknown_source_defaults(self):
        """Unknown source files get default category."""
        category = categorize_server_item("Mystery", "src/soliplex/unknown.py")
        assert category == DEFAULT_CATEGORY

    def test_none_source_defaults(self):
        """None source gets default category."""
        category = categorize_server_item("Orphan", None)
        assert category == DEFAULT_CATEGORY


class TestCategorizePath:
    """Tests for client API path categorization."""

    def test_agui_events_categorized(self):
        """agui_events path goes to AG-UI Protocol."""
        category = categorize_path("agui_events")
        assert category == "AG-UI Protocol"

    def test_widget_registry_categorized(self):
        """widget_registry path goes to Core Architecture."""
        category = categorize_path("widget_registry")
        assert category == "Core Architecture"

    def test_service_keyword_categorized(self):
        """Paths with 'service' go to Services & State."""
        category = categorize_path("auth_service")
        assert category == "Services & State"

    def test_notifier_keyword_categorized(self):
        """Paths with 'notifier' go to Services & State."""
        category = categorize_path("theme_notifier")
        assert category == "Services & State"

    def test_model_keyword_categorized(self):
        """Paths with 'model' go to Models & Data."""
        category = categorize_path("user_model")
        assert category == "Models & Data"

    def test_network_keyword_categorized(self):
        """Paths with 'network' go to Network & API."""
        category = categorize_path("network_client")
        assert category == "Network & API"

    def test_widget_keyword_categorized(self):
        """Paths with 'widget' go to UI Components."""
        category = categorize_path("custom_widget")
        assert category == "UI Components"

    def test_auth_keyword_categorized(self):
        """Paths with 'auth' (not containing 'manager') go to Authentication."""
        # Note: 'manager' matches first for 'auth_manager', so use 'auth_provider'
        category = categorize_path("auth_provider")
        assert category == "Authentication"

    def test_unknown_path_defaults(self):
        """Unknown paths get default category."""
        category = categorize_path("random_stuff")
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

        config_idx = next(i for i, l in enumerate(lines) if "Configuration" in l)
        model_idx = next(i for i, l in enumerate(lines) if "Models & Data" in l)

        # Configuration should come before Models in SERVER_CATEGORY_ORDER
        assert config_idx < model_idx


class TestRestructureClientMap:
    """Tests for client map restructuring."""

    def test_filters_noise_patterns(self):
        """Removes Method/Property/Constructor lines."""
        content = """
- [SampleWidget](https://example.com/reference/client_api/widget/SampleWidget/overview.md)
- [Method: doSomething](https://example.com/reference/client_api/widget/SampleWidget/method.md)
- [Property: name](https://example.com/reference/client_api/widget/SampleWidget/property.md)
"""
        result = restructure_client_map(content)

        assert "SampleWidget" in result
        assert "Method:" not in result
        assert "Property:" not in result

    def test_filters_test_files(self):
        """Removes test file entries."""
        content = """
- [RealWidget](https://example.com/reference/client_api/widget/RealWidget/overview.md)
- [TestWidget](https://example.com/reference/client_api/widget_test/TestWidget/overview.md)
- [SomeTest](https://example.com/reference/client_api/test/SomeTest/overview.md)
"""
        result = restructure_client_map(content)

        assert "RealWidget" in result
        assert "TestWidget" not in result
        assert "SomeTest" not in result

    def test_removes_overview_prefix(self):
        """Simplifies 'Overview for X' to 'X'."""
        content = """
- [Overview for SampleWidget](https://example.com/reference/client_api/widget/SampleWidget/overview.md)
"""
        result = restructure_client_map(content)

        # Should have SampleWidget without "Overview for" prefix
        assert "Overview for" not in result

    def test_categorizes_by_path(self):
        """Groups items by semantic category based on path."""
        content = """
- [AuthService](https://example.com/reference/client_api/auth_service/AuthService/overview.md)
- [MyWidget](https://example.com/reference/client_api/widget/MyWidget/overview.md)
"""
        result = restructure_client_map(content)

        assert "## Authentication" in result or "## Services & State" in result
        assert "## UI Components" in result


class TestCleanMapContent:
    """Tests for map content cleaning."""

    def test_delegates_client_to_restructure(self):
        """Client API content goes through restructure_client_map."""
        content = "- [Method: test](url)"
        result = clean_map_content(content, "Client API Reference")

        # Method lines should be filtered
        assert "Method:" not in result

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

    def test_local_mode_replaces_urls(self):
        """Local mode replaces remote URLs with local paths."""
        content = "Visit https://soliplex.github.io/soliplex/page.html"
        result = localize_urls(content, "/site", "/Users/me/site/")

        assert "https://soliplex.github.io/soliplex/" not in result
        assert "/Users/me/site/" in result

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
            assert cat in order_set, f"{cat} missing from SERVER_CATEGORY_ORDER"

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
