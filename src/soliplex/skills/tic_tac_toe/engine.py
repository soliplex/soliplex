"""Pure game logic — board representation, win detection, agent AI.

No AG-UI / framework dependencies. Unit-testable in isolation."""

from __future__ import annotations

import random
from collections.abc import Iterable

Mark = str  # "X" or "O"
Board = tuple[tuple[Mark | None, ...], ...]


class InvalidMove(ValueError):
    """Raised when a move targets an occupied cell or is out of range."""


def apply_move(board: Board, row: int, col: int, mark: Mark) -> Board:
    if not (0 <= row < 3 and 0 <= col < 3):
        raise InvalidMove(f"out-of-range cell ({row},{col})")  # noqa: TRY003
    if board[row][col] is not None:
        raise InvalidMove(f"cell ({row},{col}) already occupied")  # noqa: TRY003
    return tuple(
        tuple(mark if (r, c) == (row, col) else board[r][c] for c in range(3))
        for r in range(3)
    )


Cell = tuple[int, int]
Outcome = str  # "X" | "O" | "draw"

# All eight winning lines on a 3x3 board.
_LINES: tuple[tuple[Cell, ...], ...] = (
    ((0, 0), (0, 1), (0, 2)),  # row 0
    ((1, 0), (1, 1), (1, 2)),  # row 1
    ((2, 0), (2, 1), (2, 2)),  # row 2
    ((0, 0), (1, 0), (2, 0)),  # col 0
    ((0, 1), (1, 1), (2, 1)),  # col 1
    ((0, 2), (1, 2), (2, 2)),  # col 2
    ((0, 0), (1, 1), (2, 2)),  # main diagonal
    ((0, 2), (1, 1), (2, 0)),  # anti-diagonal
)


def detect_winner(board: Board) -> Outcome | None:
    for line in _LINES:
        marks = {board[r][c] for r, c in line}
        if len(marks) == 1 and None not in marks:
            return next(iter(marks))
    if all(board[r][c] is not None for r in range(3) for c in range(3)):
        return "draw"
    return None


def find_winning_line(board: Board) -> list[Cell] | None:
    for line in _LINES:
        marks = {board[r][c] for r, c in line}
        if len(marks) == 1 and None not in marks:
            return list(line)
    return None


class NoMoveAvailable(RuntimeError):
    """Raised when pick_agent_move is called on a full board."""


def pick_agent_move(board: Board, rng: random.Random) -> Cell:
    empty = [(r, c) for r in range(3) for c in range(3) if board[r][c] is None]
    if not empty:
        raise NoMoveAvailable("board is full")  # noqa: TRY003
    return rng.choice(empty)


_USER_MARK = "X"
_AGENT_MARK = "O"


def _player_to_mark(player: str) -> Mark:
    if player == "user":
        return _USER_MARK
    if player == "agent":
        return _AGENT_MARK
    raise ValueError(f"unknown player {player!r}")  # noqa: TRY003


def _next_turn(last_player: str) -> str:
    return "agent" if last_player == "user" else "user"


def replay(
    moves: Iterable[dict],
) -> tuple[Board, str, Outcome | None, list[Cell] | None]:
    """Reconstruct (board, turn, winner, winning_line) from a moves history."""
    board: Board = tuple(tuple(None for _ in range(3)) for _ in range(3))
    last_player = None
    for move in moves:
        mark = _player_to_mark(move["player"])
        board = apply_move(board, move["row"], move["col"], mark)
        last_player = move["player"]
    winner_mark = detect_winner(board)
    if winner_mark == _USER_MARK:
        winner = "user"
    elif winner_mark == _AGENT_MARK:
        winner = "agent"
    elif winner_mark == "draw":
        winner = "draw"
    else:
        winner = None
    line = find_winning_line(board) if winner in ("user", "agent") else None
    turn = "user" if last_player is None else _next_turn(last_player)
    return board, turn, winner, line
