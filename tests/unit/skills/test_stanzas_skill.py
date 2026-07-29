"""Guard the invariants of the 'stanzas' example filesystem skill.

The skill promises byte-exact quoting and addressing by section and stanza
number, and it derives every structural fact from the poem files
themselves. Nothing in the skill loader checks any of that, so the
failures are silent: metadata leaking into the verse makes the agent quote
frontmatter as poetry, and a miscount makes it cite a range that does not
exist.

The expected counts below are written out deliberately. Asserting known
values is a test's job -- it was shipping those same numbers as data, in
an index beside the poems, that made them a maintenance liability.
"""

import pathlib
import subprocess
import sys

import pytest
from haiku.skills import discovery as hs_discovery
from skills_ref import validator as skill_validator

# 'tests/unit/skills/test_stanzas_skill.py' -> parents[3] is the repo root.
_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
_SKILL_ROOT = _REPO_ROOT / "example" / "skills" / "stanzas"
_SCRIPT = _SKILL_ROOT / "scripts" / "poem.py"

# 'The Hunting of the Snark', by section number.
_SNARK_STANZAS = [22, 21, 14, 18, 29, 18, 10, 9]
_LONGEST_FIT = 5

# Poems with no '##' headings: (poem, stanza count).
_UNSECTIONED = [("jabberwocky", 7), ("cloths of heaven", 1)]


@pytest.fixture
def skill_root():
    return _SKILL_ROOT


def _run_poem(*arguments):
    """Run 'poem.py' the way the skill's 'run_script' tool would."""
    completed = subprocess.run(
        [sys.executable, str(_SCRIPT), *arguments],
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout.splitlines()


def _verse(lines):
    """Return the lines after the '---' separator."""
    return lines[lines.index("---") + 1 :]


def test_skill_metadata_passes_the_reference_validator(skill_root):
    errors = skill_validator.validate(skill_root)

    assert errors == []


def test_every_discovered_resource_is_a_catalogued_poem(skill_root):
    resources = hs_discovery.discover_resources(skill_root)

    lines = _run_poem("list")

    assert lines[0] == f"POEMS: {len(resources)}"
    assert [line.split(" | ")[0] for line in lines[1:]] == sorted(
        pathlib.Path(path).stem for path in resources
    )


@pytest.mark.parametrize("poem,expected", _UNSECTIONED)
def test_unsectioned_poem_stanza_total(poem, expected):
    lines = _run_poem("sections", poem)

    assert "SECTIONS: 0 (this poem has no sections)" in lines
    assert f"STANZAS: {expected} (1-{expected})" in lines


def test_sectioned_poem_reports_every_section_and_its_size(skill_root):
    expected = [
        f"{number}  {name}  (stanzas 1-{count})"
        for number, (name, count) in enumerate(
            zip(_snark_headings(skill_root), _SNARK_STANZAS, strict=True),
            start=1,
        )
    ]

    lines = _run_poem("sections", "snark")

    assert f"SECTIONS: {len(_SNARK_STANZAS)}" in lines
    assert lines[-len(expected) :] == expected


def _snark_headings(skill_root):
    """The '## ' headings, read straight from the poem file."""
    path = skill_root / "resources" / "the_hunting_of_the_snark.md"
    return [
        line.removeprefix("## ").strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.startswith("## ")
    ]


@pytest.mark.parametrize("poem", ["jabberwocky", "cloths of heaven"])
def test_frontmatter_is_never_quoted_as_verse(poem):
    lines = _run_poem("stanza", poem, "--stanza", "1")

    assert "---" not in _verse(lines)
    assert [line for line in _verse(lines) if line.startswith("title:")] == []


def test_frontmatter_does_not_hide_a_sectioned_poem():
    lines = _run_poem("stanza", "snark", "--section", "1", "--stanza", "1")

    assert "SECTION: 1 of 8 -- Fit the First: THE LANDING" in lines
    assert "---" not in _verse(lines)


def test_last_stanza_of_a_section_is_addressable():
    last = len(_SNARK_STANZAS)

    lines = _run_poem(
        "stanza",
        "snark",
        "--section",
        str(last),
        "--stanza",
        str(_SNARK_STANZAS[-1]),
    )

    assert f"STANZA: {_SNARK_STANZAS[-1]} of {_SNARK_STANZAS[-1]}" in lines


def test_one_past_the_last_stanza_reports_not_found():
    last = len(_SNARK_STANZAS)

    lines = _run_poem(
        "stanza",
        "snark",
        "--section",
        str(last),
        "--stanza",
        str(_SNARK_STANZAS[-1] + 1),
    )

    assert lines[0].startswith("NOT FOUND: ")
    assert f"(1-{_SNARK_STANZAS[-1]})" in lines[0]


def test_quoted_stanza_is_byte_identical_to_the_poem_file(skill_root):
    source = (
        skill_root / "resources" / "the_hunting_of_the_snark.md"
    ).read_text(encoding="utf-8")

    lines = _run_poem("stanza", "snark", "--section", "5", "--stanza", "12")

    assert "\n".join(_verse(lines)) in source


def test_quoted_stanza_keeps_its_leading_whitespace():
    lines = _run_poem("stanza", "snark", "--section", "5", "--stanza", "12")

    assert [line.startswith(" ") for line in _verse(lines)] == [
        False,
        True,
        True,
        True,
    ]


def test_an_overlong_section_is_refused_rather_than_quoted():
    longest = _SNARK_STANZAS[_LONGEST_FIT - 1]

    lines = _run_poem("section", "snark", "--section", str(_LONGEST_FIT))

    assert lines[0].startswith("TOO LONG: ")
    assert f"1-{longest}" in lines[0]


def test_a_short_section_is_quoted_with_stanza_breaks_intact():
    lines = _run_poem("section", "snark", "--section", "8")

    assert _verse(lines).count("") == _SNARK_STANZAS[-1] - 1


@pytest.mark.parametrize(
    "poem",
    ["He Wishes for the Cloths of Heaven", "yeats", "cloths of heaven"],
)
def test_a_poem_resolves_by_alternate_title_and_by_poet(poem):
    lines = _run_poem("stanza", poem, "--stanza", "1")

    assert lines[0] == "POEM: Aedh Wishes for the Cloths of Heaven"


def test_a_poet_with_two_poems_is_reported_as_ambiguous():
    lines = _run_poem("stanza", "Lewis Carroll", "--stanza", "1")

    assert lines[0].startswith("NOT FOUND: ")
    assert "matches more than one poem" in lines[0]
    assert len(lines) == 3


def test_an_unknown_poem_reports_not_found_with_the_catalog(skill_root):
    resources = hs_discovery.discover_resources(skill_root)

    lines = _run_poem("stanza", "clerihew", "--stanza", "1")

    assert lines[0].startswith("NOT FOUND: no bundled poem matches ")
    assert len(lines) == 1 + len(resources)


def test_the_poet_and_year_are_reported_from_the_poem_file():
    lines = _run_poem("stanza", "jabberwocky", "--stanza", "1")

    assert "POET: Lewis Carroll" in lines
    assert [line for line in lines if line.startswith("YEAR: ")] != []
