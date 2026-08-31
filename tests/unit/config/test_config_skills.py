import copy
import importlib.metadata
import types
from unittest import mock

import pydantic
import pytest
from bubble_sandbox import models as bs_models
from haiku.rag import config as hr_config
from haiku.rag.capabilities import analysis as hr_analysis
from haiku.rag.capabilities import rag as hr_rag

from soliplex.capabilities import filesystem as cap_fs
from soliplex.config import agui as config_agui
from soliplex.config import exceptions as config_exc
from soliplex.config import skills as config_skills
from soliplex.skills import bwrap_sandbox

SKILL_NAME = "test-skill"
FILESYSTEM_SKILL_NAME = SKILL_NAME
SKILL_DESC = "This is a test capability"
SKILL_MODEL_NAME = "removed-skill-model"
SKILL_STATE_NAMESPACE = "removed-skill-state"


# Omitted, explicitly true, and explicitly false: the three states each
# configurable skill kind must carry through to its capability, and back
# out through 'as_yaml'.
def _defer_loading_states(default):
    """The three YAML states, against a kind's own default."""
    return [
        ({}, default),
        ({"defer_loading": True}, True),
        ({"defer_loading": False}, False),
    ]


def _filesystem_capability(path):
    return cap_fs.FilesystemCapability(
        id=path.name,
        description=SKILL_DESC,
        defer_loading=True,
        instructions="Follow these instructions.",
        path=path,
    )


@pytest.fixture
def installation_config(temp_dir):
    config = mock.Mock()
    config.skill_configs = {}
    config.haiku_rag_config = hr_config.AppConfig(environment="testing")
    config.get_environment.return_value = str(temp_dir)
    return config


def test_filesystem_skill_config_properties(temp_dir):
    path = temp_dir / SKILL_NAME
    capability = _filesystem_capability(path)
    config = config_skills.FilesystemSkillConfig.from_capability(capability)

    assert config.capability is capability
    assert config.name == SKILL_NAME
    assert config.description == SKILL_DESC
    assert config.path == path
    assert config.errors == []
    assert config.kind == "filesystem"
    assert config.source is config_skills.SkillKind.FILESYSTEM
    assert config.state_type is None
    assert config.state_namespace is None
    assert config.agui_feature_names == ()
    assert config.extra_parameters == {}


def test_filesystem_skill_config_from_path(temp_dir):
    path = temp_dir / SKILL_NAME
    path.mkdir()
    (path / "SKILL.md").write_text(
        f"---\nname: {SKILL_NAME}\ndescription: {SKILL_DESC}\n---\nDo it."
    )

    config = config_skills.FilesystemSkillConfig.from_path(path)

    assert config.name == SKILL_NAME
    assert config.capability.get_instructions() == "Do it."


def test_filesystem_skill_config_from_invalid_path(temp_dir):
    path = temp_dir / SKILL_NAME
    path.mkdir()
    (path / "SKILL.md").write_text("invalid")

    config = config_skills.FilesystemSkillConfig.from_path(path)

    assert config.name == SKILL_NAME
    assert config.errors
    assert "Invalid filesystem capability" in config.description


@pytest.mark.parametrize(
    "config_class, capability_class, state_namespace",
    [
        (
            config_skills.HR_RAG_SkillConfig,
            hr_rag.RAGCapability,
            hr_rag.STATE_NAMESPACE,
        ),
        (
            config_skills.HR_Analysis_SkillConfig,
            hr_analysis.AnalysisCapability,
            hr_analysis.STATE_NAMESPACE,
        ),
    ],
)
def test_haiku_rag_capability_config(
    temp_dir,
    installation_config,
    config_class,
    capability_class,
    state_namespace,
):
    db_path = temp_dir / "rag.lancedb"
    db_path.mkdir()
    config_path = temp_dir / "room.yaml"
    config = config_class.from_yaml(
        installation_config,
        config_path,
        {
            "kind": config_class.kind,
            "rag_lancedb_override_path": str(db_path),
        },
    )

    capability = config.capability
    assert isinstance(capability, capability_class)
    assert [ref.db_path for ref in capability.scope.databases] == [db_path]
    assert capability.defer_loading is False

    assert config.state_namespace == state_namespace
    assert config.agui_feature_names == (state_namespace,)
    assert state_namespace in config_agui.AGUI_FEATURES_BY_NAME

    assert config.source is config_skills.SkillKind.NATIVE
    assert config.extra_parameters == {"database_names": ["rag"]}
    assert config.rag_lancedb_override_path == db_path
    assert config.as_yaml == {
        "kind": config.kind,
        "rag_lancedb_override_path": str(db_path),
        "defer_loading": False,
    }


def test_haiku_rag_capability_config_with_stem(
    temp_dir,
    installation_config,
):
    db_path = temp_dir / "example.lancedb"
    db_path.mkdir()
    config = config_skills.HR_RAG_SkillConfig(
        rag_lancedb_stem="example",
        _installation_config=installation_config,
    )

    assert config.rag_lancedb_path == db_path
    assert config.as_yaml == {
        "kind": config.kind,
        "rag_lancedb_stem": "example",
        "defer_loading": False,
    }


def _round_trip_hr_skill(
    config_class,
    installation_config,
    config_path,
    config_dict,
):
    """Reload a haiku.rag skill config from its own dump."""
    original = config_class.from_yaml(
        installation_config,
        config_path,
        copy.deepcopy(config_dict),
    )
    reloaded = config_class.from_yaml(
        installation_config,
        config_path,
        copy.deepcopy(original.as_yaml),
    )

    return original, reloaded


@pytest.mark.parametrize(
    "config_class",
    [
        config_skills.HR_RAG_SkillConfig,
        config_skills.HR_Analysis_SkillConfig,
    ],
)
@pytest.mark.parametrize("w_stem", [False, True])
def test_haiku_rag_capability_config_as_yaml_round_trips(
    temp_dir,
    installation_config,
    config_class,
    w_stem,
):
    db_path = temp_dir / "example.lancedb"
    db_path.mkdir()
    config_dict = {"kind": config_class.kind}

    if w_stem:
        config_dict["rag_lancedb_stem"] = "example"
    else:
        # 'from_yaml' parses this into a 'pathlib.Path' and 'as_yaml'
        # stringifies it again.
        config_dict["rag_lancedb_override_path"] = str(db_path)

    original, reloaded = _round_trip_hr_skill(
        config_class,
        installation_config,
        temp_dir / "room.yaml",
        config_dict,
    )

    assert reloaded == original
    assert reloaded.rag_lancedb_path == original.rag_lancedb_path


def test_haiku_rag_capability_config_wraps_yaml_errors(
    installation_config,
    temp_dir,
):
    with pytest.raises(config_exc.FromYamlException):
        config_skills.HR_RAG_SkillConfig.from_yaml(
            installation_config,
            temp_dir / "room.yaml",
            {"kind": config_skills.HR_RAG_SkillConfig.kind},
        )


@pytest.mark.parametrize(
    "w_yaml, exp_defer_loading", _defer_loading_states(False)
)
@pytest.mark.parametrize(
    "config_class",
    [
        config_skills.HR_RAG_SkillConfig,
        config_skills.HR_Analysis_SkillConfig,
    ],
)
def test_haiku_rag_capability_config_defer_loading(
    temp_dir,
    installation_config,
    config_class,
    w_yaml,
    exp_defer_loading,
):
    db_path = temp_dir / "rag.lancedb"
    db_path.mkdir()
    config = config_class.from_yaml(
        installation_config,
        temp_dir / "room.yaml",
        {
            "kind": config_class.kind,
            "rag_lancedb_override_path": str(db_path),
            **w_yaml,
        },
    )

    assert config.defer_loading is exp_defer_loading
    assert config.capability.defer_loading is exp_defer_loading
    assert config.as_yaml["defer_loading"] is exp_defer_loading


def test_bwrap_sandbox_config_registered_kind():
    assert (
        config_skills.SKILL_CONFIG_CLASSES_BY_KIND[
            config_skills.BwrapSandboxSkillConfig.kind
        ]
        is config_skills.BwrapSandboxSkillConfig
    )


def test_bwrap_sandbox_config_registered_bbb_alias_kind():
    assert (
        config_skills.SKILL_CONFIG_CLASSES_BY_KIND["bubble-sandbox"]
        is config_skills.BwrapSandboxSkillConfig
    )


def test_bwrap_sandbox_config_from_yaml(installation_config, temp_dir):
    volume_path = temp_dir / "volume"
    config = config_skills.BwrapSandboxSkillConfig.from_yaml(
        installation_config,
        temp_dir / "room.yaml",
        {
            "kind": bwrap_sandbox.SKILL_PROPERTIES.name,
            "id": "sandbox-id",
            "default_environment": "python",
            "allowed_environments": ["python"],
            "sandbox_config": {"max_output_chars": 1234},
            "volumes": {
                "data": {
                    "host_path": str(volume_path),
                    "writable": False,
                }
            },
        },
    )

    capability = config.capability
    assert isinstance(capability, bwrap_sandbox.SandboxCapability)
    assert capability.id == "sandbox-id"
    assert capability.default_environment == "python"
    assert config.name == bwrap_sandbox.SKILL_PROPERTIES.name
    assert config.description == bwrap_sandbox.SKILL_PROPERTIES.description
    assert config.state_type is None
    assert config.state_namespace is None
    assert config.agui_feature_names == ()
    assert config.extra_parameters == {
        "default_environment": "python",
        "allowed_environments": ["python"],
    }
    assert isinstance(config.volumes["data"], bs_models.VolumeInfo)
    assert config.as_yaml["id"] == "sandbox-id"
    assert config.as_yaml["volumes"]["data"] == {
        "host_path": str(volume_path),
        "writable": False,
    }


def test_bwrap_sandbox_config_minimal(installation_config):
    config = config_skills.BwrapSandboxSkillConfig(
        _installation_config=installation_config
    )

    assert config.as_yaml == {
        "kind": bwrap_sandbox.SKILL_PROPERTIES.name,
        "default_environment": "bare",
        "defer_loading": False,
    }
    assert config.extra_parameters == {"default_environment": "bare"}


def _round_trip_bwrap_skill(installation_config, config_path, config_dict):
    """Reload a 'BwrapSandboxSkillConfig' from its own dump."""
    klass = config_skills.BwrapSandboxSkillConfig
    original = klass.from_yaml(
        installation_config,
        config_path,
        copy.deepcopy(config_dict),
    )
    reloaded = klass.from_yaml(
        installation_config,
        config_path,
        copy.deepcopy(original.as_yaml),
    )

    return original, reloaded


@pytest.mark.parametrize("w_full", [False, True])
def test_bwrap_sandbox_config_as_yaml_round_trips(
    installation_config,
    temp_dir,
    w_full,
):
    config_dict = {"kind": bwrap_sandbox.SKILL_PROPERTIES.name}

    if w_full:
        config_dict |= {
            "id": "sandbox-id",
            "default_environment": "python",
            "allowed_environments": ["python"],
            "sandbox_config": {
                "environments_pathname": "test-environments",
                "execution_timeout_seconds": 66.0,
                "max_output_chars": 1234,
            },
            "volumes": {
                "data": {
                    "host_path": str(temp_dir / "volume"),
                    "writable": False,
                },
            },
        }

    original, reloaded = _round_trip_bwrap_skill(
        installation_config,
        temp_dir / "room.yaml",
        config_dict,
    )

    assert reloaded == original
    assert reloaded.extra_parameters == original.extra_parameters


def test_bwrap_sandbox_config_wraps_yaml_errors(
    installation_config,
    temp_dir,
):
    with pytest.raises(config_exc.FromYamlException):
        config_skills.BwrapSandboxSkillConfig.from_yaml(
            installation_config,
            temp_dir / "room.yaml",
            {
                "kind": bwrap_sandbox.SKILL_PROPERTIES.name,
                "volumes": {"data": {"unknown": True}},
            },
        )


@pytest.mark.parametrize(
    "w_yaml, exp_defer_loading", _defer_loading_states(False)
)
def test_bwrap_sandbox_config_defer_loading(
    installation_config,
    temp_dir,
    w_yaml,
    exp_defer_loading,
):
    config = config_skills.BwrapSandboxSkillConfig.from_yaml(
        installation_config,
        temp_dir / "room.yaml",
        {"kind": bwrap_sandbox.SKILL_PROPERTIES.name, **w_yaml},
    )

    assert config.defer_loading is exp_defer_loading
    assert config.capability.defer_loading is exp_defer_loading
    assert config.as_yaml["defer_loading"] is exp_defer_loading


def test_extract_skill_configs(installation_config, temp_dir):
    db_path = temp_dir / "rag.lancedb"
    db_path.mkdir()
    config_dict = {
        "skill_configs": [
            {
                "kind": config_skills.HR_RAG_SkillConfig.kind,
                "rag_lancedb_override_path": str(db_path),
            },
            {"kind": bwrap_sandbox.SKILL_PROPERTIES.name},
        ]
    }

    found = config_skills.extract_skill_configs(
        installation_config,
        temp_dir / "room.yaml",
        config_dict,
    )

    assert set(found) == {"rag", bwrap_sandbox.SKILL_PROPERTIES.name}
    assert config_dict == {}


def test_extract_skill_configs_rejects_unknown_kind(
    installation_config,
    temp_dir,
):
    with pytest.raises(config_skills.InvalidSkillKind) as raised:
        config_skills.extract_skill_configs(
            installation_config,
            temp_dir / "room.yaml",
            {"skill_configs": [{"kind": "unknown"}]},
        )

    assert raised.value.invalid_skill_kind == "unknown"


def test_room_skills_config_rejects_missing_installation_capability(
    installation_config,
    temp_dir,
):
    with pytest.raises(config_exc.FromYamlException) as raised:
        config_skills.RoomSkillsConfig.from_yaml(
            installation_config,
            temp_dir / "room.yaml",
            {"installation_skill_names": ["missing"]},
        )

    assert isinstance(raised.value.__cause__, config_skills.MissingSkillNames)


def test_room_skills_config_combines_capabilities(
    installation_config,
    temp_dir,
):
    fs_path = temp_dir / SKILL_NAME
    filesystem = config_skills.FilesystemSkillConfig.from_capability(
        _filesystem_capability(fs_path)
    )
    installation_config.skill_configs = {SKILL_NAME: filesystem}
    db_path = temp_dir / "rag.lancedb"
    db_path.mkdir()

    config = config_skills.RoomSkillsConfig.from_yaml(
        installation_config,
        temp_dir / "room.yaml",
        {
            "installation_skill_names": [SKILL_NAME],
            "skill_configs": [
                {
                    "kind": config_skills.HR_RAG_SkillConfig.kind,
                    "rag_lancedb_override_path": str(db_path),
                },
                {"kind": bwrap_sandbox.SKILL_PROPERTIES.name},
            ],
        },
    )

    assert set(config.skill_configs) == {
        SKILL_NAME,
        "rag",
        bwrap_sandbox.SKILL_PROPERTIES.name,
    }
    assert len(config.capabilities) == 3
    assert config.rag_db_paths == {"haiku-rag": str(db_path)}
    assert config.has_sandbox is True
    assert config.as_yaml["installation_skill_names"] == [
        {"name": SKILL_NAME, "defer_loading": True},
    ]
    hrsc_yaml, bws_yaml = config.as_yaml["skill_configs"]
    assert hrsc_yaml == {
        "kind": config_skills.HR_RAG_SkillConfig.kind,
        "rag_lancedb_override_path": str(db_path),
        "defer_loading": False,
    }
    assert bws_yaml == {
        "kind": bwrap_sandbox.SKILL_PROPERTIES.name,
        "default_environment": "bare",
        "sandbox_config": {
            "environments_pathname": "environments",
            "execution_timeout_seconds": 30.0,
            "max_output_chars": 100000,
        },
        "defer_loading": False,
    }


@pytest.mark.parametrize(
    "w_entry",
    [
        SKILL_NAME,
        {"name": SKILL_NAME},
        config_skills.InstallationSkillRef(name=SKILL_NAME),
    ],
    ids=["bare-name", "mapping", "ref"],
)
def test_room_skills_config_ctor_normalizes_installation_skill_names(
    installation_config,
    temp_dir,
    w_entry,
):
    filesystem = config_skills.FilesystemSkillConfig.from_capability(
        _filesystem_capability(temp_dir / SKILL_NAME)
    )
    installation_config.skill_configs = {SKILL_NAME: filesystem}

    config = config_skills.RoomSkillsConfig(
        installation_skill_names=[w_entry],
        _installation_config=installation_config,
    )

    assert config.installation_skill_names == [
        config_skills.InstallationSkillRef(name=SKILL_NAME),
    ]
    assert config.skill_configs == {SKILL_NAME: filesystem}


def test_empty_room_skills_config(installation_config):
    config = config_skills.RoomSkillsConfig(
        _installation_config=installation_config
    )

    assert config.as_yaml == {}
    assert config.skill_configs == {}
    assert config.capabilities == []
    assert config.rag_db_paths == {}
    assert config.has_sandbox is False


def _round_trip_room_skills(installation_config, config_path, config_dict):
    """Reload a 'RoomSkillsConfig' from its own dump.

    'from_yaml' drains 'skill_configs' out of the mapping it is handed
    (via 'extract_skill_configs'), hence the copies.
    """
    klass = config_skills.RoomSkillsConfig
    original = klass.from_yaml(
        installation_config,
        config_path,
        copy.deepcopy(config_dict),
    )
    reloaded = klass.from_yaml(
        installation_config,
        config_path,
        copy.deepcopy(original.as_yaml),
    )

    return original, reloaded


@pytest.mark.parametrize("w_installation_skills", [False, True])
def test_room_skills_config_as_yaml_round_trips(
    installation_config,
    temp_dir,
    w_installation_skills,
):
    filesystem = config_skills.FilesystemSkillConfig.from_capability(
        _filesystem_capability(temp_dir / SKILL_NAME)
    )
    installation_config.skill_configs = {SKILL_NAME: filesystem}
    db_path = temp_dir / "rag.lancedb"
    db_path.mkdir()
    config_dict = {
        "skill_configs": [
            {
                "kind": config_skills.HR_RAG_SkillConfig.kind,
                "rag_lancedb_override_path": str(db_path),
            },
            {"kind": bwrap_sandbox.SKILL_PROPERTIES.name},
        ],
    }

    if w_installation_skills:
        config_dict["installation_skill_names"] = [SKILL_NAME]

    original, reloaded = _round_trip_room_skills(
        installation_config,
        temp_dir / "room.yaml",
        config_dict,
    )

    assert reloaded == original
    assert reloaded.skill_configs == original.skill_configs
    assert reloaded.rag_db_paths == original.rag_db_paths
    assert reloaded.has_sandbox == original.has_sandbox


class _FakeEntryPoint:
    def __init__(self, name, target):
        self.name = name
        self._target = target

    def load(self):
        return self._target


class _FakeState(pydantic.BaseModel):
    pass


def _stateful_module():
    return types.SimpleNamespace(
        STATE_NAMESPACE="entrypoint-test",
        STATE_TYPE=_FakeState,
        DESCRIPTION="A test capability",
        create_capability=lambda defer_loading, **params: {
            "defer_loading": defer_loading,
            "params": params,
        },
    )


def _stateless_module():
    return types.SimpleNamespace(
        create_capability=lambda defer_loading, **params: {
            "defer_loading": defer_loading,
            "params": params,
        },
    )


def _patch_entry_points(monkeypatch, mapping):
    eps = [_FakeEntryPoint(name, target) for name, target in mapping.items()]
    monkeypatch.setattr(importlib.metadata, "entry_points", lambda group: eps)


def test_entrypoint_capability_registered_kind():
    assert (
        config_skills.SKILL_CONFIG_CLASSES_BY_KIND["entrypoint"]
        is config_skills.EntrypointCapabilityConfig
    )


def test_entrypoint_capability_config_stateful(
    monkeypatch, installation_config, temp_dir
):
    _patch_entry_points(monkeypatch, {"my-cap": _stateful_module()})
    config = config_skills.EntrypointCapabilityConfig.from_yaml(
        installation_config,
        temp_dir / "room.yaml",
        {"kind": "entrypoint", "name": "my-cap", "foo": "bar"},
    )

    assert config.name == "my-cap"
    assert config.description == "A test capability"
    assert config.state_namespace == "entrypoint-test"
    assert config.state_type is _FakeState
    assert config.agui_feature_names == ("entrypoint-test",)
    assert config.source is config_skills.SkillKind.ENTRYPOINT
    assert config.extra_parameters == {"foo": "bar"}
    assert config.as_yaml == {
        "kind": "entrypoint",
        "name": "my-cap",
        "foo": "bar",
        "defer_loading": True,
    }
    assert config.capability == {
        "defer_loading": True,
        "params": {"foo": "bar"},
    }
    assert "entrypoint-test" in config_agui.AGUI_FEATURES_BY_NAME


def test_entrypoint_capability_config_stateless(
    monkeypatch, installation_config, temp_dir
):
    _patch_entry_points(monkeypatch, {"plain": _stateless_module()})
    config = config_skills.EntrypointCapabilityConfig.from_yaml(
        installation_config,
        temp_dir / "room.yaml",
        {"kind": "entrypoint", "name": "plain"},
    )

    assert config.description == ""
    assert config.state_namespace is None
    assert config.state_type is None
    assert config.agui_feature_names == ()
    assert config.extra_parameters == {}
    assert config.capability == {"defer_loading": True, "params": {}}


def _round_trip_entrypoint_skill(
    installation_config,
    config_path,
    config_dict,
):
    """Reload an 'EntrypointCapabilityConfig' from its own dump."""
    klass = config_skills.EntrypointCapabilityConfig
    original = klass.from_yaml(
        installation_config,
        config_path,
        copy.deepcopy(config_dict),
    )
    reloaded = klass.from_yaml(
        installation_config,
        config_path,
        copy.deepcopy(original.as_yaml),
    )

    return original, reloaded


@pytest.mark.parametrize("w_params", [{}, {"foo": "bar"}])
def test_entrypoint_capability_config_as_yaml_round_trips(
    monkeypatch,
    installation_config,
    temp_dir,
    w_params,
):
    _patch_entry_points(monkeypatch, {"my-cap": _stateful_module()})
    config_dict = {"kind": "entrypoint", "name": "my-cap"} | w_params

    original, reloaded = _round_trip_entrypoint_skill(
        installation_config,
        temp_dir / "room.yaml",
        config_dict,
    )

    assert reloaded == original
    assert reloaded.extra_parameters == original.extra_parameters


def test_entrypoint_capability_config_unknown_entry_point(
    monkeypatch, installation_config, temp_dir
):
    _patch_entry_points(monkeypatch, {"other": _stateless_module()})
    with pytest.raises(config_exc.FromYamlException) as raised:
        config_skills.EntrypointCapabilityConfig.from_yaml(
            installation_config,
            temp_dir / "room.yaml",
            {"kind": "entrypoint", "name": "missing"},
        )

    assert isinstance(
        raised.value.__cause__, config_skills.UnknownCapabilityEntryPoint
    )


@pytest.mark.parametrize(
    "w_yaml, exp_defer_loading", _defer_loading_states(True)
)
def test_entrypoint_capability_config_defer_loading(
    monkeypatch,
    installation_config,
    temp_dir,
    w_yaml,
    exp_defer_loading,
):
    _patch_entry_points(monkeypatch, {"my-cap": _stateless_module()})
    config = config_skills.EntrypointCapabilityConfig.from_yaml(
        installation_config,
        temp_dir / "room.yaml",
        {"kind": "entrypoint", "name": "my-cap", "foo": "bar", **w_yaml},
    )

    assert config.defer_loading is exp_defer_loading
    # The flag is Soliplex's, not the plugin's:  it reaches
    # 'create_capability' as its own argument, never as a parameter.
    assert config.params == {"foo": "bar"}
    assert config.capability == {
        "defer_loading": exp_defer_loading,
        "params": {"foo": "bar"},
    }
    assert config.as_yaml["defer_loading"] is exp_defer_loading


@pytest.mark.parametrize(
    "klass, exp_kind, exp_namespace",
    [
        (
            config_skills.HR_EvidenceCompaction_SkillConfig,
            "haiku.rag.skills.evidence_compaction",
            None,
        ),
        (
            config_skills.HR_CitationPolicy_SkillConfig,
            "haiku.rag.skills.citation_policy",
            "citation_policy",
        ),
    ],
)
def test_haiku_rag_evidence_skill_config(
    installation_config,
    temp_dir,
    klass,
    exp_kind,
    exp_namespace,
):
    """The evidence capabilities configure nothing and advertise themselves."""
    config = klass.from_yaml(
        installation_config,
        temp_dir / "room_config.yaml",
        {"kind": exp_kind},
    )

    assert klass.kind == exp_kind
    assert config.source == config_skills.SkillKind.NATIVE
    assert config.state_namespace == exp_namespace
    assert config.as_yaml == {"kind": exp_kind}
    assert config.extra_parameters == {}

    # A namespace a client can read is advertised as a feature; a
    # capability which owns none advertises nothing.
    if exp_namespace is None:
        assert config.agui_feature_names == ()
        assert exp_namespace not in config_agui.AGUI_FEATURES_BY_NAME
    else:
        assert config.agui_feature_names == (exp_namespace,)
        assert exp_namespace in config_agui.AGUI_FEATURES_BY_NAME

    capability = config.capability

    assert capability.id == config.capability_id


@pytest.mark.parametrize(
    "klass",
    [
        config_skills.HR_EvidenceCompaction_SkillConfig,
        config_skills.HR_CitationPolicy_SkillConfig,
    ],
)
def test_haiku_rag_evidence_skill_config_wraps_yaml_errors(
    installation_config, temp_dir, klass
):
    with pytest.raises(config_exc.FromYamlException):
        klass.from_yaml(
            installation_config,
            temp_dir / "room_config.yaml",
            {"kind": klass.kind, "bogus": "nonesuch"},
        )


@pytest.mark.parametrize(
    "w_entry, exp_name, exp_defer_loading",
    [
        (SKILL_NAME, SKILL_NAME, True),
        ({"name": SKILL_NAME}, SKILL_NAME, True),
        ({"name": SKILL_NAME, "defer_loading": True}, SKILL_NAME, True),
        ({"name": SKILL_NAME, "defer_loading": False}, SKILL_NAME, False),
    ],
)
def test_installation_skill_ref_from_yaml(
    w_entry,
    exp_name,
    exp_defer_loading,
):
    ref = config_skills.InstallationSkillRef.from_yaml(w_entry)

    assert ref.name == exp_name
    assert ref.defer_loading is exp_defer_loading


@pytest.mark.parametrize(
    "w_defer_loading, exp_yaml",
    [
        (True, {"name": SKILL_NAME, "defer_loading": True}),
        (False, {"name": SKILL_NAME, "defer_loading": False}),
    ],
)
def test_installation_skill_ref_as_yaml(w_defer_loading, exp_yaml):
    ref = config_skills.InstallationSkillRef(
        name=SKILL_NAME,
        defer_loading=w_defer_loading,
    )

    assert ref.as_yaml == exp_yaml


@pytest.mark.parametrize("w_defer_loading", [True, False])
def test_room_skills_config_installation_skill_defer_loading(
    installation_config,
    temp_dir,
    w_defer_loading,
):
    filesystem = config_skills.FilesystemSkillConfig.from_capability(
        _filesystem_capability(temp_dir / SKILL_NAME)
    )
    installation_config.skill_configs = {SKILL_NAME: filesystem}

    config = config_skills.RoomSkillsConfig.from_yaml(
        installation_config,
        temp_dir / "room.yaml",
        {
            "installation_skill_names": [
                {"name": SKILL_NAME, "defer_loading": w_defer_loading},
            ],
        },
    )

    (capability,) = config.capabilities
    assert capability.defer_loading is w_defer_loading

    # Installation skill configs are shared between rooms:  a room's
    # choice is a copy, never a write to the discovered capability.
    assert filesystem.capability.defer_loading is True
    if w_defer_loading:
        assert capability is filesystem.capability
    else:
        assert capability is not filesystem.capability


@pytest.mark.parametrize(
    "w_entry, exp_cause",
    [
        ({"nombre": SKILL_NAME}, TypeError),
        ({"defer_loading": False}, TypeError),
        ({"name": "missing"}, config_skills.MissingSkillNames),
    ],
)
def test_room_skills_config_rejects_bad_installation_skill_entry(
    installation_config,
    temp_dir,
    w_entry,
    exp_cause,
):
    filesystem = config_skills.FilesystemSkillConfig.from_capability(
        _filesystem_capability(temp_dir / SKILL_NAME)
    )
    installation_config.skill_configs = {SKILL_NAME: filesystem}

    with pytest.raises(config_exc.FromYamlException) as raised:
        config_skills.RoomSkillsConfig.from_yaml(
            installation_config,
            temp_dir / "room.yaml",
            {"installation_skill_names": [w_entry]},
        )

    assert isinstance(raised.value.__cause__, exp_cause)
