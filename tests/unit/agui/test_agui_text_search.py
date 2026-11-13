import pytest
import sqlalchemy
from ag_ui import core as agui_core

from soliplex.agui import schema as agui_schema
from soliplex.agui import text_search as agui_text_search

USER_1 = agui_core.UserMessage(id="u1", content="first question")
ASSISTANT_1 = agui_core.AssistantMessage(id="a1", content="first answer")
USER_2 = agui_core.UserMessage(id="u2", content="second question")
USER_3 = agui_core.UserMessage(id="u3", content="third question")
TOOL_1 = agui_core.ToolMessage(
    id="t1", content="tool output", tool_call_id="c1"
)
MULTIMODAL = agui_core.UserMessage(
    id="u4",
    content=[
        agui_core.TextInputContent(text="what is"),
        agui_core.ImageInputContent(
            source=agui_core.InputContentDataSource(
                value="aGk=", mime_type="image/png"
            ),
        ),
        agui_core.TextInputContent(text="this picture?"),
    ],
)
EMPTY = agui_core.UserMessage(id="u5", content="")


@pytest.mark.parametrize(
    "dialect_name, expected",
    [
        ("postgresql", True),
        ("sqlite", False),
    ],
)
def test_supports_text_search(dialect_name, expected):
    assert agui_text_search.supports_text_search(dialect_name) is expected


@pytest.mark.parametrize(
    "messages, expected",
    [
        ([], []),
        ([USER_1], ["first question"]),
        # Earlier turns are history, already indexed by earlier runs.
        ([USER_1, ASSISTANT_1, USER_2], ["second question"]),
        # Only the last message: an earlier, unanswered prompt was
        # indexed by its own run.
        ([USER_1, ASSISTANT_1, USER_2, USER_3], ["third question"]),
        # A run resuming after a tool call brings no new user text.
        ([USER_1, ASSISTANT_1, TOOL_1], []),
        ([ASSISTANT_1, MULTIMODAL], ["what is", "this picture?"]),
        ([ASSISTANT_1, EMPTY], []),
    ],
)
def test_new_user_texts(messages, expected):
    assert agui_text_search.new_user_texts(messages) == expected


@pytest.mark.parametrize(
    "events, expected",
    [
        ([], []),
        (
            [
                agui_core.TextMessageStartEvent(message_id="a1"),
                agui_core.TextMessageContentEvent(
                    message_id="a1", delta="Start at the"
                ),
                agui_core.TextMessageContentEvent(
                    message_id="a1", delta=" calip"
                ),
                agui_core.TextMessageContentEvent(
                    message_id="a1", delta="er."
                ),
                agui_core.TextMessageEndEvent(message_id="a1"),
            ],
            ["Start at the caliper."],
        ),
        (
            # A chunk without a 'message_id' continues the previous one.
            [
                agui_core.TextMessageChunkEvent(
                    message_id="a1", delta="Use the "
                ),
                agui_core.TextMessageChunkEvent(delta="mineral oil."),
                agui_core.TextMessageChunkEvent(message_id="a2"),
            ],
            ["Use the mineral oil."],
        ),
        (
            # Reasoning, thinking, and tool traffic are never included,
            # nor are messages without text (e.g., tool-call parents).
            [
                agui_core.ReasoningStartEvent(message_id="r1"),
                agui_core.ReasoningMessageContentEvent(
                    message_id="r1", delta="pondering"
                ),
                agui_core.ThinkingTextMessageContentEvent(delta="musing"),
                agui_core.TextMessageStartEvent(message_id="a1"),
                agui_core.TextMessageEndEvent(message_id="a1"),
                agui_core.ToolCallStartEvent(
                    tool_call_id="c1",
                    tool_call_name="search",
                    parent_message_id="a1",
                ),
                agui_core.ToolCallArgsEvent(
                    tool_call_id="c1", delta='{"query": "brakes"}'
                ),
                agui_core.ToolCallResultEvent(
                    message_id="t1", tool_call_id="c1", content="results"
                ),
                agui_core.TextMessageContentEvent(
                    message_id="a2", delta="Answer."
                ),
            ],
            ["Answer."],
        ),
        (
            # Interleaved messages are each assembled in order.
            [
                agui_core.TextMessageContentEvent(message_id="a1", delta="A"),
                agui_core.TextMessageContentEvent(message_id="a2", delta="X"),
                agui_core.TextMessageContentEvent(message_id="a1", delta="B"),
            ],
            ["AB", "X"],
        ),
    ],
)
def test_assistant_texts(events, expected):
    assert agui_text_search.assistant_texts(events) == expected


@pytest.mark.parametrize(
    "max_chars, expected",
    [
        (
            agui_text_search.MAX_RUN_TEXT_CHARS,
            "second question\n\nsecond answer",
        ),
        (10, "second que"),
    ],
)
def test_run_search_text(max_chars, expected):
    messages = [USER_1, ASSISTANT_1, USER_2]
    events = [
        agui_core.TextMessageContentEvent(message_id="a2", delta="second "),
        agui_core.TextMessageContentEvent(message_id="a2", delta="answer"),
    ]

    found = agui_text_search.run_search_text(
        messages, events, max_chars=max_chars
    )

    assert found == expected


def test_run_search_text_default_max_chars():
    messages = [
        agui_core.UserMessage(
            id="u1",
            content="x" * (agui_text_search.MAX_RUN_TEXT_CHARS + 1),
        )
    ]

    found = agui_text_search.run_search_text(messages, [])

    assert len(found) == agui_text_search.MAX_RUN_TEXT_CHARS


def _fake_to_tsvector(config, text):
    return f"<{config}:{text}>"


@pytest.fixture
def sqlite_to_tsvector(the_session):
    """Register a stand-in 'to_tsvector' SQL function on SQLite.

    With it (and the 'text_search' column being plain text on SQLite),
    the PostgreSQL 'UPDATE' appending to the vector runs on SQLite,
    concatenating the stand-in's output.
    """
    raw = the_session.connection().connection.driver_connection
    raw.create_function("to_tsvector", 2, _fake_to_tsvector)
    return _fake_to_tsvector


@pytest.mark.parametrize(
    "before, expected_prefix",
    [
        (None, ""),
        ("<earlier>", "<earlier>"),
    ],
)
def test_append_text_statement(
    the_session,
    sqlite_to_tsvector,
    before,
    expected_prefix,
):
    thread = agui_schema.Thread(
        room_id="room", user_name="user", text_search=before
    )
    bystander = agui_schema.Thread(room_id="room", user_name="user")
    the_session.add_all([thread, bystander])
    the_session.flush()

    the_session.execute(
        agui_text_search.append_text_statement(thread.id_, "some text")
    )

    found = the_session.scalars(
        sqlalchemy.select(agui_schema.Thread.text_search).order_by(
            agui_schema.Thread.id_
        )
    ).all()
    expected = expected_prefix + sqlite_to_tsvector(
        agui_text_search.TEXT_SEARCH_CONFIG, "some text"
    )
    assert found == [expected, None]


def test_matches_clause():
    clause = agui_text_search.matches_clause("brake -oil")

    assert clause.left.compare(agui_schema.Thread.text_search.expression)
    assert clause.operator.opstring == "@@"
    assert clause.right.name == "websearch_to_tsquery"
    assert [arg.value for arg in clause.right.clauses] == [
        agui_text_search.TEXT_SEARCH_CONFIG,
        "brake -oil",
    ]
