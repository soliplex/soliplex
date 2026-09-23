from __future__ import annotations

import pathlib
from unittest import mock

import pytest

from soliplex.cli.audit import quizzes as audit_quizzes
from soliplex.config import quizzes as config_quizzes

TESTING_QUIZ_ERROR = "testing quiz error"


class QuizError(ValueError):
    def __init__(self):
        super().__init__(TESTING_QUIZ_ERROR)


@pytest.mark.parametrize(
    "w_layout, exp_yields",
    [
        ([], []),
        ([("p1", [])], []),
        ([("p1", ["readme.txt"])], []),
        ([("p1", ["q1.json"])], [("p1", "q1.json")]),
        (
            [("p1", ["q1.json", "readme.txt", "q2.json"])],
            [("p1", "q1.json"), ("p1", "q2.json")],
        ),
        (
            [
                ("p1", ["q1.json"]),
                ("p2", []),
                ("p3", ["q2.json", "q3.json"]),
            ],
            [
                ("p1", "q1.json"),
                ("p3", "q2.json"),
                ("p3", "q3.json"),
            ],
        ),
    ],
)
def test__iter_quiz_configs(
    tmp_path,
    the_installation,
    w_layout,
    exp_yields,
):
    quizzes_paths = []
    for dir_name, files in w_layout:
        d = tmp_path / dir_name
        d.mkdir()
        for f_name in files:
            (d / f_name).write_text("{}")
        quizzes_paths.append(d)

    the_installation._config.quizzes_paths = quizzes_paths

    expected = sorted(
        [
            (
                tmp_path / dir_name,
                tmp_path / dir_name / f_name,
                config_quizzes.QuizConfig(
                    id="check",
                    question_file=str(tmp_path / dir_name / f_name),
                ),
            )
            for dir_name, f_name in exp_yields
        ],
        key=lambda t: (str(t[0]), str(t[1])),
    )

    found = sorted(
        audit_quizzes._iter_quiz_configs(the_installation),
        key=lambda t: (str(t[0]), str(t[1])),
    )

    for found_item, exp_item in zip(found, expected, strict=True):
        assert found_item == exp_item


@pytest.mark.parametrize(
    "w_quiz_specs, exp_errors",
    [
        ([], {}),
        ([("p1", "q1.json", False)], {}),
        (
            [("p1", "q1.json", True)],
            {"quizzes": {"p1": {"q1.json": TESTING_QUIZ_ERROR}}},
        ),
        (
            [("p1", "q1.json", True), ("p1", "q2.json", False)],
            {"quizzes": {"p1": {"q1.json": TESTING_QUIZ_ERROR}}},
        ),
        (
            [("p1", "q1.json", True), ("p1", "q2.json", True)],
            {
                "quizzes": {
                    "p1": {
                        "q1.json": TESTING_QUIZ_ERROR,
                        "q2.json": TESTING_QUIZ_ERROR,
                    },
                },
            },
        ),
        (
            [("p1", "q1.json", True), ("p2", "q2.json", True)],
            {
                "quizzes": {
                    "p1": {"q1.json": TESTING_QUIZ_ERROR},
                    "p2": {"q2.json": TESTING_QUIZ_ERROR},
                },
            },
        ),
    ],
)
@mock.patch("soliplex.cli.audit.quizzes._iter_quiz_configs")
def test__invalid_quizzes(
    iter_quiz_configs,
    the_installation,
    w_quiz_specs,
    exp_errors,
):
    quiz_tuples = []
    for path_name, file_name, has_error in w_quiz_specs:
        q_path = pathlib.Path(path_name)
        q_file = mock.Mock()
        q_file.name = file_name
        q_config = mock.Mock()
        if has_error:
            q_config.get_questions.side_effect = QuizError()
        quiz_tuples.append((q_path, q_file, q_config))

    iter_quiz_configs.return_value = quiz_tuples

    found = audit_quizzes._invalid_quizzes(the_installation)

    assert found == exp_errors
    iter_quiz_configs.assert_called_once_with(the_installation)


# _audit_quizzes_section: ui only
# audit_quizzes: command
