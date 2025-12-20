"""Tests for validate_llms_strategy.py."""

import pytest

from llms_constants import DOMAINS, PATTERNS
from validate_llms_strategy import (
    check_context_efficiency,
    check_file_existence,
    check_link_integrity,
    check_map_content,
    estimate_tokens,
)


class TestEstimateTokens:
    """Tests for token estimation."""

    def test_empty_string(self):
        """Empty string has 0 tokens."""
        assert estimate_tokens("") == 0

    def test_short_string(self):
        """Short string estimation (chars // 4)."""
        assert estimate_tokens("hello") == 1  # 5 // 4 = 1

    def test_long_string(self):
        """Longer string estimation."""
        text = "a" * 100
        assert estimate_tokens(text) == 25  # 100 // 4 = 25


class TestCheckFileExistence:
    """Tests for file existence checks."""

    def test_missing_root_file(self, tmp_path):
        """Reports error when llms.txt is missing."""
        import validate_llms_strategy

        original_site_dir = validate_llms_strategy.SITE_DIR
        try:
            validate_llms_strategy.SITE_DIR = tmp_path / "site"
            validate_llms_strategy.SITE_DIR.mkdir()

            errors, warnings = check_file_existence()
            assert any("llms.txt" in e for e in errors)
        finally:
            validate_llms_strategy.SITE_DIR = original_site_dir

    def test_all_files_exist(self, sample_site_with_domains):
        """No errors when all files exist."""
        import validate_llms_strategy

        original_site_dir = validate_llms_strategy.SITE_DIR
        try:
            validate_llms_strategy.SITE_DIR = sample_site_with_domains
            # Create root entry point
            (sample_site_with_domains / "llms.txt").write_text("# Root")

            errors, warnings = check_file_existence()
            assert len(errors) == 0
        finally:
            validate_llms_strategy.SITE_DIR = original_site_dir


class TestCheckContextEfficiency:
    """Tests for context efficiency validation."""

    def test_passes_when_within_threshold(self, sample_site_with_domains):
        """No errors when map/content ratio is within threshold."""
        import validate_llms_strategy

        original_site_dir = validate_llms_strategy.SITE_DIR
        try:
            validate_llms_strategy.SITE_DIR = sample_site_with_domains

            errors, metrics = check_context_efficiency()
            assert len(errors) == 0
            assert "project" in metrics
            assert "server" in metrics
            assert "client" in metrics
            assert "_total" in metrics
        finally:
            validate_llms_strategy.SITE_DIR = original_site_dir

    def test_fails_when_exceeds_threshold(self, tmp_path):
        """Reports error when map size exceeds threshold."""
        import validate_llms_strategy

        site = tmp_path / "site"
        site.mkdir()

        # Create map that's too large relative to content
        (site / "llms-project.txt").write_text("x" * 1000)
        (site / "llms-project-full.txt").write_text("y" * 1000)  # Same size = 100%

        original_site_dir = validate_llms_strategy.SITE_DIR
        try:
            validate_llms_strategy.SITE_DIR = site

            errors, metrics = check_context_efficiency()
            # Should have at least one error for project exceeding threshold
            project_errors = [e for e in errors if "project" in e]
            assert len(project_errors) > 0
        finally:
            validate_llms_strategy.SITE_DIR = original_site_dir

    def test_calculates_total_reduction(self, sample_site_with_domains):
        """Correctly calculates total reduction percentage."""
        import validate_llms_strategy

        original_site_dir = validate_llms_strategy.SITE_DIR
        try:
            validate_llms_strategy.SITE_DIR = sample_site_with_domains

            errors, metrics = check_context_efficiency()
            total = metrics["_total"]

            assert "reduction_pct" in total
            assert total["reduction_pct"] > 0
        finally:
            validate_llms_strategy.SITE_DIR = original_site_dir


class TestCheckLinkIntegrity:
    """Tests for link integrity validation."""

    def test_no_errors_for_external_links(self, sample_site_with_domains):
        """No errors when all links are external (https)."""
        import validate_llms_strategy

        original_site_dir = validate_llms_strategy.SITE_DIR
        try:
            validate_llms_strategy.SITE_DIR = sample_site_with_domains
            # Overwrite domain maps with only external links
            (sample_site_with_domains / "llms.txt").write_text(
                "# Root\n[Project](https://example.com/project.md)"
            )
            (sample_site_with_domains / "llms-project.txt").write_text(
                "# Project\n[Docs](https://example.com/docs)"
            )
            (sample_site_with_domains / "llms-server.txt").write_text(
                "# Server\n[API](https://example.com/api)"
            )
            (sample_site_with_domains / "llms-client.txt").write_text(
                "# Client\n[Widget](https://example.com/widget)"
            )

            errors, link_count = check_link_integrity()
            assert len(errors) == 0
            assert link_count > 0
        finally:
            validate_llms_strategy.SITE_DIR = original_site_dir

    def test_counts_links_correctly(self, sample_site_with_domains):
        """Correctly counts validated links."""
        import validate_llms_strategy

        original_site_dir = validate_llms_strategy.SITE_DIR
        try:
            validate_llms_strategy.SITE_DIR = sample_site_with_domains
            (sample_site_with_domains / "llms.txt").write_text(
                "# Root\n[A](https://a.com)\n[B](https://b.com)"
            )
            # Ensure domain maps have only external links
            (sample_site_with_domains / "llms-project.txt").write_text(
                "# Project\n[X](https://x.com)"
            )
            (sample_site_with_domains / "llms-server.txt").write_text(
                "# Server\n[Y](https://y.com)"
            )
            (sample_site_with_domains / "llms-client.txt").write_text(
                "# Client\n[Z](https://z.com)"
            )

            errors, link_count = check_link_integrity()
            # Should count links from root + domain maps
            assert link_count >= 2
        finally:
            validate_llms_strategy.SITE_DIR = original_site_dir

    def test_detects_broken_relative_links(self, sample_site_with_domains):
        """Reports errors for broken relative links."""
        import validate_llms_strategy

        original_site_dir = validate_llms_strategy.SITE_DIR
        try:
            validate_llms_strategy.SITE_DIR = sample_site_with_domains
            # Create a map with a relative link to a non-existent file
            (sample_site_with_domains / "llms.txt").write_text("# Root")
            (sample_site_with_domains / "llms-project.txt").write_text(
                "# Project\n[Missing](does-not-exist.md)"
            )
            (sample_site_with_domains / "llms-server.txt").write_text(
                "# Server\n[API](https://example.com)"
            )
            (sample_site_with_domains / "llms-client.txt").write_text(
                "# Client\n[Widget](https://example.com)"
            )

            errors, link_count = check_link_integrity()
            assert len(errors) > 0
            assert any("does-not-exist.md" in e for e in errors)
        finally:
            validate_llms_strategy.SITE_DIR = original_site_dir


class TestPatterns:
    """Tests for regex patterns from constants."""

    def test_markdown_link_pattern(self):
        """Markdown link pattern matches correctly."""
        import re

        pattern = re.compile(PATTERNS["markdown_link"])
        text = "[Click Here](https://example.com/page.html)"
        match = pattern.search(text)

        assert match is not None
        assert match.group(1) == "Click Here"
        assert match.group(2) == "https://example.com/page.html"

    def test_markdown_link_pattern_multiple(self):
        """Pattern finds all links in text."""
        import re

        pattern = re.compile(PATTERNS["markdown_link"])
        text = "[A](http://a.com) text [B](http://b.com)"
        matches = pattern.findall(text)

        assert len(matches) == 2
        assert matches[0] == ("A", "http://a.com")
        assert matches[1] == ("B", "http://b.com")


class TestDomainConfiguration:
    """Tests for domain configuration constants."""

    def test_all_domains_have_required_keys(self):
        """All domain configs have map, content, and threshold."""
        for domain, config in DOMAINS.items():
            assert "map" in config, f"{domain} missing 'map'"
            assert "content" in config, f"{domain} missing 'content'"
            assert "threshold" in config, f"{domain} missing 'threshold'"

    def test_thresholds_are_valid(self):
        """All thresholds are between 0 and 1."""
        for domain, config in DOMAINS.items():
            threshold = config["threshold"]
            assert 0 < threshold < 1, f"{domain} threshold {threshold} out of range"

    def test_filenames_follow_convention(self):
        """All filenames follow llms-*.txt convention."""
        for domain, config in DOMAINS.items():
            assert config["map"].startswith("llms-"), f"{domain} map name invalid"
            assert config["map"].endswith(".txt"), f"{domain} map extension invalid"
            assert config["content"].endswith("-full.txt"), f"{domain} content suffix"


class TestCheckMapContent:
    """Tests for map content validation."""

    def test_map_with_only_header_fails(self, tmp_path):
        """Map file with only a header should fail validation."""
        import validate_llms_strategy

        original_site_dir = validate_llms_strategy.SITE_DIR
        try:
            site_dir = tmp_path / "site"
            site_dir.mkdir()
            validate_llms_strategy.SITE_DIR = site_dir

            # Create map with only header (no categories)
            map_file = site_dir / "llms-server.txt"
            map_file.write_text(
                "# Soliplex - Server API Reference\n\n"
                "Navigate to specific modules below.\n"
            )

            # Create matching content file
            content_file = site_dir / "llms-server-full.txt"
            content_file.write_text("# Server API\n\n## `SomeClass`\n\nDocs here.")

            errors, _ = check_map_content()

            assert len(errors) > 0
            assert any("server" in e.lower() for e in errors)
        finally:
            validate_llms_strategy.SITE_DIR = original_site_dir

    def test_map_with_categories_passes(self, tmp_path):
        """Map file with category headers should pass validation."""
        import validate_llms_strategy

        original_site_dir = validate_llms_strategy.SITE_DIR
        try:
            site_dir = tmp_path / "site"
            site_dir.mkdir()
            validate_llms_strategy.SITE_DIR = site_dir

            # Create map with categories
            map_file = site_dir / "llms-server.txt"
            map_file.write_text(
                "# Soliplex - Server API Reference\n\n"
                "## Configuration\n"
                "- `ConfigClass`\n\n"
                "## Models\n"
                "- `ModelClass`\n"
            )

            # Create matching content file
            content_file = site_dir / "llms-server-full.txt"
            content_file.write_text("# Server API\n\n## `SomeClass`\n\nDocs here.")

            errors, _ = check_map_content()

            assert len(errors) == 0
        finally:
            validate_llms_strategy.SITE_DIR = original_site_dir
