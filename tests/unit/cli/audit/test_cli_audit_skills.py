from __future__ import annotations

import pathlib
from unittest import mock

import pytest

from soliplex.cli.audit import skills as audit_skills

TESTING_SKILL_ERROR = "testing skill error"


class SkillError(ValueError):
    def __init__(self):
        super().__init__(TESTING_SKILL_ERROR)


@pytest.mark.parametrize(
    "w_self_has_skill, w_subs, exp_yields",
    [
        (True, [], ["."]),
        (True, [("a", True), ("b", True)], ["."]),
        (False, [], []),
        (False, [("a", False), ("b", False)], []),
        (False, [("a", True), ("b", False), ("c", True)], ["a", "c"]),
        (False, [(".hidden", True), ("a", True)], ["a"]),
        (False, [("c", True), ("a", True), ("b", True)], ["a", "b", "c"]),
    ],
)
def test__find_skill_paths(
    tmp_path,
    w_self_has_skill,
    w_subs,
    exp_yields,
):
    to_search = tmp_path / "search"
    to_search.mkdir()

    if w_self_has_skill:
        (to_search / "SKILL.md").write_text("")

    for sub_name, has_skill in w_subs:
        sub = to_search / sub_name
        sub.mkdir()
        if has_skill:
            (sub / "SKILL.md").write_text("")

    expected = [
        to_search if name == "." else to_search / name for name in exp_yields
    ]

    found = list(audit_skills._find_skill_paths(to_search))

    assert found == expected


@pytest.mark.parametrize(
    "w_skill_specs, exp_errors",
    [
        ([], {}),
        ([("s1", None)], {}),
        ([("s1", 0)], {}),
        ([("s1", 1)], {"skills": {"s1": [TESTING_SKILL_ERROR]}}),
        (
            [("s1", 2)],
            {"skills": {"s1": [TESTING_SKILL_ERROR, TESTING_SKILL_ERROR]}},
        ),
        (
            [("s1", None), ("s2", 1), ("s3", 0), ("s4", 2)],
            {
                "skills": {
                    "s2": [TESTING_SKILL_ERROR],
                    "s4": [TESTING_SKILL_ERROR, TESTING_SKILL_ERROR],
                },
            },
        ),
    ],
)
def test__invalid_skill_configs(
    the_installation,
    w_skill_specs,
    exp_errors,
):
    skill_configs = {}
    for skill_name, errors_count in w_skill_specs:
        cfg = mock.Mock()
        if errors_count is None:
            cfg.errors = None
        else:
            cfg.errors = [SkillError() for _ in range(errors_count)]
        skill_configs[skill_name] = cfg

    the_installation._config.skill_configs = skill_configs

    found = audit_skills._invalid_skill_configs(the_installation)

    assert found == exp_errors


@pytest.mark.parametrize(
    "w_path_specs, exp_errors",
    [
        ([], {}),
        ([("p1", [])], {}),
        ([("p1", [("s1", 0)])], {}),
        (
            [("p1", [("s1", 1)])],
            {"skills_filesystem": {"s1": [TESTING_SKILL_ERROR]}},
        ),
        (
            [("p1", [("s1", 2)])],
            {
                "skills_filesystem": {
                    "s1": [TESTING_SKILL_ERROR, TESTING_SKILL_ERROR],
                },
            },
        ),
        (
            [
                ("p1", [("s1", 1), ("s2", 0)]),
                ("p2", []),
                ("p3", [("s3", 1), ("s4", 2)]),
            ],
            {
                "skills_filesystem": {
                    "s1": [TESTING_SKILL_ERROR],
                    "s3": [TESTING_SKILL_ERROR],
                    "s4": [TESTING_SKILL_ERROR, TESTING_SKILL_ERROR],
                },
            },
        ),
    ],
)
@mock.patch("soliplex.cli.audit.skills.skill_validator.validate")
@mock.patch("soliplex.cli.audit.skills._find_skill_paths")
def test__invalid_filesystem_skills(
    find_skill_paths,
    validate,
    the_installation,
    w_path_specs,
    exp_errors,
):
    fs_paths = []
    find_side_effects = []
    validate_side_effects = []
    for path_name, skill_specs in w_path_specs:
        fs_paths.append(pathlib.Path(path_name))
        skill_paths_for_this = []
        for skill_name, errors_count in skill_specs:
            skill_paths_for_this.append(pathlib.Path(skill_name))
            validate_side_effects.append(
                [SkillError() for _ in range(errors_count)]
            )
        find_side_effects.append(skill_paths_for_this)

    the_installation._config.filesystem_skills_paths = fs_paths
    find_skill_paths.side_effect = find_side_effects
    validate.side_effect = validate_side_effects

    found = audit_skills._invalid_filesystem_skills(the_installation)

    assert found == exp_errors
    assert find_skill_paths.call_args_list == [mock.call(p) for p in fs_paths]


# _audit_skills_section: ui only
# audit_skills: command
