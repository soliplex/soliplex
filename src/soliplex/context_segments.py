"""Attribute a measured context size to the parts that make it up.

The total is measured, not composed: it is what the provider reported
for a run's final request. What this adds is *where* those tokens went,
by counting each stored message on its own and treating whatever is left
over as overhead.

That residual is the point. Everything a client cannot enumerate --
the agent's instructions, capability instructions, tool and MCP schemas,
the chat template's per-turn scaffolding, the deferred-capability
catalog -- lands in it correctly without any of it being reconstructed.
MCP tool schemas in particular are only knowable by connecting to the
MCP server, so composing the prefix instead would read low.
"""

#: Kinds a client can attribute tokens to. These mirror the segment
#: kinds the UI groups a breakdown by; a name added here has to be added
#: there too or its slice is silently dropped.
USER_TEXT = "userText"
ASSISTANT_TEXT = "assistantText"
TOOL_CALL_ARGUMENTS = "toolCallArguments"
TOOL_RESULT = "toolResult"
OVERHEAD = "overhead"


def _tool_call_text(tool_call) -> str:
    """Render a tool call the way a request carries it."""
    function = getattr(tool_call, "function", None)
    name = getattr(function, "name", "") or ""
    arguments = getattr(function, "arguments", "") or ""

    return f"{name}{arguments}"


def collect_texts(messages) -> list[tuple[str, str]]:
    """Return '(kind, text)' for each countable piece of 'messages'.

    A system or developer message is folded into overhead rather than
    given its own kind: from a reader's point of view it is part of the
    same invisible prefix as the instructions and tool schemas, and
    splitting it out would invite the reading that the rest is
    attributable when it is not.
    """
    pieces = []

    for message in messages:
        role = getattr(message, "role", None)
        content = getattr(message, "content", None)

        if role == "user":
            kind = USER_TEXT
        elif role == "assistant":
            kind = ASSISTANT_TEXT
        elif role == "tool":
            kind = TOOL_RESULT
        else:
            kind = OVERHEAD

        if content:
            pieces.append((kind, content))

        for tool_call in getattr(message, "tool_calls", None) or ():
            text = _tool_call_text(tool_call)

            if text:
                pieces.append((TOOL_CALL_ARGUMENTS, text))

    return pieces


def totals_by_kind(pieces, counts, measured_tokens) -> dict[str, int]:
    """Fold per-piece counts into a per-kind breakdown.

    'measured_tokens' anchors the result: whatever it exceeds the
    counted pieces by is overhead, and it is reported as such. A
    negative residual is dropped rather than shown, because a breakdown
    that sums past its own total is worse than one that admits it
    cannot account for everything.
    """
    by_kind: dict[str, int] = {}

    for (kind, _text), count in zip(pieces, counts, strict=True):
        by_kind[kind] = by_kind.get(kind, 0) + count

    residual = measured_tokens - sum(by_kind.values())

    if residual > 0:
        by_kind[OVERHEAD] = by_kind.get(OVERHEAD, 0) + residual

    return by_kind


def texts_of(pieces) -> list[str]:
    """Return just the texts from 'collect_texts' output."""
    return [text for _kind, text in pieces]
