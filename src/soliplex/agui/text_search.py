"""Full-text search over the text of AG-UI threads (PostgreSQL only)

Each finished run appends its new user prompts and its agent responses
to its thread's 'text_search' vector; a thread search matches against
that vector.  Reasoning / thinking output, tool calls and tool results
are never included.
"""

from __future__ import annotations

import collections.abc

from ag_ui import core as agui_core
from sqlalchemy import sql as sqla_sql

from soliplex.agui import schema as agui_schema

TEXT_SEARCH_CONFIG = "english"

# Longest text one run contributes to its thread's search vector; the
# rest of the run's text is dropped.
MAX_RUN_TEXT_CHARS = 100_000

_ASSISTANT_TEXT_EVENT_TYPES = frozenset(
    {
        agui_core.EventType.TEXT_MESSAGE_CONTENT,
        agui_core.EventType.TEXT_MESSAGE_CHUNK,
    }
)


def supports_text_search(dialect_name: str) -> bool:
    """Is full-text search available on the named SQL dialect?"""
    return dialect_name == "postgresql"


def new_user_texts(
    messages: collections.abc.Sequence[agui_core.Message],
) -> list[str]:
    """Return the text parts of the last message, if from the user

    A run's input repeats the thread's whole history:  only its last
    message, the user's prompt, is new to the run.  Non-text content
    parts (images, documents, etc.) are skipped.
    """
    if not messages or messages[-1].role != "user":
        return []

    content = messages[-1].content

    if isinstance(content, str):
        texts = [content]
    else:
        texts = [part.text for part in content if part.type == "text"]

    return [text for text in texts if text]


def assistant_texts(
    events: collections.abc.Iterable[agui_core.Event],
) -> list[str]:
    """Return the text of each agent message in 'events'

    'events' must be in the order they were emitted:  a message's text
    may be split across many events.  A 'TEXT_MESSAGE_CHUNK' with no
    'message_id' continues the previous message.  Messages with no text
    are omitted.
    """
    by_message_id: dict[str | None, list[str]] = {}
    message_id = None

    for event in events:
        if event.type in _ASSISTANT_TEXT_EVENT_TYPES:
            if event.message_id is not None:
                message_id = event.message_id

            if event.delta:
                by_message_id.setdefault(message_id, []).append(event.delta)

    return ["".join(deltas) for deltas in by_message_id.values()]


def run_search_text(
    messages: collections.abc.Sequence[agui_core.Message],
    events: collections.abc.Iterable[agui_core.Event],
    max_chars: int = MAX_RUN_TEXT_CHARS,
) -> str:
    """Return the searchable text a run adds to its thread

    The run's new user prompts, then its agent responses, separated by
    blank lines and truncated to 'max_chars'.
    """
    texts = new_user_texts(messages) + assistant_texts(events)
    return "\n\n".join(texts)[:max_chars]


def append_text_statement(thread_pk: int, text: str):
    """Return an 'UPDATE' appending 'text' to a thread's search vector"""
    column = agui_schema.Thread.text_search
    empty = sqla_sql.cast(sqla_sql.literal(""), column.type)

    return (
        sqla_sql.update(agui_schema.Thread)
        .where(agui_schema.Thread.id_ == thread_pk)
        .values(
            text_search=sqla_sql.func.coalesce(column, empty).op("||")(
                sqla_sql.func.to_tsvector(TEXT_SEARCH_CONFIG, text)
            )
        )
        .execution_options(synchronize_session=False)
    )


def matches_clause(text_query: str):
    """Return a clause matching threads whose text matches 'text_query'

    'text_query' is in 'websearch_to_tsquery' syntax:  bare words (all
    required), '"quoted phrases"', 'OR', and '-excluded' words.  It
    never raises a syntax error.
    """
    return agui_schema.Thread.text_search.op("@@")(
        sqla_sql.func.websearch_to_tsquery(TEXT_SEARCH_CONFIG, text_query)
    )
