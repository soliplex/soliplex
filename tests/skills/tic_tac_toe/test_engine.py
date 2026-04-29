import random

from soliplex.skills.tic_tac_toe import engine


def empty_board():
    return tuple(tuple(None for _ in range(3)) for _ in range(3))


class TestApplyMove:
    def test_places_mark_at_empty_cell(self):
        board = empty_board()
        new_board = engine.apply_move(board, 1, 1, "X")
        assert new_board[1][1] == "X"

    def test_other_cells_unchanged(self):
        board = empty_board()
        new_board = engine.apply_move(board, 1, 1, "X")
        for r in range(3):
            for c in range(3):
                if (r, c) != (1, 1):
                    assert new_board[r][c] is None

    def test_returns_immutable_board(self):
        board = empty_board()
        new_board = engine.apply_move(board, 0, 0, "X")
        assert isinstance(new_board, tuple)
        assert isinstance(new_board[0], tuple)
        # Original board untouched
        assert board[0][0] is None

    def test_raises_when_cell_occupied(self):
        board = empty_board()
        b1 = engine.apply_move(board, 0, 0, "X")
        try:
            engine.apply_move(b1, 0, 0, "O")
        except engine.InvalidMove:
            pass
        else:
            raise AssertionError("expected InvalidMove")  # noqa: TRY003


class TestDetectWinner:
    def test_empty_board_no_winner(self):
        board = empty_board()
        assert engine.detect_winner(board) is None

    def test_partial_board_no_winner(self):
        board = empty_board()
        board = engine.apply_move(board, 0, 0, "X")
        board = engine.apply_move(board, 1, 1, "O")
        assert engine.detect_winner(board) is None

    def test_row_win(self):
        board = empty_board()
        for c in range(3):
            board = engine.apply_move(board, 1, c, "X")
        assert engine.detect_winner(board) == "X"

    def test_column_win(self):
        board = empty_board()
        for r in range(3):
            board = engine.apply_move(board, r, 2, "O")
        assert engine.detect_winner(board) == "O"

    def test_diagonal_win(self):
        board = empty_board()
        for i in range(3):
            board = engine.apply_move(board, i, i, "X")
        assert engine.detect_winner(board) == "X"

    def test_anti_diagonal_win(self):
        board = empty_board()
        for i in range(3):
            board = engine.apply_move(board, i, 2 - i, "O")
        assert engine.detect_winner(board) == "O"

    def test_full_board_no_winner_is_draw(self):
        board = (
            ("X", "O", "X"),
            ("X", "O", "O"),
            ("O", "X", "X"),
        )
        assert engine.detect_winner(board) == "draw"


class TestFindWinningLine:
    def test_no_winner_returns_none(self):
        board = empty_board()
        assert engine.find_winning_line(board) is None

    def test_row_winning_line(self):
        board = (
            ("X", "X", "X"),
            (None, None, None),
            (None, None, None),
        )
        assert engine.find_winning_line(board) == [(0, 0), (0, 1), (0, 2)]

    def test_diagonal_winning_line(self):
        board = (
            ("X", None, None),
            (None, "X", None),
            (None, None, "X"),
        )
        assert engine.find_winning_line(board) == [(0, 0), (1, 1), (2, 2)]

    def test_draw_returns_none(self):
        board = (
            ("X", "O", "X"),
            ("X", "O", "O"),
            ("O", "X", "X"),
        )
        assert engine.find_winning_line(board) is None


class TestPickAgentMove:
    def test_picks_only_empty_cell_when_one_remains(self):
        board = (
            ("X", "O", "X"),
            ("X", "O", "O"),
            ("O", "X", None),
        )
        rng = random.Random(0)
        assert engine.pick_agent_move(board, rng) == (2, 2)

    def test_picks_from_empty_cells_only(self):
        board = (
            ("X", None, None),
            (None, "O", None),
            (None, None, "X"),
        )
        rng = random.Random(42)
        for _ in range(20):
            r, c = engine.pick_agent_move(board, rng)
            assert board[r][c] is None

    def test_full_board_raises(self):
        board = (
            ("X", "O", "X"),
            ("X", "O", "O"),
            ("O", "X", "X"),
        )
        rng = random.Random(0)
        try:
            engine.pick_agent_move(board, rng)
        except engine.NoMoveAvailable:
            pass
        else:
            raise AssertionError("expected NoMoveAvailable")  # noqa: TRY003


class TestReplay:
    def test_empty_history(self):
        board, turn, winner, line = engine.replay([])
        assert board == empty_board()
        assert turn == "user"
        assert winner is None
        assert line is None

    def test_one_user_move(self):
        moves = [{"player": "user", "row": 1, "col": 1, "mark": "X"}]
        board, turn, winner, line = engine.replay(moves)
        assert board[1][1] == "X"
        assert turn == "agent"
        assert winner is None
        assert line is None

    def test_user_winning_history(self):
        moves = [
            {"player": "user",  "row": 0, "col": 0, "mark": "X"},
            {"player": "agent", "row": 1, "col": 0, "mark": "O"},
            {"player": "user",  "row": 0, "col": 1, "mark": "X"},
            {"player": "agent", "row": 1, "col": 1, "mark": "O"},
            {"player": "user",  "row": 0, "col": 2, "mark": "X"},
        ]
        board, turn, winner, line = engine.replay(moves)
        assert winner == "user"
        assert line == [(0, 0), (0, 1), (0, 2)]
