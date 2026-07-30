---
name: stanzas
description: >-
  Answer questions about a poem: quote a stanza or section verbatim, count
  stanzas or lines, list sections, find which stanza mentions a word, explain
  what a stanza says, name the verse form, or report the poet and year. Use it
  whenever a question involves poetry, a poem, a poet, a verse, a stanza, a
  canto, or a fit. It works on a poem pasted into the conversation, and on a
  small bundled anthology of well-known poems: ask what it holds, or name a
  poem and it will say whether it has it. It quotes and analyses existing
  poems; it does not write new ones.
---

# Stanzas

Find sections and stanzas of poems, quote them exactly, and answer questions
about them. Quote only poems you are given or that this skill bundles. Do not
write new verse, and do not supply lines from memory.

## Your tools

`read_resource` reads a bundled poem file. Its `path` argument always
starts with `resources/`.

`run_script` runs a bundled script. Its `script` argument is always
`scripts/poem.py`, and its `arguments` argument is one string holding the
command line.

Prefer `scripts/poem.py`. It counts sections and stanzas for you and returns
the exact lines. Read a poem file yourself ONLY if the script fails twice.

## The bundled poems

Every bundled poem is one file under `resources/`, named `<id>.md` after the
id in the first column of `scripts/poem.py list`. Each one carries its own
title, poet and year at the top, between two `---` lines.

Run `scripts/poem.py list` to see the poems with their poets, years, and
section and stanza counts. Do that when you are asked what poems are
available, or when you cannot tell which poem is wanted.

You do not need to look first to fetch a stanza. Name the poem and the script
will find it: the title works, so does a distinctive word from it, and so does
the poet's name. If the name matches nothing, or matches more than one poem,
the script answers with the list of poems to choose from - so a single wrong
guess costs nothing.

## Definitions

METADATA BLOCK - if the text starts with a line of exactly three hyphens
(`---`), then everything from there through the next such line is metadata:
the title, poet and year. It is NOT verse. Never count it as a stanza and
never quote it. The poem begins after it. Bundled poems all start this way.

TITLE LINE - a line starting with a single `#` and a space, if the poem has
one. It is NOT a section and NOT a stanza. Never count it. Never quote it as a
stanza. Bundled poems have no title line; a pasted poem may.

SECTION - a line starting with exactly two hash marks and a space, written
`##` below, plus every line after it up to but not including the next `##`
line, or the end of the poem. Section numbers start at 1 and count in the
order the `##` lines appear. A section's NAME is the text after `##` and its
space. If the poem has no `##` line, the poem HAS NO SECTIONS - say so.
Never invent a section.

PREFACE - any non-blank lines before the first `##` line, once the METADATA
BLOCK and TITLE LINE are set aside. A preface is not a section and has no
number. Call it "the preface". None of the bundled poems has one.

BLANK LINE - a line with nothing on it, or only spaces.

STANZA - a run of one or more non-blank lines in a row, with a BLANK LINE, or
the start or end of its section, on each side. Heading lines are never part of
a stanza. ONE OR MORE blank lines in a row count as ONE separator: two or
three blank lines in a row do NOT make an empty stanza. Stanza numbers start
at 1 and restart at 1 inside every section. When the poem has no sections,
stanza 1 is the first run of non-blank lines after the METADATA BLOCK and the
TITLE LINE.

VERBATIM - character for character. Keep leading spaces exactly as they are;
some lines are indented 1, 5 or 6 spaces. Keep the exact quote marks the poem
uses: some poems use `“ ” ’` and some use `" '`. Keep `--` as two hyphens
and `—` as an em dash. Keep underscores such as `_was_`. Do not straighten
quotes, do not re-align indentation, do not fix spelling, do not modernise
anything.

## Steps - follow in order, do not skip

1. DECIDE WHERE THE POEM IS. Does the request, or the conversation, contain
   two or more lines of verse in a row - actual lines of the poem, not just a
   title? If YES, the poem is PASTED: use only that text, read no file, run
   no script, and go to step 4. If NO, the poem is BUNDLED: go to step 2.

2. NAME THE BUNDLED POEM. Use whatever the request calls it - the title, a
   distinctive word from the title, or the poet. Do not invent an id and do not
   guess between two poems: if you are unsure, run `scripts/poem.py list`
   first. If the script comes back with a list of poems instead of verse, the
   name was unknown or ambiguous: report that list, ask which poem is wanted,
   and STOP.

3. ASK THE SCRIPT, then go to step 6. Run `scripts/poem.py` with one of:
   - `stanza <poem> --stanza <n>` - one stanza of a poem with no sections
   - `stanza <poem> --section <n-or-name> --stanza <n>` - one stanza of a
     sectioned poem
   - `sections <poem>` - the section names and how many stanzas each has
   - `section <poem> --section <n-or-name>` - one whole section, if it is short
   - `search <poem> "<words>"` - which stanzas contain some words
   - `list` - every bundled poem, with poet, year and counts

   `<poem>` is the title, part of the title, or the poet. Quote it if it
   contains spaces.

   The script prints labels, then a line containing only `---`, then the
   exact lines of verse. Copy those lines into your answer unchanged. If it
   prints a line starting `NOT FOUND:` or `TOO LONG:`, that line is your
   answer - pass it on and quote no verse. Run the script at most twice.

4. FOR A PASTED POEM, FIND THE SECTION. If the poem has no `##` line, say it
   has no sections and treat the whole poem as one section. Otherwise match
   the requested section against the `##` lines, ignoring capitals and
   punctuation: "Fit the First" is section 1, "the fifth fit" is section 5,
   "section 3" is section 3. If it does not exist, report NOT FOUND with the
   valid range, and STOP.

5. FOR A PASTED POEM, FIND THE STANZA. Count exactly like this:
   a. Start at the first line of verse: after the section's `##` line, or
      after the METADATA BLOCK and TITLE LINE if the poem has no sections.
   b. Set n = 0.
   c. Go down the lines one at a time. Every time a non-blank line comes
      right after a blank line, or right after a heading line, add 1 to n.
   d. When n equals the number you were asked for, stop counting. The stanza
      is that line plus every non-blank line directly below it, up to the
      next blank line.
   e. If you run out of lines before n reaches the number, the stanza does
      not exist: report NOT FOUND with the number of stanzas you counted,
      and STOP.

6. ANSWER using the Output rules below. Then STOP. Do not read another file.
   Do not quote anything else.

Use at most 2 tool calls in total.

## Other kinds of question

WHICH STANZA MENTIONS A WORD - for a bundled poem run
`search <poem> "<words>"`; it does the searching. For a pasted poem, scan the
lines yourself. Cite every stanza that matches, but quote only the first. If
the words appear nowhere, say so and quote nothing.

WHAT A STANZA MEANS - quote the stanza first, then explain in AT MOST 3
sentences, using only the words and images in the lines you just quoted.
Gloss invented words such as "brillig" and "slithy" as invented, not as real
vocabulary. Leave out biography and publication history unless asked. The
poet and year come from the poem's own METADATA BLOCK, or from `list` - never
from memory.

FORM AND COUNTS - count the lines of the stanza you quoted: say "couplet"
for two lines, "quatrain" for four. Get section and stanza totals from
`sections <poem>`; never estimate them. For rhyme scheme, label the end words
with letters such as ABAB, and quote the stanza so the reader can check. Say
"roughly" about metre, and do not scan line by line unless asked.

## Worked example

Request: "What is the third stanza of Jabberwocky?"

There is no verse in the request, so the poem is bundled. Call
`run_script(script="scripts/poem.py", arguments="stanza jabberwocky --stanza 3")`.
The script prints labels, `---`, and four lines. The answer:

Jabberwocky - stanza 3 of 7

```text
He took his vorpal sword in hand:
Long time the manxome foe he sought—
So rested he by the Tumtum tree,
And stood awhile in thought.
```

That is a quatrain. The em dash and the straight apostrophes are copied
exactly as the poem has them.

## Output

1. One citation line, then the quoted stanza, then at most a few sentences of
   explanation if a question was asked.

2. The citation line is:
   `<Poem Title> - <Section name> - stanza <n> of <total in that section>`
   Leave out the section part when the poem has no sections.

3. Put quoted verse in a fenced code block: three backticks, the lines, three
   backticks. Use a fenced block, NEVER a `>` blockquote - only a fenced
   block keeps the leading spaces.

4. Quote ONLY the lines you were asked for. Everything else stays out.

5. Quote AT MOST 40 lines of verse in one answer. If the request needs more,
   quote nothing and ask which section or which stanza is wanted.

6. If a whole poem is requested, do not quote it: say how many sections and
   stanzas it has, and ask which one to quote.

7. When something does not exist, write one line and nothing else:
   `NOT FOUND: <what was asked for>. <Poem> has <N> <sections|stanzas> (1-<N>).`
   Quote no verse in a NOT FOUND answer.

8. Every line of verse in your answer must be copied from the pasted poem or
   from script output. If you cannot find a line, write NOT FOUND. Never
   write a line of verse from memory, even for a poem you know well.
