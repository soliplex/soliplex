import dataclasses

import pytest

from soliplex import monty_capabilities

# ---- Helpers ---------------------------------------------------------------


@dataclasses.dataclass
class FakeSkillConfig:
    """Minimal stand-in for ``config.SkillConfig``."""

    name: str
    metadata: dict | None = None


def _make_skills(**kwargs):
    """Build a skill_configs dict from keyword arguments.

    Each keyword maps a skill name to its metadata dict (or ``None``).
    """
    return {
        name: FakeSkillConfig(name=name, metadata=meta)
        for name, meta in kwargs.items()
    }


# ---- parse_monty_version ---------------------------------------------------


class TestParseMontyVersion:
    @pytest.mark.parametrize("header", [None, "", "  "])
    def test_absent_or_empty(self, header):
        assert monty_capabilities.parse_monty_version(header) is None

    @pytest.mark.parametrize("header", ["abc", "1.2", "v1", "🚀"])
    def test_invalid(self, header):
        assert monty_capabilities.parse_monty_version(header) is None

    def test_valid_integer(self):
        assert monty_capabilities.parse_monty_version("1") == 1

    def test_valid_with_whitespace(self):
        assert monty_capabilities.parse_monty_version("  2  ") == 2

    def test_zero(self):
        assert monty_capabilities.parse_monty_version("0") == 0

    def test_negative(self):
        assert monty_capabilities.parse_monty_version("-1") == -1


# ---- filter_skill_configs --------------------------------------------------


class TestFilterSkillConfigs:
    def _skills(self):
        return _make_skills(
            **{
                "math-solver": None,
                "soliplex-api": {"foo": "bar"},
                "monty-df": {"generated": "true", "category": "df"},
                "monty-chart": {"generated": "true", "category": "chart"},
            }
        )

    # -- client version sufficient -------------------------------------------

    def test_matching_version_includes_all(self):
        skills = self._skills()
        result = monty_capabilities.filter_skill_configs(
            skills,
            monty_capabilities.EXPECTED_BRIDGE_VERSION,
        )
        assert set(result) == set(skills)

    def test_higher_version_includes_all(self):
        skills = self._skills()
        result = monty_capabilities.filter_skill_configs(
            skills,
            monty_capabilities.EXPECTED_BRIDGE_VERSION + 1,
        )
        assert set(result) == set(skills)

    # -- client version insufficient -----------------------------------------

    def test_none_strips_monty(self):
        skills = self._skills()
        result = monty_capabilities.filter_skill_configs(skills, None)
        assert set(result) == {"math-solver", "soliplex-api"}

    def test_lower_version_strips_monty(self):
        skills = self._skills()
        result = monty_capabilities.filter_skill_configs(
            skills,
            monty_capabilities.EXPECTED_BRIDGE_VERSION - 1,
        )
        assert set(result) == {"math-solver", "soliplex-api"}

    def test_zero_version_strips_monty(self):
        skills = self._skills()
        result = monty_capabilities.filter_skill_configs(skills, 0)
        assert set(result) == {"math-solver", "soliplex-api"}

    # -- edge cases ----------------------------------------------------------

    def test_empty_skills(self):
        result = monty_capabilities.filter_skill_configs({}, None)
        assert result == {}

    def test_empty_skills_with_version(self):
        result = monty_capabilities.filter_skill_configs(
            {},
            monty_capabilities.EXPECTED_BRIDGE_VERSION,
        )
        assert result == {}

    def test_no_monty_skills_passthrough(self):
        skills = _make_skills(
            **{
                "math-solver": None,
                "soliplex-api": {"foo": "bar"},
            }
        )
        result = monty_capabilities.filter_skill_configs(skills, None)
        assert set(result) == {"math-solver", "soliplex-api"}

    def test_only_monty_skills_stripped(self):
        skills = _make_skills(
            **{
                "monty-df": {"generated": "true", "category": "df"},
            }
        )
        result = monty_capabilities.filter_skill_configs(skills, None)
        assert result == {}

    def test_metadata_none_passes_through(self):
        """Skills with metadata=None are never monty skills."""
        skills = _make_skills(**{"orphan": None})
        result = monty_capabilities.filter_skill_configs(skills, None)
        assert set(result) == {"orphan"}

    def test_generated_false_passes_through(self):
        """Skills with generated != 'true' are not filtered."""
        skills = _make_skills(
            **{"custom": {"generated": "false", "category": "x"}}
        )
        result = monty_capabilities.filter_skill_configs(skills, None)
        assert set(result) == {"custom"}


# ---- module constants ------------------------------------------------------


def test_expected_bridge_version_is_positive():
    assert monty_capabilities.EXPECTED_BRIDGE_VERSION >= 1


def test_header_name():
    assert monty_capabilities.HEADER_NAME == "X-Monty-Version"
