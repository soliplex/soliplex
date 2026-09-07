from unittest import mock

import pytest

from soliplex import context_segments


def _message(role, content=None, tool_calls=None):
    return mock.Mock(
        spec_set=["role", "content", "tool_calls"],
        role=role,
        content=content,
        tool_calls=tool_calls,
    )


def _tool_call(name, arguments):
    function = mock.Mock(spec_set=["name", "arguments"])
    function.name = name
    function.arguments = arguments
    return mock.Mock(spec_set=["function"], function=function)


class TestCollectTexts:
    def test_no_messages(self):
        assert context_segments.collect_texts([]) == []

    @pytest.mark.parametrize(
        "role, expected",
        [
            ("user", context_segments.USER_TEXT),
            ("assistant", context_segments.ASSISTANT_TEXT),
            ("tool", context_segments.TOOL_RESULT),
            ("system", context_segments.OVERHEAD),
            ("developer", context_segments.OVERHEAD),
        ],
    )
    def test_roles_map_to_kinds(self, role, expected):
        found = context_segments.collect_texts([_message(role, "hello")])

        assert found == [(expected, "hello")]

    def test_empty_content_contributes_nothing(self):
        """An assistant turn that only made a call has no text of its own."""
        found = context_segments.collect_texts(
            [_message("assistant", "", tool_calls=None)],
        )

        assert found == []

    def test_tool_calls_are_their_own_kind(self):
        found = context_segments.collect_texts(
            [
                _message(
                    "assistant",
                    "thinking",
                    tool_calls=[_tool_call("search", '{"q":"a"}')],
                ),
            ],
        )

        assert found == [
            (context_segments.ASSISTANT_TEXT, "thinking"),
            (context_segments.TOOL_CALL_ARGUMENTS, 'search{"q":"a"}'),
        ]

    def test_an_empty_tool_call_contributes_nothing(self):
        function = mock.Mock(spec_set=["name", "arguments"])
        function.name = None
        function.arguments = None
        call = mock.Mock(spec_set=["function"], function=function)

        found = context_segments.collect_texts(
            [_message("assistant", None, tool_calls=[call])],
        )

        assert found == []

    def test_a_call_without_a_function_contributes_nothing(self):
        call = mock.Mock(spec_set=["function"], function=None)

        found = context_segments.collect_texts(
            [_message("assistant", None, tool_calls=[call])],
        )

        assert found == []


class TestTotalsByKind:
    def test_the_residual_becomes_overhead(self):
        """What the measurement exceeds the pieces by is the hidden prefix."""
        pieces = [
            (context_segments.USER_TEXT, "a"),
            (context_segments.ASSISTANT_TEXT, "b"),
        ]

        found = context_segments.totals_by_kind(pieces, [10, 20], 100)

        assert found == {
            context_segments.USER_TEXT: 10,
            context_segments.ASSISTANT_TEXT: 20,
            context_segments.OVERHEAD: 70,
        }

    def test_pieces_of_a_kind_are_summed(self):
        pieces = [
            (context_segments.USER_TEXT, "a"),
            (context_segments.USER_TEXT, "b"),
        ]

        found = context_segments.totals_by_kind(pieces, [10, 5], 15)

        assert found == {context_segments.USER_TEXT: 15}

    def test_overhead_adds_to_an_existing_overhead_slice(self):
        pieces = [(context_segments.OVERHEAD, "system prompt")]

        found = context_segments.totals_by_kind(pieces, [30], 100)

        assert found == {context_segments.OVERHEAD: 100}

    def test_no_residual_adds_no_overhead(self):
        pieces = [(context_segments.USER_TEXT, "a")]

        found = context_segments.totals_by_kind(pieces, [50], 50)

        assert found == {context_segments.USER_TEXT: 50}

    def test_a_negative_residual_is_dropped(self):
        """A breakdown that sums past its own total is worse than a gap."""
        pieces = [(context_segments.USER_TEXT, "a")]

        found = context_segments.totals_by_kind(pieces, [80], 50)

        assert context_segments.OVERHEAD not in found

    def test_nothing_counted_is_all_overhead(self):
        found = context_segments.totals_by_kind([], [], 400)

        assert found == {context_segments.OVERHEAD: 400}

    def test_counts_must_line_up_with_pieces(self):
        with pytest.raises(ValueError, match="argument 2 is shorter"):
            context_segments.totals_by_kind(
                [(context_segments.USER_TEXT, "a")],
                [],
                10,
            )


def test_texts_of_drops_the_kinds():
    pieces = [
        (context_segments.USER_TEXT, "a"),
        (context_segments.TOOL_RESULT, "b"),
    ]

    assert context_segments.texts_of(pieces) == ["a", "b"]
