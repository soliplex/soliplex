import random

import jsonpatch
import pytest
from ag_ui import core as agui_core

from soliplex.skills.tic_tac_toe import skill


def _apply_metadata(state: dict, metadata: list) -> dict:
    """Apply each StateDeltaEvent in metadata, returning the result."""
    s = dict(state)
    for ev in metadata:
        assert isinstance(ev, agui_core.StateDeltaEvent)
        s = jsonpatch.apply_patch(s, list(ev.delta))
    return s


class TestStartGame:
    def test_initializes_game_state(self):
        rng = random.Random(0)
        result = skill.start_game(state={}, rng=rng)
        new_state = _apply_metadata({}, result.metadata)
        game = new_state["game"]
        assert game["board"] == [
            [None, None, None],
            [None, None, None],
            [None, None, None],
        ]
        assert game["moves"] == []
        assert game["winner"] is None
        assert game["winning_line"] is None
        assert game["turn"] in ("user", "agent")

    def test_clears_inbox(self):
        # The wire delta must not re-introduce inbox keys; the
        # `test_emitted_delta_does_not_touch_inbox` test asserts the
        # patch never touches `/_inbox`. Here we just verify the
        # delta does not add a `game` slot under `_inbox` or otherwise
        # surface inbox via the patch.
        rng = random.Random(0)
        state = {"_inbox": {"tic_tac_toe": {"intent": "new_game"}}}
        result = skill.start_game(state=state, rng=rng)
        for ev in result.metadata or []:
            for op in list(ev.delta):
                assert not op.get("path", "").startswith("/_inbox")

    def test_emitted_delta_does_not_touch_inbox(self):
        """Regression: the JSON patch must not include any op on the
        `_inbox` path. The client's bus never contains _inbox, so a
        `remove /_inbox` op would crash `bus.update(applyJsonPatch)`.
        """
        rng = random.Random(0)
        state = {"_inbox": {"tic_tac_toe": {"intent": "new_game"}}}
        result = skill.start_game(state=state, rng=rng)
        for ev in result.metadata or []:
            for op in list(ev.delta):
                assert not op.get("path", "").startswith(
                    "/_inbox",
                ), f"delta op leaks _inbox: {op}"


class TestPlayMove:
    def test_applies_user_move_and_agent_response(self):
        rng = random.Random(0)
        state = {
            "game": {
                "id": "g1",
                "board": [[None] * 3 for _ in range(3)],
                "moves": [],
                "turn": "user",
                "winner": None,
                "winning_line": None,
                "started_at": "2026-04-29T00:00:00",
            },
            "_inbox": {
                "tic_tac_toe": {
                    "intent": "play",
                    "move": {"row": 1, "col": 1},
                },
            },
        }
        result = skill.play_move(state=state, row=1, col=1, rng=rng)
        new_state = _apply_metadata(state, result.metadata)
        moves = new_state["game"]["moves"]
        assert moves[0] == {"player": "user", "row": 1, "col": 1, "mark": "X"}
        assert len(moves) == 2  # user + agent
        assert moves[1]["player"] == "agent"
        # Wire delta must never touch `_inbox` (see regression test).
        for ev in result.metadata or []:
            for op in list(ev.delta):
                assert not op.get("path", "").startswith("/_inbox")

    def test_user_winning_move_skips_agent_response(self):
        # Pre-fill so user's next move wins immediately.
        rng = random.Random(0)
        state = {
            "game": {
                "id": "g1",
                "board": [
                    ["X", "X", None],
                    ["O", "O", None],
                    [None, None, None],
                ],
                "moves": [
                    {"player": "user",  "row": 0, "col": 0, "mark": "X"},
                    {"player": "agent", "row": 1, "col": 0, "mark": "O"},
                    {"player": "user",  "row": 0, "col": 1, "mark": "X"},
                    {"player": "agent", "row": 1, "col": 1, "mark": "O"},
                ],
                "turn": "user",
                "winner": None,
                "winning_line": None,
                "started_at": "2026-04-29T00:00:00",
            },
            "_inbox": {
                "tic_tac_toe": {
                    "intent": "play",
                    "move": {"row": 0, "col": 2},
                },
            },
        }
        result = skill.play_move(state=state, row=0, col=2, rng=rng)
        new_state = _apply_metadata(state, result.metadata)
        moves = new_state["game"]["moves"]
        # User's winning move appended; no agent move appended after.
        assert moves[-1] == {"player": "user", "row": 0, "col": 2, "mark": "X"}
        assert new_state["game"]["winner"] == "user"
        assert new_state["game"]["winning_line"] is not None

    def test_invalid_move_raises(self):
        rng = random.Random(0)
        state = {
            "game": {
                "id": "g1",
                "board": [
                    ["X", None, None],
                    [None, None, None],
                    [None, None, None],
                ],
                "moves": [
                    {"player": "user", "row": 0, "col": 0, "mark": "X"},
                ],
                "turn": "agent",
                "winner": None,
                "winning_line": None,
                "started_at": "2026-04-29T00:00:00",
            },
            "_inbox": {
                "tic_tac_toe": {
                    "intent": "play",
                    "move": {"row": 0, "col": 0},
                },
            },
        }
        with pytest.raises(skill.InvalidIntent):
            skill.play_move(state=state, row=0, col=0, rng=rng)


class TestUndoTo:
    def test_truncates_moves(self):
        state = {
            "game": {
                "id": "g1",
                "board": [
                    ["X", None, None],
                    ["O", None, None],
                    [None, None, None],
                ],
                "moves": [
                    {"player": "user",  "row": 0, "col": 0, "mark": "X"},
                    {"player": "agent", "row": 1, "col": 0, "mark": "O"},
                ],
                "turn": "user",
                "winner": None,
                "winning_line": None,
                "started_at": "2026-04-29T00:00:00",
            },
            "_inbox": {"tic_tac_toe": {"intent": "undo", "target_index": 0}},
        }
        result = skill.undo_to(state=state, target_index=0)
        new_state = _apply_metadata(state, result.metadata)
        assert new_state["game"]["moves"] == []
        assert new_state["game"]["board"] == [[None] * 3 for _ in range(3)]
        assert new_state["game"]["turn"] == "user"
        assert new_state["game"]["winner"] is None


class TestRedoReplay:
    def test_appends_supplied_moves(self):
        state = {
            "game": {
                "id": "g1",
                "board": [[None] * 3 for _ in range(3)],
                "moves": [],
                "turn": "user",
                "winner": None,
                "winning_line": None,
                "started_at": "2026-04-29T00:00:00",
            },
            "_inbox": {
                "tic_tac_toe": {
                    "intent": "redo",
                    "moves": [
                        {"player": "user",  "row": 0, "col": 0, "mark": "X"},
                        {"player": "agent", "row": 1, "col": 0, "mark": "O"},
                    ],
                },
            },
        }
        result = skill.redo_replay(
            state=state,
            moves=[
                {"player": "user",  "row": 0, "col": 0, "mark": "X"},
                {"player": "agent", "row": 1, "col": 0, "mark": "O"},
            ],
        )
        new_state = _apply_metadata(state, result.metadata)
        assert len(new_state["game"]["moves"]) == 2


class TestDispatchInbox:
    """The factory's pre-LLM dispatcher reads `_inbox.tic_tac_toe`
    and returns the matching tool's events synchronously, without
    invoking the LLM. Conversational inputs (no inbox) fall through
    and return None so the regular LLM path runs."""

    def test_play_intent_dispatches_to_play_move(self):
        rng = random.Random(0)
        state = {
            "game": {
                "id": "g1",
                "board": [[None] * 3 for _ in range(3)],
                "moves": [],
                "turn": "user",
                "winner": None,
                "winning_line": None,
                "started_at": "2026-04-29T00:00:00",
            },
            "_inbox": {
                "tic_tac_toe": {
                    "intent": "play",
                    "move": {"row": 0, "col": 0},
                },
            },
        }
        events = skill.dispatch_inbox(state=state, rng=rng)
        assert events is not None
        assert any(
            isinstance(e, agui_core.StateDeltaEvent) for e in events
        )

    def test_no_inbox_returns_none(self):
        state = {"game": None}
        assert skill.dispatch_inbox(
            state=state, rng=random.Random(0),
        ) is None

    def test_unknown_intent_raises(self):
        state = {
            "game": None,
            "_inbox": {"tic_tac_toe": {"intent": "frobnicate"}},
        }
        with pytest.raises(skill.InvalidIntent):
            skill.dispatch_inbox(state=state, rng=random.Random(0))
