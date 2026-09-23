from __future__ import annotations

from unittest import mock

import pytest

from soliplex.cli.audit import rooms as audit_rooms
from soliplex.config import rag as config_rag
from tests.unit.cli.audit import audit_helpers

TESTING_RAG_ERROR = "testing rag error"


class RAGError(ValueError):
    def __init__(self):
        super().__init__(TESTING_RAG_ERROR)


class _OkRagCfg:
    haiku_rag_config = None
    rag_databases = ()
    rag_lancedb_path = None


class _ErrRagCfg:
    haiku_rag_config = None
    rag_databases = ()

    @property
    def rag_lancedb_path(self):
        raise RAGError()


class _NoDbRagCfg:
    """Exposes a haiku-rag config but names no database at all"""

    haiku_rag_config = None


class _DeferringRagCfg(_ErrRagCfg):
    """Leaves placement to its haiku.rag config, so has no path to probe"""

    names_own_databases = False


TESTING_RAG_UNBUILDABLE = (
    "lancedb.uri is not a thing; write lancedb.databases: {NAME: <location>}"
)


class _UnbuildableRagCfg(_ErrRagCfg):
    """A config whose haiku.rag configuration will not load

    Its database also fails to resolve, and only one of the two is the
    diagnosis an operator can act on.
    """

    @property
    def haiku_rag_config(self):
        raise ValueError(TESTING_RAG_UNBUILDABLE)


class _MultiRagCfg:
    """Names two databases, the second of which cannot be resolved"""

    class _Papers(_OkRagCfg):
        name = "papers"

    class _Wiki(_ErrRagCfg):
        name = "wiki"

    haiku_rag_config = None
    rag_databases = (_Papers(), _Wiki())


@pytest.mark.parametrize("w_count", [0, 5])
@pytest.mark.anyio
async def test__async_count(w_count):
    rag = mock.AsyncMock()
    rag_a = rag.__aenter__.return_value
    rag_a.count_documents = mock.AsyncMock(return_value=w_count)

    found = await audit_rooms._async_count(rag)

    assert found == w_count
    rag_a.count_documents.assert_awaited_once_with()


@pytest.mark.parametrize(
    "w_count, exp_result",
    [
        (0, ("0 documents", None)),
        (5, ("5 documents", None)),
        (None, ("ERROR: boom", "boom")),
    ],
)
def test__count_rag_documents(w_count, exp_result):
    rag = mock.AsyncMock()
    rag_a = rag.__aenter__.return_value

    if w_count is None:
        rag_a.count_documents = mock.AsyncMock(
            side_effect=RuntimeError("boom"),
        )
    else:
        rag_a.count_documents = mock.AsyncMock(return_value=w_count)

    found = audit_rooms._count_rag_documents(rag)

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
        side_effects.append(
            audit_helpers.ModelException() if has_error else None
        )

    the_installation._config.room_configs = room_configs
    mrfc.side_effect = side_effects

    found = audit_rooms._invalid_rooms(the_installation)

    if exp_invalid_ids:
        assert found == {
            "room": {
                rid: audit_helpers.TESTING_MODEL_ERROR
                for rid in exp_invalid_ids
            },
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

    found = list(audit_rooms._iter_room_rag_candidates(room_config))

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

    found = list(audit_rooms._iter_room_rag_candidates(room_config))

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

    found = audit_rooms._invalid_room_agui_features(the_installation)

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
@mock.patch("soliplex.cli.audit.rooms._iter_room_rag_candidates")
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

    found = audit_rooms._invalid_room_rag_dbs(the_installation)

    assert found == exp_errors
    assert iter_candidates.call_args_list == [
        mock.call(rc) for rc in room_configs.values()
    ]


@mock.patch("soliplex.cli.audit.rooms._iter_room_rag_candidates")
def test__invalid_room_rag_dbs_w_rag_databases(
    iter_candidates,
    the_installation,
):
    """Each named database is probed and reported under its own name"""
    room_cfg = mock.Mock()
    room_cfg.id = "r1"
    the_installation._config.room_configs = {"r1": room_cfg}
    iter_candidates.side_effect = [[("skill:rag", _MultiRagCfg())]]

    found = audit_rooms._invalid_room_rag_dbs(the_installation)

    assert found == {"rag": {"r1": {"skill:rag#wiki": TESTING_RAG_ERROR}}}


@mock.patch("soliplex.cli.audit.rooms._iter_room_rag_candidates")
def test__invalid_room_rag_dbs_wo_database(
    iter_candidates,
    the_installation,
):
    """A config naming no database is reported, not raised at the caller"""
    room_cfg = mock.Mock()
    room_cfg.id = "r1"
    the_installation._config.room_configs = {"r1": room_cfg}
    iter_candidates.side_effect = [[("skill:rag", _NoDbRagCfg())]]

    found = audit_rooms._invalid_room_rag_dbs(the_installation)

    assert "rag_lancedb_path" in found["rag"]["r1"]["skill:rag"]


@mock.patch("soliplex.cli.audit.rooms._iter_room_rag_candidates")
def test__invalid_room_rag_dbs_w_deferred_database(
    iter_candidates,
    the_installation,
):
    """A config placing no database of its own has no path to probe"""
    room_cfg = mock.Mock()
    room_cfg.id = "r1"
    the_installation._config.room_configs = {"r1": room_cfg}
    iter_candidates.side_effect = [[("skill:rag", _DeferringRagCfg())]]

    assert audit_rooms._invalid_room_rag_dbs(the_installation) == {}


@mock.patch("soliplex.cli.audit.rooms._iter_room_rag_candidates")
def test__invalid_room_rag_dbs_w_unbuildable_config(
    iter_candidates,
    the_installation,
):
    """A config that will not build reports that, not its unresolved path

    Its path fails to resolve as well, but naming the missing file sends
    the operator to create it, which is not the fix.
    """
    room_cfg = mock.Mock()
    room_cfg.id = "r1"
    the_installation._config.room_configs = {"r1": room_cfg}
    iter_candidates.side_effect = [[("skill:rag", _UnbuildableRagCfg())]]

    found = audit_rooms._invalid_room_rag_dbs(the_installation)

    (reported,) = found["rag"]["r1"].values()
    assert reported == TESTING_RAG_UNBUILDABLE
    assert TESTING_RAG_ERROR not in reported
    assert list(found["rag"]["r1"]) == ["skill:rag"]


# _audit_rooms_section: ui only
# audit_rooms: command
