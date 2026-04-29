from __future__ import annotations

import contextlib
import pathlib
from unittest import mock

import pytest
import typer
import yaml

from soliplex import installation
from soliplex import secrets
from soliplex.cli import audit as cli_audit
from soliplex.config import installation as config_installation
from soliplex.config import quizzes as config_quizzes
from soliplex.config import rag as config_rag

TESTING_MODEL_ERROR = "testing model error"
TESTING_RAG_ERROR = "testing rag error"
TESTING_QUIZ_ERROR = "testing quiz error"
TESTING_SKILL_ERROR = "testing skill error"

no_error_none = contextlib.nullcontext()


class ModelException(ValueError):
    def __init__(self):
        super().__init__(TESTING_MODEL_ERROR)


class RAGError(ValueError):
    def __init__(self):
        super().__init__(TESTING_RAG_ERROR)


class QuizError(ValueError):
    def __init__(self):
        super().__init__(TESTING_QUIZ_ERROR)


class SkillError(ValueError):
    def __init__(self):
        super().__init__(TESTING_SKILL_ERROR)


class _OkRagCfg:
    rag_lancedb_path = None


class _ErrRagCfg:
    @property
    def rag_lancedb_path(self):
        raise RAGError()


@pytest.fixture
def ctx():
    return mock.create_autospec(typer.Context, obj={})


@pytest.fixture
def installation_path(tmp_path):
    installation_path = tmp_path / "installation.yaml"
    installation_path.write_text("id: test")
    return installation_path


@pytest.fixture
def the_installation() -> installation.Installation:
    i_config = mock.create_autospec(config_installation.InstallationConfig)
    return installation.Installation(_config=i_config)


@pytest.mark.parametrize("w_quiet", [False, True])
@mock.patch("soliplex.cli.audit.the_console")
def test__quiet_console_funcs(the_console, w_quiet):
    found = cli_audit._quiet_console_funcs(w_quiet)

    (f_line, f_rule, f_print, f_print_exception) = found

    if w_quiet:
        assert f_line is cli_audit._noop
        assert f_rule is cli_audit._noop
        assert f_print is cli_audit._noop
        assert f_print_exception is cli_audit._noop
    else:
        assert f_line is the_console.line
        assert f_rule is the_console.rule
        assert f_print is the_console.print
        assert f_print_exception is the_console.print_exception


@pytest.mark.parametrize("w_quiet", [False, True])
@pytest.mark.parametrize("w_errors", [{}, {"foo": "bar"}])
@mock.patch("soliplex.cli.audit.the_console")
@mock.patch("sys.exit")
def test__emit_errors(
    sys_exit,
    the_console,
    w_errors,
    w_quiet,
):
    cli_audit._emit_errors(w_errors, w_quiet)

    if w_errors and w_quiet:
        the_console.print_json.assert_called_once_with(data=w_errors)
    else:
        the_console.print_json.assert_not_called()

    if w_errors:
        sys_exit.assert_called_once_with(1)
    else:
        sys_exit.assert_not_called()


@pytest.mark.parametrize("w_already", [False, True])
@mock.patch("soliplex.cli.cli_util.get_installation")
def test__get_installation(
    get_installation,
    ctx,
    installation_path,
    w_already,
):
    already = object()

    if w_already:
        ctx.obj["the_installation"] = already

    found = cli_audit._get_installation(ctx, installation_path)

    if w_already:
        assert found is already
        get_installation.assert_not_called()
    else:
        assert found is get_installation.return_value
        get_installation.assert_called_once_with(
            installation_path,
            auditing=True,
        )


@pytest.mark.parametrize(
    "w_args, exp_args",
    [
        ((), ["all"]),
        (["-q"], ["-q", "all"]),
        (["all"], ["all"]),
        (["-q", "all"], ["-q", "all"]),
        (["other", "w_arg"], ["other", "w_arg"]),
        (["-q", "other", "w_arg"], ["-q", "other", "w_arg"]),
        (["-q", "path"], ["-q", "all", "path"]),
        (["path"], ["all", "path"]),
    ],
)
@mock.patch("soliplex.cli.audit.typer_core.TyperGroup.parse_args")
def test__auditgroup_parse_args(parse_args, ctx, w_args, exp_args):
    all_command = mock.Mock(spec_set=())
    other_command = mock.Mock(spec_set=())
    ag = cli_audit._AuditGroup(
        commands={"all": all_command, "other": other_command},
    )

    found = ag.parse_args(ctx, w_args)

    assert found is parse_args.return_value
    parse_args.assert_called_once_with(ctx, exp_args)


@pytest.mark.parametrize("w_quiet", [False, True])
def test__audit_callback(ctx, w_quiet):
    w_quiet_kw = {"quiet": w_quiet}

    cli_audit._audit_callback(ctx, **w_quiet_kw)

    assert ctx.obj["quiet"] == w_quiet


@pytest.mark.parametrize("w_errors", [False, True])
@pytest.mark.parametrize("w_quiet", [False, True])
@mock.patch("soliplex.cli.audit._emit_errors")
@mock.patch("soliplex.cli.audit._audit_logfire_section")
@mock.patch("soliplex.cli.audit._audit_logging_section")
@mock.patch("soliplex.cli.audit._audit_skills_section")
@mock.patch("soliplex.cli.audit._audit_quizzes_section")
@mock.patch("soliplex.cli.audit._audit_completions_section")
@mock.patch("soliplex.cli.audit._audit_rooms_section")
@mock.patch("soliplex.cli.audit._audit_oidc_section")
@mock.patch("soliplex.cli.audit._audit_environment_section")
@mock.patch("soliplex.cli.audit._audit_secrets_section")
@mock.patch("soliplex.cli.audit._audit_installation_section")
def test_audit_all(
    _audit_installation_section,
    _audit_secrets_section,
    _audit_environment_section,
    _audit_oidc_section,
    _audit_rooms_section,
    _audit_completions_section,
    _audit_quizzes_section,
    _audit_skills_section,
    _audit_logging_section,
    _audit_logfire_section,
    _emit_errors,
    ctx,
    installation_path,
    w_quiet,
    w_errors,
):
    ctx.obj["quiet"] = w_quiet

    if w_errors:
        _audit_installation_section.return_value = {"installation": None}
        _audit_secrets_section.return_value = {"secrets": None}
        _audit_environment_section.return_value = {"environment": None}
        _audit_oidc_section.return_value = {"oidc": None}
        _audit_rooms_section.return_value = {"rooms": None}
        _audit_completions_section.return_value = {"completions": None}
        _audit_quizzes_section.return_value = {"quizzes": None}
        _audit_skills_section.return_value = {"skills": None}
        _audit_logging_section.return_value = {"logging": None}
        _audit_logfire_section.return_value = {"logfire": None}

        expected = {
            "installation": None,
            "secrets": None,
            "environment": None,
            "oidc": None,
            "rooms": None,
            "completions": None,
            "quizzes": None,
            "skills": None,
            "logging": None,
            "logfire": None,
        }
    else:
        _audit_installation_section.return_value = {}
        _audit_secrets_section.return_value = {}
        _audit_environment_section.return_value = {}
        _audit_oidc_section.return_value = {}
        _audit_rooms_section.return_value = {}
        _audit_completions_section.return_value = {}
        _audit_quizzes_section.return_value = {}
        _audit_skills_section.return_value = {}
        _audit_logging_section.return_value = {}
        _audit_logfire_section.return_value = {}

        expected = {}

    cli_audit.audit_all(ctx, installation_path)

    _emit_errors.assert_called_once_with(expected, w_quiet)

    _audit_installation_section.assert_called_once_with(ctx, installation_path)
    _audit_secrets_section.assert_called_once_with(ctx, installation_path)
    _audit_environment_section.assert_called_once_with(ctx, installation_path)
    _audit_oidc_section.assert_called_once_with(ctx, installation_path)
    _audit_rooms_section.assert_called_once_with(ctx, installation_path)
    _audit_completions_section.assert_called_once_with(ctx, installation_path)
    _audit_quizzes_section.assert_called_once_with(ctx, installation_path)
    _audit_skills_section.assert_called_once_with(ctx, installation_path)
    _audit_logging_section.assert_called_once_with(ctx, installation_path)
    _audit_logfire_section.assert_called_once_with(ctx, installation_path)


@pytest.mark.parametrize("w_error", [False, True])
@mock.patch("soliplex.models.Installation.from_config")
def test__invalid_installation(mifc, the_installation, w_error):
    if w_error:
        mifc.side_effect = ModelException()

    found = cli_audit._invalid_installation(the_installation)

    if w_error:
        assert found == {"installation_model": TESTING_MODEL_ERROR}
    else:
        assert found == {}

    mifc.assert_called_once_with(the_installation._config)


# _audit_installation_section: ui only
# audit_installation: command


@pytest.mark.parametrize(
    "w_missing_secrets, exp_missing",
    [
        (None, None),
        ("alpha", ["alpha"]),
        ("alpha,beta", ["alpha", "beta"]),
    ],
)
@mock.patch("soliplex.installation.Installation.resolve_secrets")
def test__missing_secrets(
    resolve_secrets,
    the_installation,
    w_missing_secrets,
    exp_missing,
):
    if w_missing_secrets is not None:
        resolve_secrets.side_effect = secrets.SecretsNotFound(
            w_missing_secrets,
            [ValueError()],
        )

    found = cli_audit._missing_secrets(the_installation)

    if exp_missing is not None:
        assert found == {"missing_secrets": exp_missing}
    else:
        assert found == {}

    resolve_secrets.assert_called_once_with()


# _audit_secrets_section: ui only
# audit_secrets: command


@pytest.mark.parametrize(
    "w_missing_env_vars, exp_missing",
    [
        (None, None),
        ("ALPHA", ["ALPHA"]),
        ("ALPHA,BETA", ["ALPHA", "BETA"]),
    ],
)
@mock.patch("soliplex.installation.Installation.resolve_environment")
def test__missing_env_vars(
    resolve_environment,
    the_installation,
    w_missing_env_vars,
    exp_missing,
):
    if w_missing_env_vars is not None:
        resolve_environment.side_effect = config_installation.MissingEnvVars(
            w_missing_env_vars,
            [ValueError()],
        )

    found = cli_audit._missing_env_vars(the_installation)

    if exp_missing is not None:
        assert found == {"missing_env_vars": exp_missing}
    else:
        assert found == {}

    resolve_environment.assert_called_once_with()


# _audit_environment_section: ui only
# audit_environment: command


@pytest.mark.parametrize(
    "w_cfg_id_and_error, exp_invalid_ids",
    [
        ([], []),
        ([("alpha", False)], []),
        ([("alpha", True)], ["alpha"]),
        ([("alpha", False), ("beta", True)], ["beta"]),
        ([("alpha", True), ("beta", True)], ["alpha", "beta"]),
    ],
)
@mock.patch("soliplex.models.OIDCAuthSystem.from_config")
def test__invalid_oidc_auth_providers(
    moafc,
    the_installation,
    w_cfg_id_and_error,
    exp_invalid_ids,
):
    oidc_configs = []
    side_effects = []
    for cfg_id, has_error in w_cfg_id_and_error:
        cfg = mock.Mock()
        cfg.id = cfg_id
        oidc_configs.append(cfg)
        side_effects.append(ModelException() if has_error else None)

    the_installation._config.oidc_auth_system_configs = oidc_configs
    moafc.side_effect = side_effects

    found = cli_audit._invalid_oidc_auth_providers(the_installation)

    if exp_invalid_ids:
        assert found == {
            "oidc": {cid: TESTING_MODEL_ERROR for cid in exp_invalid_ids},
        }
    else:
        assert found == {}

    assert moafc.call_args_list == [mock.call(cfg) for cfg in oidc_configs]


# _audit_oidc_section: ui only
# audit_oidc_auth_providers: command


@pytest.mark.parametrize("w_count", [0, 5])
@pytest.mark.anyio
async def test__async_count(w_count):
    rag = mock.AsyncMock()
    rag_a = rag.__aenter__.return_value
    rag_a.count_documents = mock.AsyncMock(return_value=w_count)

    found = await cli_audit._async_count(rag)

    assert found == w_count
    rag_a.count_documents.assert_awaited_once_with()


@pytest.mark.parametrize(
    "w_count, exp_result",
    [
        (0, "0 documents"),
        (5, "5 documents"),
        (None, "boom"),
    ],
)
def test__count_rag_documents(w_count, exp_result):
    rag = mock.AsyncMock()
    rag_a = rag.__aenter__.return_value

    if w_count is None:
        rag_a.count_documents = mock.AsyncMock(
            side_effect=RuntimeError(exp_result),
        )
    else:
        rag_a.count_documents = mock.AsyncMock(return_value=w_count)

    found = cli_audit._count_rag_documents(rag)

    assert found == exp_result
    rag_a.count_documents.assert_awaited_once_with()


@pytest.mark.parametrize(
    "w_room_id_and_error, exp_invalid_ids",
    [
        ([], []),
        ([("r1", False)], []),
        ([("r1", True)], ["r1"]),
        ([("r1", False), ("r2", True)], ["r2"]),
        ([("r1", True), ("r2", True)], ["r1", "r2"]),
    ],
)
@mock.patch("soliplex.models.Room.from_config")
def test__invalid_rooms(
    mrfc,
    the_installation,
    w_room_id_and_error,
    exp_invalid_ids,
):
    room_configs = {}
    side_effects = []
    for room_id, has_error in w_room_id_and_error:
        cfg = mock.Mock()
        cfg.id = room_id
        room_configs[room_id] = cfg
        side_effects.append(ModelException() if has_error else None)

    the_installation._config.room_configs = room_configs
    mrfc.side_effect = side_effects

    found = cli_audit._invalid_rooms(the_installation)

    if exp_invalid_ids:
        assert found == {
            "room": {rid: TESTING_MODEL_ERROR for rid in exp_invalid_ids},
        }
    else:
        assert found == {}

    assert mrfc.call_args_list == [
        mock.call(cfg) for cfg in room_configs.values()
    ]


def _rag_cfg(**attrs):
    cfg = object.__new__(config_rag._RAGConfigBase)
    for k, v in attrs.items():
        setattr(cfg, k, v)
    return cfg


@pytest.mark.parametrize(
    "w_agent_rag, skills_and_rag, tools_and_rag",
    [
        (False, [], []),
        (False, [("s1", False)], [("t1", False)]),
        (True, [], []),
        (False, [("s1", True), ("s2", False)], []),
        (False, [], [("t1", True), ("t2", False)]),
        (
            True,
            [("s1", True), ("s2", False)],
            [("t1", True), ("t2", False)],
        ),
    ],
)
def test__iter_room_rag_candidates(w_agent_rag, skills_and_rag, tools_and_rag):
    room_config = mock.Mock()

    if w_agent_rag:
        room_config.agent_config = _rag_cfg()
    else:
        room_config.agent_config = mock.Mock()

    skill_configs = {
        s_name: _rag_cfg() if is_rag else mock.Mock()
        for s_name, is_rag in skills_and_rag
    }
    skills = mock.Mock()
    skills.skill_configs = skill_configs
    room_config.skills = skills

    tool_configs = {
        t_name: _rag_cfg(tool_name=t_name) if is_rag else mock.Mock()
        for t_name, is_rag in tools_and_rag
    }
    room_config.tool_configs = tool_configs

    found = list(cli_audit._iter_room_rag_candidates(room_config))

    expected = []
    if w_agent_rag:
        expected.append(("agent", room_config.agent_config))
    for s_name, is_rag in skills_and_rag:
        if is_rag:
            expected.append((f"skill:{s_name}", skill_configs[s_name]))
    for t_name, is_rag in tools_and_rag:
        if is_rag:
            expected.append((f"tool:{t_name}", tool_configs[t_name]))

    assert found == expected


def test__iter_room_rag_candidates_skills_none():
    room_config = mock.Mock()
    room_config.agent_config = mock.Mock()
    room_config.skills = None
    room_config.tool_configs = {}

    found = list(cli_audit._iter_room_rag_candidates(room_config))

    assert found == []


@pytest.mark.parametrize(
    "rooms_and_features, registered, exp_errors",
    [
        ([], (), {}),
        ([("r1", ())], (), {}),
        ([("r1", ("a",))], ("a",), {}),
        (
            [("r1", ("a", "missing"))],
            ("a",),
            {"agui_features": {"r1": ["missing"]}},
        ),
        (
            [
                ("r1", ("a", "missing")),
                ("r2", ("a",)),
                ("r3", ("x", "y")),
            ],
            ("a",),
            {
                "agui_features": {
                    "r1": ["missing"],
                    "r3": ["x", "y"],
                },
            },
        ),
    ],
)
def test__invalid_room_agui_features(
    the_installation,
    patched_agui_features,
    rooms_and_features,
    registered,
    exp_errors,
):
    for name in registered:
        patched_agui_features[name] = mock.Mock()

    room_configs = {}
    for room_id, feature_names in rooms_and_features:
        cfg = mock.Mock()
        cfg.id = room_id
        cfg.agui_feature_names = feature_names
        room_configs[room_id] = cfg

    the_installation._config.room_configs = room_configs

    found = cli_audit._invalid_room_agui_features(the_installation)

    assert found == exp_errors


@pytest.mark.parametrize(
    "rooms_and_candidates, exp_errors",
    [
        ([], {}),
        ([("r1", [])], {}),
        ([("r1", [("agent", False)])], {}),
        (
            [("r1", [("agent", True)])],
            {"rag": {"r1": {"agent": TESTING_RAG_ERROR}}},
        ),
        (
            [
                ("r1", [("agent", False), ("tool:t1", True)]),
                ("r2", [("skill:s1", False)]),
                ("r3", [("agent", True)]),
            ],
            {
                "rag": {
                    "r1": {"tool:t1": TESTING_RAG_ERROR},
                    "r3": {"agent": TESTING_RAG_ERROR},
                },
            },
        ),
    ],
)
@mock.patch("soliplex.cli.audit._iter_room_rag_candidates")
def test__invalid_room_rag_dbs(
    iter_candidates,
    the_installation,
    rooms_and_candidates,
    exp_errors,
):
    room_configs = {}
    side_effects = []
    for room_id, candidate_specs in rooms_and_candidates:
        room_cfg = mock.Mock()
        room_cfg.id = room_id
        room_configs[room_id] = room_cfg
        side_effects.append(
            [
                (source, _ErrRagCfg() if has_error else _OkRagCfg())
                for source, has_error in candidate_specs
            ]
        )

    the_installation._config.room_configs = room_configs
    iter_candidates.side_effect = side_effects

    found = cli_audit._invalid_room_rag_dbs(the_installation)

    assert found == exp_errors
    assert iter_candidates.call_args_list == [
        mock.call(rc) for rc in room_configs.values()
    ]


# _audit_rooms_section: ui only
# audit_rooms: command


@pytest.mark.parametrize(
    "w_compl_id_and_error, exp_invalid_ids",
    [
        ([], []),
        ([("c1", False)], []),
        ([("c1", True)], ["c1"]),
        ([("c1", False), ("c2", True)], ["c2"]),
        ([("c1", True), ("c2", True)], ["c1", "c2"]),
    ],
)
@mock.patch("soliplex.models.Completion.from_config")
def test__invalid_completions(
    mcfc,
    the_installation,
    w_compl_id_and_error,
    exp_invalid_ids,
):
    completion_configs = {}
    side_effects = []
    for compl_id, has_error in w_compl_id_and_error:
        cfg = mock.Mock()
        cfg.id = compl_id
        completion_configs[compl_id] = cfg
        side_effects.append(ModelException() if has_error else None)

    the_installation._config.completion_configs = completion_configs
    mcfc.side_effect = side_effects

    found = cli_audit._invalid_completions(the_installation)

    if exp_invalid_ids:
        assert found == {
            "completions": {
                cid: TESTING_MODEL_ERROR for cid in exp_invalid_ids
            },
        }
    else:
        assert found == {}

    assert mcfc.call_args_list == [
        mock.call(cfg) for cfg in completion_configs.values()
    ]


# _audit_completions_section: ui only
# audit_completions: command


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

    found = sorted(
        cli_audit._iter_quiz_configs(the_installation),
        key=lambda t: (str(t[0]), str(t[1])),
    )

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
@mock.patch("soliplex.cli.audit._iter_quiz_configs")
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

    found = cli_audit._invalid_quizzes(the_installation)

    assert found == exp_errors
    iter_quiz_configs.assert_called_once_with(the_installation)


# _audit_quizzes_section: ui only
# audit_quizzes: command


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

    found = list(cli_audit._find_skill_paths(to_search))

    expected = [
        to_search if name == "." else to_search / name for name in exp_yields
    ]

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

    found = cli_audit._invalid_skill_configs(the_installation)

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
@mock.patch("soliplex.cli.audit.skill_validator.validate")
@mock.patch("soliplex.cli.audit._find_skill_paths")
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

    found = cli_audit._invalid_filesystem_skills(the_installation)

    assert found == exp_errors
    assert find_skill_paths.call_args_list == [mock.call(p) for p in fs_paths]


# _audit_skills_section: ui only
# audit_skills: command


_MISSING_FILE = object()


@pytest.mark.parametrize(
    "w_yaml_content, expectation",
    [
        (None, contextlib.nullcontext(None)),
        ("version: 1", contextlib.nullcontext({"version": 1})),
        (
            "a: b\nc: d",
            contextlib.nullcontext({"a": "b", "c": "d"}),
        ),
        ("key: [unclosed", pytest.raises(yaml.YAMLError)),
        (_MISSING_FILE, pytest.raises(FileNotFoundError)),
    ],
)
def test__load_logging_config(
    tmp_path,
    the_installation,
    w_yaml_content,
    expectation,
):
    if w_yaml_content is None:
        the_installation._config.logging_config_file = None
    elif w_yaml_content is _MISSING_FILE:
        the_installation._config.logging_config_file = tmp_path / "nope.yaml"
    else:
        config_file = tmp_path / "logging.yaml"
        config_file.write_text(w_yaml_content)
        the_installation._config.logging_config_file = config_file

    with expectation as expected:
        found = cli_audit._load_logging_config(the_installation)

    if not isinstance(expected, pytest.ExceptionInfo):
        assert found == expected


@pytest.mark.parametrize(
    "w_exc, exp_errors",
    [
        (None, {}),
        (yaml.YAMLError("bad yaml"), {"logging": "bad yaml"}),
        (OSError("missing file"), {"logging": "missing file"}),
    ],
)
@mock.patch("soliplex.cli.audit._load_logging_config")
def test__invalid_logging(
    load_logging_config,
    the_installation,
    w_exc,
    exp_errors,
):
    if w_exc is not None:
        load_logging_config.side_effect = w_exc

    found = cli_audit._invalid_logging(the_installation)

    assert found == exp_errors
    load_logging_config.assert_called_once_with(the_installation)


# _audit_logging_section: ui only
# audit_logging: command


# _audit_logfire_section: ui only
# audit_logfire: command
