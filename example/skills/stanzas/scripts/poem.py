#!/usr/bin/env python3
"""Locate sections and stanzas in the poems bundled with this skill.

Answers structural questions deterministically so the calling agent never
has to count stanzas or reproduce long passages from memory.

Every command exits 0, including for "not found": a non-zero exit is
reported to the agent as a tool malfunction, which provokes retry loops,
whereas a 'NOT FOUND:' line on stdout is directly quotable.

Trust boundary: skill scripts run unsandboxed, as the server user. This
one reads the skill's own resource files and writes nothing.
"""

import argparse
import pathlib
import re
import sys
import unicodedata

import yaml

SKILL_ROOT = pathlib.Path(__file__).resolve().parent.parent
RESOURCES = SKILL_ROOT / "resources"
MAX_QUOTED_LINES = 40


def _norm(text):
    """Casefold and strip punctuation, for forgiving matching."""
    folded = unicodedata.normalize("NFKC", str(text)).casefold()
    collapsed = re.sub(r"[^0-9a-z]+", " ", folded).strip()
    return re.sub(r"^the\s+", "", collapsed)


def _split_frontmatter(text):
    """Return (metadata, body) for a file that may open with '---'.

    The metadata block is NOT part of the poem: keeping it out of 'body' is
    what stops it being counted and quoted as the first stanza.
    """
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    metadata = yaml.safe_load(parts[1])
    if not isinstance(metadata, dict):
        return {}, text
    return metadata, parts[2].lstrip("\n")


def _load_catalog():
    """Build the catalog from each poem file's own frontmatter.

    The poem files are the single source of truth: there is no index to
    drift out of step with them. A poem's id is its filename stem.
    """
    entries = []
    for path in sorted(RESOURCES.glob("*.md")):
        metadata, body = _split_frontmatter(path.read_text(encoding="utf-8"))
        entries.append(
            {
                "id": path.stem,
                "title": metadata.get("title", path.stem),
                "poet": metadata.get("poet", "unknown"),
                "year": metadata.get("year"),
                "alternate_title": metadata.get("alternate_title"),
                "file": f"resources/{path.name}",
                "sections": _parse_poem(body),
            }
        )
    return sorted(entries, key=lambda entry: entry["title"])


def _match_keys(entry):
    """The names a request may use to reach this poem."""
    keys = [entry["id"], entry["title"], entry["poet"]]
    if entry["alternate_title"]:
        keys.append(entry["alternate_title"])
    return [_norm(key) for key in keys]


def _find_poem(catalog, query):
    """Return (entry, candidates): one match, or None plus the near misses."""
    wanted = _norm(query)
    if not wanted:
        return None, catalog

    exact = [
        entry
        for entry in catalog
        if any(wanted == key for key in _match_keys(entry))
    ]
    if len(exact) == 1:
        return exact[0], []

    tokens = set(wanted.split())
    loose = []
    for entry in catalog:
        if any(
            wanted in key or tokens <= set(key.split())
            for key in _match_keys(entry)
        ):
            loose.append(entry)
    if len(loose) == 1:
        return loose[0], []
    return None, loose or catalog


def _parse_poem(text):
    """Split a poem into [(section_name_or_None, [[line, ...], ...]), ...].

    A stanza is a run of non-blank lines; one or more blank lines in a row
    act as a single separator. Heading lines never join a stanza.
    """
    sections = []
    stanzas = None
    stanza = None

    def _start_section(name):
        nonlocal stanzas, stanza
        stanzas = []
        stanza = None
        sections.append((name, stanzas))

    for line in text.splitlines():
        if line.startswith("## "):
            _start_section(line[3:].strip())
            continue
        if line.startswith("# "):
            continue
        if not line.strip():
            stanza = None
            continue
        if stanzas is None:
            _start_section(None)
        if stanza is None:
            stanza = []
            stanzas.append(stanza)
        stanza.append(line)

    return sections


def _poem_sections(entry):
    return entry["sections"]


def _stanza_total(entry):
    return sum(len(stanzas) for _name, stanzas in entry["sections"])


def _section_total(entry):
    """Sections proper: an unsectioned poem has one anonymous section."""
    if entry["sections"] and entry["sections"][0][0] is None:
        return 0
    return len(entry["sections"])


def _resolve_section(sections, spec):
    """Return (number, name, stanzas), or None plus ambiguous candidates."""
    if spec is None:
        return None, []
    if spec.strip().isdigit():
        number = int(spec.strip())
        if 1 <= number <= len(sections):
            name, stanzas = sections[number - 1]
            return (number, name, stanzas), []
        return None, []

    wanted = _norm(spec)
    tokens = set(wanted.split())
    matches = []
    for number, (name, stanzas) in enumerate(sections, start=1):
        hay = _norm(name or "")
        if wanted == hay or wanted in hay or tokens <= set(hay.split()):
            matches.append((number, name, stanzas))
    if len(matches) == 1:
        return matches[0], []
    return None, matches


def _header(entry):
    lines = [f"POEM: {entry['title']}", f"POET: {entry['poet']}"]
    if entry["year"]:
        lines.append(f"YEAR: {entry['year']}")
    if entry["alternate_title"]:
        lines.append(f"ALSO TITLED: {entry['alternate_title']}")
    return lines


def _section_lines(sections):
    lines = []
    for number, (name, stanzas) in enumerate(sections, start=1):
        lines.append(f"{number}  {name}  (stanzas 1-{len(stanzas)})")
    return lines


def _emit(lines):
    sys.stdout.write("\n".join(lines) + "\n")


def _no_poem(query, candidates, catalog):
    """Report an unmatched or ambiguous poem name, then list the choices."""
    if 0 < len(candidates) < len(catalog):
        detail = f'"{query}" matches more than one poem. Did you mean:'
    else:
        detail = f'no bundled poem matches "{query}". Available poems:'
    _emit(
        [
            f"NOT FOUND: {detail}",
            *[
                f"- {entry['id']}: {entry['title']} ({entry['poet']})"
                for entry in candidates
            ],
        ]
    )


def _no_section(spec, sections, candidates):
    total = len(sections)
    if candidates:
        detail = f'section "{spec}" matches more than one section.'
    else:
        detail = f'section "{spec}" does not exist.'
    _emit(
        [
            f"NOT FOUND: {detail} This poem has {total} sections (1-{total}):",
            *_section_lines(sections),
        ]
    )


def _need_section(sections):
    total = len(sections)
    _emit(
        [
            f"NOT FOUND: this poem has {total} sections, so --section is "
            "required. Stanza numbers restart at 1 in every section.",
            *_section_lines(sections),
        ]
    )


def _cite(number, name, index, total):
    if name is None:
        return f"STANZA: {index} of {total}"
    return f"STANZA: {index} of {total} (section {number}: {name})"


def cmd_list(_args, catalog):
    """List the anthology, with counts derived from the poem files."""
    _emit(
        [f"POEMS: {len(catalog)}"]
        + [
            "{id} | {title} | {poet}{year} | sections {sections} | "
            "stanzas {stanzas}".format(
                id=entry["id"],
                title=entry["title"],
                poet=entry["poet"],
                year=f", {entry['year']}" if entry["year"] else "",
                sections=_section_total(entry),
                stanzas=_stanza_total(entry),
            )
            for entry in catalog
        ]
    )


def cmd_sections(args, catalog):
    entry, candidates = _find_poem(catalog, args.poem)
    if entry is None:
        return _no_poem(args.poem, candidates, catalog)

    sections = _poem_sections(entry)
    if sections and sections[0][0] is None:
        total = len(sections[0][1])
        _emit(
            _header(entry)
            + [
                "SECTIONS: 0 (this poem has no sections)",
                f"STANZAS: {total} (1-{total})",
            ]
        )
        return None

    _emit(
        _header(entry)
        + [f"SECTIONS: {len(sections)}"]
        + _section_lines(sections)
    )
    return None


def cmd_section(args, catalog):
    entry, candidates = _find_poem(catalog, args.poem)
    if entry is None:
        return _no_poem(args.poem, candidates, catalog)

    sections = _poem_sections(entry)
    sectioned = sections[0][0] is not None
    if sectioned:
        if args.section is None:
            return _need_section(sections)
        found, ambiguous = _resolve_section(sections, args.section)
        if found is None:
            return _no_section(args.section, sections, ambiguous)
        number, name, stanzas = found
    else:
        number, name, stanzas = 1, None, sections[0][1]

    verse = []
    for stanza in stanzas:
        if verse:
            verse.append("")
        verse.extend(stanza)
    count = sum(len(stanza) for stanza in stanzas)
    label = name or entry["title"]
    if count > MAX_QUOTED_LINES:
        _emit(
            [
                f"TOO LONG: {label} has {len(stanzas)} stanzas "
                f"({count} lines). Ask for one stanza, numbered "
                f"1-{len(stanzas)}.",
            ]
        )
        return None

    head = _header(entry)
    if name is not None:
        head.append(f"SECTION: {number} of {len(sections)} -- {name}")
    head += [f"STANZAS: {len(stanzas)}", f"LINES: {count}", "---"]
    _emit(head + verse)
    return None


def cmd_stanza(args, catalog):
    entry, candidates = _find_poem(catalog, args.poem)
    if entry is None:
        return _no_poem(args.poem, candidates, catalog)

    sections = _poem_sections(entry)
    sectioned = sections[0][0] is not None
    if sectioned:
        if args.section is None:
            return _need_section(sections)
        found, ambiguous = _resolve_section(sections, args.section)
        if found is None:
            return _no_section(args.section, sections, ambiguous)
        number, name, stanzas = found
    else:
        number, name, stanzas = 1, None, sections[0][1]

    total = len(stanzas)
    where = f" in section {number} ({name})" if name else ""
    if not 1 <= args.stanza <= total:
        _emit(
            [
                f"NOT FOUND: stanza {args.stanza}{where}. "
                f"{entry['title']} has {total} stanzas there (1-{total})."
            ]
        )
        return None

    verse = stanzas[args.stanza - 1]
    head = _header(entry)
    if name is not None:
        head.append(f"SECTION: {number} of {len(sections)} -- {name}")
    head += [
        f"STANZA: {args.stanza} of {total}",
        f"LINES: {len(verse)}",
        "---",
    ]
    _emit(head + verse)
    return None


def cmd_search(args, catalog):
    entry, candidates = _find_poem(catalog, args.poem)
    if entry is None:
        return _no_poem(args.poem, candidates, catalog)

    sections = _poem_sections(entry)
    needle = _norm(args.query)
    hits = []
    for number, (name, stanzas) in enumerate(sections, start=1):
        for index, stanza in enumerate(stanzas, start=1):
            haystack = _norm(" ".join(stanza))
            if needle and needle in haystack:
                hits.append((number, name, index, len(stanzas), stanza))

    head = _header(entry) + [
        f'SEARCH: "{args.query}"',
        f"MATCHES: {len(hits)}",
    ]
    if not hits:
        _emit(head + ["NOT FOUND: no stanza contains that text."])
        return None

    citations = [
        "- " + _cite(number, name, index, total).removeprefix("STANZA: ")
        for number, name, index, total in [hit[:4] for hit in hits]
    ]
    number, name, index, total, stanza = hits[0]
    _emit(
        head + citations + [_cite(number, name, index, total), "---"] + stanza
    )
    return None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="list the bundled poems")

    for name, help_text in [
        ("sections", "list a poem's sections and their stanza counts"),
        ("section", "quote one whole section, if it is short enough"),
        ("stanza", "quote one stanza"),
        ("search", "find which stanzas contain some text"),
    ]:
        sub = subparsers.add_parser(name, help=help_text)
        sub.add_argument("poem", help="poem id, title, or alias")
        if name in {"section", "stanza"}:
            sub.add_argument(
                "--section",
                help="section number, or part of its heading",
            )
        if name == "stanza":
            sub.add_argument(
                "--stanza",
                type=int,
                required=True,
                help="1-based stanza number within the section",
            )
        if name == "search":
            sub.add_argument("query", help="text to look for")

    args = parser.parse_args(argv)
    handlers = {
        "list": cmd_list,
        "sections": cmd_sections,
        "section": cmd_section,
        "stanza": cmd_stanza,
        "search": cmd_search,
    }
    handlers[args.command](args, _load_catalog())
    return 0


if __name__ == "__main__":
    sys.exit(main())
