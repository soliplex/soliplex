"""AG-UI tool adapters for tic-tac-toe.

Each function returns a `pydantic_ai.ToolReturn` whose metadata
contains one or more `agui_core.StateDeltaEvent`s. The pattern
mirrors `src/soliplex/examples.py` and
`src/soliplex/tools/agui_run_feedback.py`.
"""

from __future__ import annotations

import contextlib
import datetime
import random
import uuid
from collections.abc import AsyncIterator
from typing import Any

import jsonpatch
import pydantic_ai
from ag_ui import core as agui_core
from pydantic_ai import messages as ai_messages
from pydantic_ai import output as ai_output
from pydantic_ai import run as ai_run
from pydantic_ai import tools as ai_tools
from pydantic_ai.models import openai as openai_models
from pydantic_ai.providers import ollama as ollama_providers

from soliplex import agents
from soliplex.config import agents as config_agents
from soliplex.config import tools as config_tools
from soliplex.skills.tic_tac_toe import engine
from soliplex.skills.tic_tac_toe import prompts

INBOX_KEY = "_inbox"
SURFACE_KEY = "tic_tac_toe"

_USER_MARK = "X"
_AGENT_MARK = "O"


class InvalidIntent(ValueError):
    """Raised when an inbox intent cannot be applied to the state."""


def _empty_game(*, rng: random.Random) -> dict[str, Any]:
    first_turn = rng.choice(["user", "agent"])
    return {
        "id": str(uuid.uuid4()),
        "board": [[None, None, None], [None, None, None], [None, None, None]],
        "moves": [],
        "turn": first_turn,
        "winner": None,
        "winning_line": None,
        "started_at": datetime.datetime.now(datetime.UTC).isoformat(
            timespec="seconds",
        ),
    }


def _board_to_lists(board: engine.Board) -> list[list[str | None]]:
    return [list(row) for row in board]


def _list_board_to_tuple(board: list[list[str | None]]) -> engine.Board:
    return tuple(tuple(row) for row in board)


def _line_to_dicts(line: list[engine.Cell] | None) -> list[dict] | None:
    if line is None:
        return None
    return [{"row": r, "col": c} for r, c in line]


def _state_with(state: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    return {**state, **overrides}


def _strip_inbox(state: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of state with INBOX_KEY removed.

    `_inbox` is wire-only — the client's bus never holds it. If we
    let a `remove /_inbox` op leak into a StateDeltaEvent, applying
    that delta on the client side will throw `PathNotFound` because
    the client's `agentState` does not contain that key. So we diff
    inbox-stripped states.
    """
    new_state = dict(state)
    new_state.pop(INBOX_KEY, None)
    return new_state


def _patch(before: dict[str, Any], after: dict[str, Any]) -> list[dict]:
    # Diff inbox-stripped states so emitted deltas never touch _inbox.
    return list(
        jsonpatch.make_patch(_strip_inbox(before), _strip_inbox(after)),
    )


def _clear_inbox_slice(state: dict[str, Any]) -> dict[str, Any]:
    """Server-side bookkeeping — clear the consumed inbox slice from
    the *server's working copy* of state. Callers pass this state
    through `_patch`, which itself strips `_inbox` from both sides,
    so the cleared slice doesn't appear in the wire delta. This
    function still exists so the server's own subsequent state
    reads (e.g., chained tool calls in the same run) don't see
    stale inbox data.
    """
    inbox = dict(state.get(INBOX_KEY, {}))
    if SURFACE_KEY in inbox:
        del inbox[SURFACE_KEY]
    if inbox:
        return _state_with(state, **{INBOX_KEY: inbox})
    new_state = dict(state)
    new_state.pop(INBOX_KEY, None)
    return new_state


def _wrap(
    before: dict[str, Any],
    after: dict[str, Any],
) -> pydantic_ai.ToolReturn:
    delta = _patch(before, after)
    return pydantic_ai.ToolReturn(
        return_value="ok",
        metadata=[agui_core.StateDeltaEvent(delta=delta)],
    )


def _outcome_from_mark(mark: str) -> str:
    if mark == _USER_MARK:
        return "user"
    if mark == _AGENT_MARK:
        return "agent"
    if mark == "draw":
        return "draw"
    raise ValueError(f"unknown mark {mark!r}")  # noqa: TRY003


def start_game(
    *,
    state: dict[str, Any],
    rng: random.Random | None = None,
) -> pydantic_ai.ToolReturn:
    rng = rng or random.Random()
    new_game = _empty_game(rng=rng)
    # If the random first-turn pick lands on the agent, play the
    # agent's opening move now so the user always meets a board on
    # which it is their turn.
    if new_game["turn"] == "agent":
        board = _list_board_to_tuple(new_game["board"])
        agent_row, agent_col = engine.pick_agent_move(board, rng)
        board_after = engine.apply_move(
            board, agent_row, agent_col, _AGENT_MARK,
        )
        new_game["board"] = _board_to_lists(board_after)
        new_game["moves"] = [
            {
                "player": "agent",
                "row": agent_row,
                "col": agent_col,
                "mark": _AGENT_MARK,
            },
        ]
        new_game["turn"] = "user"
    after = _state_with(state, game=new_game)
    after = _clear_inbox_slice(after)
    return _wrap(state, after)


def play_move(
    *,
    state: dict[str, Any],
    row: int,
    col: int,
    rng: random.Random | None = None,
) -> pydantic_ai.ToolReturn:
    rng = rng or random.Random()
    game = state.get("game")
    if game is None:
        raise InvalidIntent("no active game")  # noqa: TRY003
    if game["winner"] is not None:
        raise InvalidIntent("game already finished")  # noqa: TRY003
    if game["turn"] != "user":
        raise InvalidIntent(  # noqa: TRY003
            f"not user's turn (turn={game['turn']!r})",
        )

    board = _list_board_to_tuple(game["board"])
    try:
        board_after_user = engine.apply_move(board, row, col, _USER_MARK)
    except engine.InvalidMove as exc:
        raise InvalidIntent(str(exc)) from exc

    moves: list[dict] = list(game["moves"])
    moves.append(
        {"player": "user", "row": row, "col": col, "mark": _USER_MARK},
    )

    user_winner = engine.detect_winner(board_after_user)
    if user_winner is not None:
        # User's move ended the game; no agent response.
        line = engine.find_winning_line(board_after_user)
        new_game = {
            **game,
            "board": _board_to_lists(board_after_user),
            "moves": moves,
            "turn": "user",  # frozen
            "winner": _outcome_from_mark(user_winner),
            "winning_line": _line_to_dicts(line),
        }
    else:
        agent_row, agent_col = engine.pick_agent_move(board_after_user, rng)
        board_after_agent = engine.apply_move(
            board_after_user, agent_row, agent_col, _AGENT_MARK,
        )
        moves.append(
            {
                "player": "agent",
                "row": agent_row,
                "col": agent_col,
                "mark": _AGENT_MARK,
            },
        )
        agent_winner = engine.detect_winner(board_after_agent)
        line = (
            engine.find_winning_line(board_after_agent)
            if agent_winner in (_USER_MARK, _AGENT_MARK)
            else None
        )
        new_game = {
            **game,
            "board": _board_to_lists(board_after_agent),
            "moves": moves,
            "turn": "user",
            "winner": (
                _outcome_from_mark(agent_winner) if agent_winner else None
            ),
            "winning_line": _line_to_dicts(line),
        }

    after = _state_with(state, game=new_game)
    after = _clear_inbox_slice(after)
    return _wrap(state, after)


def undo_to(
    *,
    state: dict[str, Any],
    target_index: int,
) -> pydantic_ai.ToolReturn:
    game = state.get("game")
    if game is None:
        raise InvalidIntent("no active game")  # noqa: TRY003
    if not (0 <= target_index <= len(game["moves"])):
        raise InvalidIntent(  # noqa: TRY003
            f"target_index {target_index} out of range",
        )

    truncated = list(game["moves"])[:target_index]
    board, turn, winner, line = engine.replay(truncated)
    new_game = {
        **game,
        "board": _board_to_lists(board),
        "moves": truncated,
        "turn": turn,
        "winner": winner,
        "winning_line": _line_to_dicts(line),
    }
    after = _state_with(state, game=new_game)
    after = _clear_inbox_slice(after)
    return _wrap(state, after)


def redo_replay(
    *,
    state: dict[str, Any],
    moves: list[dict],
) -> pydantic_ai.ToolReturn:
    game = state.get("game")
    if game is None:
        raise InvalidIntent("no active game")  # noqa: TRY003
    full_moves = list(game["moves"]) + list(moves)
    board, turn, winner, line = engine.replay(full_moves)
    new_game = {
        **game,
        "board": _board_to_lists(board),
        "moves": full_moves,
        "turn": turn,
        "winner": winner,
        "winning_line": _line_to_dicts(line),
    }
    after = _state_with(state, game=new_game)
    after = _clear_inbox_slice(after)
    return _wrap(state, after)


def dispatch_inbox(
    *,
    state: dict[str, Any],
    rng: random.Random | None = None,
) -> list[agui_core.Event] | None:
    """Inspect state['_inbox']['tic_tac_toe'] and dispatch to the
    corresponding tool. Returns the metadata events (StateDeltaEvent)
    or None if there is no game intent (LLM should handle).

    Raises InvalidIntent on malformed/unknown intents.
    """
    inbox = state.get(INBOX_KEY) or {}
    intent_payload = inbox.get(SURFACE_KEY)
    if intent_payload is None:
        return None
    intent = intent_payload.get("intent")
    if intent == "new_game":
        return list(start_game(state=state, rng=rng).metadata or [])
    if intent == "play":
        move = intent_payload.get("move") or {}
        return list(
            play_move(
                state=state,
                row=int(move["row"]),
                col=int(move["col"]),
                rng=rng,
            ).metadata or [],
        )
    if intent == "undo":
        target_index = int(intent_payload["target_index"])
        return list(
            undo_to(state=state, target_index=target_index).metadata or [],
        )
    if intent == "redo":
        moves = list(intent_payload.get("moves") or [])
        return list(
            redo_replay(state=state, moves=moves).metadata or [],
        )
    raise InvalidIntent(f"unknown intent {intent!r}")  # noqa: TRY003


def tic_tac_toe_agent_factory(
    agent_config: config_agents.FactoryAgentConfig,
    tool_configs: config_tools.ToolConfigMap = None,
    mcp_client_toolset_configs: (
        config_tools.MCP_ClientToolsetConfigMap | None
    ) = None,
    skill_toolset_config: agents.SkillToolsetConfig | None = None,
) -> _TicTacToeAgent:
    """Hybrid agent: dispatches game intents deterministically (no
    LLM), falls through to a normal LLM agent for chat (no inbox).

    The dispatcher runs *before* the LLM in `run_stream_events` —
    when `_inbox.tic_tac_toe` is present, we yield only the
    `StateDeltaEvent`(s) returned by the corresponding tool plus a
    small templated assistant message ("Played (1,2)") and finish,
    skipping the LLM call entirely.

    When no inbox is present the agent behaves like a regular
    pydantic-ai agent with `prompts.SYSTEM_PROMPT`.
    """
    installation_config = agent_config._installation_config
    base_url = installation_config.get_environment("OLLAMA_BASE_URL")
    provider = openai_models.OpenAIChatModel(
        model_name="gpt-oss:latest",
        provider=ollama_providers.OllamaProvider(base_url=f"{base_url}/v1"),
    )
    inner = pydantic_ai.Agent(
        model=provider,
        system_prompt=prompts.SYSTEM_PROMPT,
    )
    return _TicTacToeAgent(inner=inner)


class _TicTacToeAgent:
    """Wraps a pydantic-ai Agent with a pre-LLM inbox dispatcher.

    Mirrors the FauxAgent shape (`run`, `run_stream`,
    `run_stream_events`) used in `soliplex.examples` so the runtime
    can drive it the same way.
    """

    def __init__(self, *, inner: pydantic_ai.Agent) -> None:
        self._inner = inner

    async def run(
        self,
        prompt,
        *,
        message_history=None,
        deps=None,
    ):
        return await self._inner.run(
            prompt,
            message_history=message_history,
            deps=deps,
        )

    @contextlib.asynccontextmanager
    async def run_stream(
        self,
        prompt,
        *,
        message_history=None,
        deps=None,
    ):
        async with self._inner.run_stream(
            prompt,
            message_history=message_history,
            deps=deps,
        ) as r:
            yield r

    async def run_stream_events(
        self,
        output_type: ai_output.OutputSpec | None = None,
        message_history=None,
        deferred_tool_results: pydantic_ai.DeferredToolResults | None = None,
        deps: ai_tools.AgentDepsT = None,
        **kwargs,
    ) -> AsyncIterator:
        state = getattr(deps, "state", None) or {}
        events = dispatch_inbox(state=state)
        if events is not None:
            tc_part = ai_messages.ToolCallPart("tic_tac_toe_dispatch")
            yield ai_messages.PartStartEvent(index=0, part=tc_part)
            yield ai_messages.PartEndEvent(index=0, part=tc_part)
            yield ai_messages.FunctionToolResultEvent(
                result=ai_messages.ToolReturnPart(
                    tool_name="tic_tac_toe_dispatch",
                    tool_call_id=tc_part.tool_call_id,
                    content="ok",
                    metadata=events,
                ),
            )
            text = _summarize_intent(state)
            if text:
                text_part = ai_messages.TextPart(content=text)
                yield ai_messages.PartStartEvent(index=1, part=text_part)
                yield ai_messages.PartEndEvent(index=1, part=text_part)
            yield ai_run.AgentRunResultEvent(
                result=text if text else "ok",
            )
            return
        async for ev in self._inner.run_stream_events(
            output_type=output_type,
            message_history=message_history,
            deferred_tool_results=deferred_tool_results,
            deps=deps,
            **kwargs,
        ):
            yield ev


def _summarize_intent(state: dict[str, Any]) -> str | None:
    payload = (state.get(INBOX_KEY) or {}).get(SURFACE_KEY)
    if not payload:
        return None
    intent = payload.get("intent")
    if intent == "play":
        m = payload.get("move") or {}
        return f"You played ({m.get('row')}, {m.get('col')})."
    if intent == "new_game":
        return "Starting a new game."
    if intent == "undo":
        return "Undone."
    if intent == "redo":
        return "Redone."
    return None
