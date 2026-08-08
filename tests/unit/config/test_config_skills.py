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
    assert config.license is None
    assert config.compatibility is None
    assert config.allowed_tools == []
    assert config.metadata == {}
    assert config.extra_parameters == {"path": path}


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
    assert capability.db_path == db_path
    assert capability.defer_loading is True
    assert config.agui_feature_names == (state_namespace,)
    assert config.source is config_skills.SkillKind.NATIVE
    assert config.license is None
    assert config.compatibility is None
    assert config.allowed_tools == []
    assert config.metadata == {}
    assert config.extra_parameters == {"rag_lancedb_path": db_path}
    assert config.rag_lancedb_override_path == db_path
    assert config.as_yaml == {
        "kind": config.kind,
        "rag_lancedb_override_path": str(db_path),
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
    }


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


def test_bwrap_sandbox_config_from_yaml(installation_config, temp_dir):
    volume_path = temp_dir / "volume"
    config = config_skills.BwrapSandboxSkillConfig.from_yaml(
        installation_config,
        temp_dir / "room.yaml",
        {
            "kind": bwrap_sandbox.CAPABILITY_NAME,
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
    assert config.name == bwrap_sandbox.CAPABILITY_NAME
    assert config.description
    assert config.state_type is None
    assert config.state_namespace is None
    assert config.agui_feature_names == ()
    assert config.license is None
    assert config.compatibility is None
    assert config.allowed_tools == []
    assert config.metadata == {}
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
        "kind": bwrap_sandbox.CAPABILITY_NAME,
        "default_environment": "bare",
    }
    assert config.extra_parameters == {"default_environment": "bare"}


def test_bwrap_sandbox_config_wraps_yaml_errors(
    installation_config,
    temp_dir,
):
    with pytest.raises(config_exc.FromYamlException):
        config_skills.BwrapSandboxSkillConfig.from_yaml(
            installation_config,
            temp_dir / "room.yaml",
            {
                "kind": bwrap_sandbox.CAPABILITY_NAME,
                "volumes": {"data": {"unknown": True}},
            },
        )


def test_extract_skill_configs(installation_config, temp_dir):
    db_path = temp_dir / "rag.lancedb"
    db_path.mkdir()
    config_dict = {
        "skill_configs": [
            {
                "kind": config_skills.HR_RAG_SkillConfig.kind,
                "rag_lancedb_override_path": str(db_path),
            },
            {"kind": bwrap_sandbox.CAPABILITY_NAME},
        ]
    }

    found = config_skills.extract_skill_configs(
        installation_config,
        temp_dir / "room.yaml",
        config_dict,
    )

    assert set(found) == {"rag", bwrap_sandbox.CAPABILITY_NAME}
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
                {"kind": bwrap_sandbox.CAPABILITY_NAME},
            ],
        },
    )

    assert set(config.skill_configs) == {
        SKILL_NAME,
        "rag",
        bwrap_sandbox.CAPABILITY_NAME,
    }
    assert len(config.capabilities) == 3
    assert config.rag_db_paths == {"haiku-rag": str(db_path)}
    assert config.has_sandbox is True
    assert config.as_yaml["installation_skill_names"] == [SKILL_NAME]
    assert len(config.as_yaml["skill_configs"]) == 2


def test_empty_room_skills_config(installation_config):
    config = config_skills.RoomSkillsConfig(
        _installation_config=installation_config
    )

    assert config.as_yaml == {}
    assert config.skill_configs == {}
    assert config.capabilities == []
    assert config.rag_db_paths == {}
    assert config.has_sandbox is False


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
    assert config.license is None
    assert config.compatibility is None
    assert config.allowed_tools == []
    assert config.metadata == {}
    assert config.extra_parameters == {"foo": "bar"}
    assert config.as_yaml == {
        "kind": "entrypoint",
        "name": "my-cap",
        "foo": "bar",
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
