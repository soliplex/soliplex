import contextlib
import dataclasses
import warnings
from unittest import mock

import pydantic
import pytest
import yaml
from bubble_sandbox import config as bs_config
from bubble_sandbox import models as bs_models
from haiku.rag import config as hr_config
from haiku.rag.skills import analysis as hr_skills_analysis
from haiku.rag.skills import rag as hr_skills_rag
from haiku.skills import models as hs_models
from pydantic_ai.models import openai as openai_models
from pydantic_ai.providers import ollama as ollama_providers

from soliplex.config import agents as config_agents
from soliplex.config import exceptions as config_exc
from soliplex.config import installation as config_installation
from soliplex.config import skills as config_skills
from soliplex.skills import bwrap_sandbox as sk_bwrap_sandbox

SKILL_NAME = "test-skill"
FILESYSTEM_SKILL_NAME = "test-fs-skill"
ENTRYPOINT_SKILL_NAME = "test-ep-skill"
SKILL_DESC = "Skill description"
SKILL_LICENSE = "Skill license"
SKILL_COMPAT = "Skill compatibility"
TOOL_ONE = "tool-one"
TOOL_TWO = "tool-two"
SKILL_ALLOWED_TOOLS = f"{TOOL_ONE} {TOOL_TWO}"
SKILL_AUTHOR = "phreddy@example.com"
SKILL_VERSION = "0.0.1"
SKILL_METADATA = {
    "author": SKILL_AUTHOR,
    "version": SKILL_VERSION,
}
DOMAIN_PREAMBLE = "test domain preamble"

BARE_SKILL_MD_KW = {
    "name": SKILL_NAME,
    "description": SKILL_DESC,
}
BARE_SKILL_MD_YAML = f"""\
---
name: {SKILL_NAME}
description: {SKILL_DESC}
---
"""

FULL_SKILL_MD_KW = {
    "name": SKILL_NAME,
    "description": SKILL_DESC,
    "license": SKILL_LICENSE,
    "compatibility": SKILL_COMPAT,
    "allowed_tools": SKILL_ALLOWED_TOOLS,
    "metadata": {
        "author": SKILL_AUTHOR,
        "version": SKILL_VERSION,
    },
}
FULL_SKILL_MD_YAML = f"""\
---
name: "{SKILL_NAME}"
description: "{SKILL_DESC}"
license: "{SKILL_LICENSE}"
compatibility: "{SKILL_COMPAT}"
allowed-tools: "{SKILL_ALLOWED_TOOLS}"
metadata:
    author: "{SKILL_AUTHOR}"
    version: "{SKILL_VERSION}"
---
"""

SKILL_MODEL_NAME = "test-skill-model"
SKILL_PATH = f"/path/to/skills/{SKILL_NAME}"
SKILL_STATE_NAMESPACE = "test-skill-namespace"
SKILL_VALIDATION_ERROR = "Test skill validation error"
SKILL_TYPE_NAMESPACE = "test-skill-namespace"

BOGUS_ROOM_SKILLS_CONFIG_YAML = ""

ROOM_SKILLS_MODEL_NAME = "test-roomskills-model"
BARE_ROOM_SKILLS_CONFIG_KW = {
    "model_name": ROOM_SKILLS_MODEL_NAME,
}
BARE_ROOM_SKILLS_CONFIG_YAML = f"""\
model_name: "{ROOM_SKILLS_MODEL_NAME}"
"""

W_INSTALLATION_SKILLS_ROOM_SKILLS_CONFIG_KW = {
    "model_name": ROOM_SKILLS_MODEL_NAME,
    "installation_skill_names": [SKILL_NAME],
}
W_INSTALLATION_SKILLS_ROOM_SKILLS_CONFIG_YAML = f"""\
model_name: "{ROOM_SKILLS_MODEL_NAME}"
installation_skill_names:
    - "{SKILL_NAME}"
"""
W_MISSING_INSTALLATION_SKILLS_ROOM_SKILLS_CONFIG_KW = {
    "model_name": ROOM_SKILLS_MODEL_NAME,
    "installation_skill_names": ["bogus"],
}
W_MISSING_INSTALLATION_SKILLS_ROOM_SKILLS_CONFIG_YAML = f"""\
model_name: "{ROOM_SKILLS_MODEL_NAME}"
installation_skill_names:
    - "bogus"
"""

TEST_ROOM_ID = "test_room_id"
TEST_THREAD_ID = "test_thread_id"
TEST_RUN_ID = "test_run_id"


@pytest.fixture
def derived_skillconfigmodel_klass():
    class TestSkillConfigModel(config_skills._SkillConfigModelBase):
        pass

    return TestSkillConfigModel


@pytest.fixture
def model_agent_config():
    return mock.create_autospec(config_agents.AgentConfig)


@pytest.fixture
def openai_test_model():
    provider = ollama_providers.OllamaProvider(
        base_url="http://ollama.example.com:11434",
        api_key="dummy",
    )
    return openai_models.OpenAIChatModel(
        model_name="test-model",
        provider=provider,
    )


USE_MODEL_AGENT_CONFIG = object()
GMFC_RETURN_VALUE = object()


@pytest.mark.parametrize(
    "ctor_kwargs, expectation",
    [
        ({}, contextlib.nullcontext(None)),
        (
            {"model_name": SKILL_MODEL_NAME},
            contextlib.nullcontext(SKILL_MODEL_NAME),
        ),
        (
            {"agent_config": USE_MODEL_AGENT_CONFIG},
            contextlib.nullcontext(GMFC_RETURN_VALUE),
        ),
        (
            {
                "model_name": SKILL_MODEL_NAME,
                "agent_config": USE_MODEL_AGENT_CONFIG,
            },
            pytest.raises(config_skills.OnlyOneOfModelNameAgentConfig),
        ),
    ],
)
@mock.patch("soliplex.config.agents.get_model_from_config")
def test_derivedskillconfigmodel_model_or_name(
    gmfc,
    derived_skillconfigmodel_klass,
    model_agent_config,
    ctor_kwargs,
    expectation,
):
    if "agent_config" in ctor_kwargs:
        ctor_kwargs |= {"agent_config": model_agent_config}

    with expectation as expected:
        derived = derived_skillconfigmodel_klass(**ctor_kwargs)

        found = derived.model_or_name

    if not isinstance(expected, pytest.ExceptionInfo):
        if "agent_config" in ctor_kwargs:
            assert found is gmfc.return_value
            gmfc.assert_called_once_with(agent_config=model_agent_config)
        else:
            assert found == expected
            gmfc.assert_not_called()


def test_derivedskillconfigmodel_extra_parameters(
    derived_skillconfigmodel_klass,
):
    derived = derived_skillconfigmodel_klass()

    assert derived.extra_parameters == {}


class SkillTypeTest(pydantic.BaseModel):
    pass


@pytest.fixture
def skill_path(temp_dir):
    path = temp_dir / "skills" / SKILL_NAME
    path.mkdir(parents=True)
    return path


@pytest.mark.parametrize(
    "w_metadata_kw, exp_allowed_tools",
    [
        ({"name": SKILL_NAME, "description": SKILL_DESC}, []),
        (
            {
                "name": SKILL_NAME,
                "description": SKILL_DESC,
                "license": SKILL_LICENSE,
                "compatibility": SKILL_COMPAT,
                "allowed_tools": [TOOL_ONE, TOOL_TWO],
                "metadata": SKILL_METADATA,
            },
            [TOOL_ONE, TOOL_TWO],
        ),
        (  # XXX See: https://github.com/ggozad/haiku.skills/issues/19
            {
                "name": SKILL_NAME,
                "description": SKILL_DESC,
                "license": SKILL_LICENSE,
                "compatibility": SKILL_COMPAT,
                "allowed_tools": SKILL_ALLOWED_TOOLS,
                "metadata": SKILL_METADATA,
            },
            [TOOL_ONE, TOOL_TWO],
        ),
    ],
)
def test_filesystemskillconfig_ctor(
    skill_path,
    w_metadata_kw,
    exp_allowed_tools,
):
    skill_config = config_skills.FilesystemSkillConfig(
        _skill_metadata=hs_models.SkillMetadata(**w_metadata_kw),
        _skill_path=skill_path,
    )

    assert skill_config.source == hs_models.SkillSource.FILESYSTEM
    assert skill_config.name == SKILL_NAME
    assert skill_config.description == SKILL_DESC
    assert skill_config.license == w_metadata_kw.get("license")
    assert skill_config.compatibility == w_metadata_kw.get("compatibility")
    assert skill_config.allowed_tools == exp_allowed_tools
    assert skill_config.metadata == w_metadata_kw.get("metadata", {})
    assert skill_config.errors == []
    assert skill_config.path == skill_path
    assert skill_config.extra_parameters == {"path": skill_path}


def test_filesystemskillconfig_ctor_w_errors(skill_path):
    validation_error = hs_models.SkillValidationError(
        SKILL_VALIDATION_ERROR,
        skill_path,
    )
    skill_metadata = hs_models.SkillMetadata(
        name=SKILL_NAME,
        description=SKILL_VALIDATION_ERROR,
    )
    skill_config = config_skills.FilesystemSkillConfig(
        _skill_path=skill_path,
        _skill_metadata=skill_metadata,
        _validation_errors=[validation_error],
    )

    assert skill_config.name is SKILL_NAME
    assert skill_config.description is SKILL_VALIDATION_ERROR
    assert skill_config.license is None
    assert skill_config.compatibility is None
    assert skill_config.allowed_tools == []
    assert skill_config.metadata == {}
    assert skill_config.errors == [validation_error]


def test_filesystemskillconfig_from_skill_preserves_original(skill_path):
    """FilesystemSkillConfig.from_skill returns the original Skill object,
    preserving tools, instructions, and other fields that would be lost
    if the Skill were reconstructed from metadata alone."""

    my_tool = mock.Mock()

    original = hs_models.Skill(
        metadata=hs_models.SkillMetadata(
            name=SKILL_NAME,
            description=SKILL_DESC,
        ),
        source=hs_models.SkillSource.FILESYSTEM,
        path=skill_path,
        instructions="Use the tool.",
        tools=[my_tool],
    )

    skill_config = config_skills.FilesystemSkillConfig.from_skill(original)
    found = skill_config.skill

    assert found is original


@pytest.mark.parametrize("w_errors", [[], [SKILL_VALIDATION_ERROR]])
@mock.patch("haiku.skills.discovery.discover_from_paths")
def test_filesystemskillconfig_from_path(
    hsd_dfp,
    skill_path,
    w_errors,
):
    if w_errors:
        hsd_dfp.return_value = (
            [],
            [
                hs_models.SkillValidationError(msg, skill_path)
                for msg in w_errors
            ],
        )
    else:
        metadata = mock.create_autospec(hs_models.SkillMetadata)
        metadata.name = SKILL_NAME  # mock quirk
        skill = mock.create_autospec(hs_models.Skill)
        skill.metadata = metadata  # mock quirk
        skill.path = skill_path
        hsd_dfp.return_value = [skill], []

    found = config_skills.FilesystemSkillConfig.from_path(skill_path)

    if w_errors:
        assert found.name == SKILL_NAME
        assert found.errors == w_errors
        assert found.description.startswith("Invalid filesystem skill")
    else:
        assert found._skill_metadata is metadata
        assert found.errors == []

    hsd_dfp.assert_called_once_with([skill_path])


@pytest.mark.parametrize(
    "w_kw",
    [
        {},
        {
            "state_type": SkillTypeTest,
            "state_namespace": SKILL_TYPE_NAMESPACE,
        },
    ],
)
def test_filesystemskillconfig_agui_feature_names(skill_path, w_kw):
    skill_config = config_skills.FilesystemSkillConfig(
        _skill_path=skill_path,
        _skill_metadata=hs_models.SkillMetadata(
            name=SKILL_NAME,
            description=SKILL_DESC,
        ),
        **w_kw,
    )

    found = skill_config.agui_feature_names

    if w_kw:
        assert found == (w_kw["state_namespace"],)
    else:
        assert found == ()


@pytest.mark.parametrize(
    "w_metadata_kw, w_kw, exp_model",
    [
        (
            {
                "name": SKILL_NAME,
                "description": SKILL_DESC,
            },
            {},
            None,
        ),
        (
            {
                "name": SKILL_NAME,
                "description": SKILL_DESC,
                "license": SKILL_LICENSE,
                "compatibility": SKILL_COMPAT,
                "allowed_tools": SKILL_ALLOWED_TOOLS,
                "metadata": SKILL_METADATA,
            },
            {
                "state_type": SkillTypeTest,
                "state_namespace": SKILL_TYPE_NAMESPACE,
                # no 'model_name' or 'agent_config'
            },
            None,
        ),
        (
            {
                "name": SKILL_NAME,
                "description": SKILL_DESC,
            },
            {
                "state_type": SkillTypeTest,
                "state_namespace": SKILL_TYPE_NAMESPACE,
                "model_name": SKILL_MODEL_NAME,
            },
            SKILL_MODEL_NAME,
        ),
        (
            {
                "name": SKILL_NAME,
                "description": SKILL_DESC,
            },
            {
                "state_type": SkillTypeTest,
                "state_namespace": SKILL_TYPE_NAMESPACE,
                "agent_config": USE_MODEL_AGENT_CONFIG,
            },
            GMFC_RETURN_VALUE,
        ),
    ],
)
@mock.patch("soliplex.config.agents.get_model_from_config")
def test_filesystemskillconfig_skill(
    gmfc,
    skill_path,
    model_agent_config,
    openai_test_model,
    w_metadata_kw,
    w_kw,
    exp_model,
):
    if "agent_config" in w_kw:
        w_kw |= {"agent_config": model_agent_config}
        exp_model = gmfc.return_value = openai_test_model

    skill_config = config_skills.FilesystemSkillConfig(
        _skill_metadata=hs_models.SkillMetadata(**w_metadata_kw),
        _skill_path=skill_path,
        **w_kw,
    )

    found = skill_config.skill

    assert isinstance(found, hs_models.Skill)
    assert found.source == hs_models.SkillSource.FILESYSTEM
    assert found.metadata.name == skill_config.name
    assert found.metadata.description == skill_config.description
    assert found.metadata.license == skill_config.license
    assert found.metadata.compatibility == skill_config.compatibility
    assert found.metadata.allowed_tools == skill_config.allowed_tools
    assert found.metadata.metadata == skill_config.metadata
    assert found.path == skill_path
    assert found.state_type is w_kw.get("state_type")
    assert found.state_namespace is w_kw.get("state_namespace")
    assert found.model is exp_model

    if "agent_config" in w_kw:
        gmfc.assert_called_once_with(agent_config=model_agent_config)
    else:
        gmfc.assert_not_called()


@pytest.mark.parametrize(
    "w_metadata_kw, exp_allowed_tools",
    [
        ({"name": SKILL_NAME, "description": SKILL_DESC}, []),
        (
            {
                "name": SKILL_NAME,
                "description": SKILL_DESC,
                "license": SKILL_LICENSE,
                "compatibility": SKILL_COMPAT,
                "allowed_tools": [TOOL_ONE, TOOL_TWO],
                "metadata": SKILL_METADATA,
            },
            [TOOL_ONE, TOOL_TWO],
        ),
        (  # XXX See: https://github.com/ggozad/haiku.skills/issues/19
            {
                "name": SKILL_NAME,
                "description": SKILL_DESC,
                "license": SKILL_LICENSE,
                "compatibility": SKILL_COMPAT,
                "allowed_tools": SKILL_ALLOWED_TOOLS,
                "metadata": SKILL_METADATA,
            },
            [TOOL_ONE, TOOL_TWO],
        ),
    ],
)
def test_entrypointskillconfig_ctor(w_metadata_kw, exp_allowed_tools):
    skill_config = config_skills.EntrypointSkillConfig(
        _skill_metadata=hs_models.SkillMetadata(**w_metadata_kw),
    )

    assert skill_config.name == SKILL_NAME
    assert skill_config.description == SKILL_DESC
    assert skill_config.license == w_metadata_kw.get("license")
    assert skill_config.compatibility == w_metadata_kw.get("compatibility")
    assert skill_config.allowed_tools == exp_allowed_tools
    assert skill_config.metadata == w_metadata_kw.get("metadata", {})
    assert skill_config.extra_parameters == {}


def test_entrypointskillconfig_from_skill_preserves_original():
    """EntrypointSkillConfig.from_skill returns the original Skill object,
    preserving tools, instructions, and other fields that would be lost
    if the Skill were reconstructed from metadata alone."""

    my_tool = mock.Mock()

    original = hs_models.Skill(
        metadata=hs_models.SkillMetadata(
            name=SKILL_NAME,
            description=SKILL_DESC,
        ),
        source=hs_models.SkillSource.ENTRYPOINT,
        instructions="Use the tool.",
        tools=[my_tool],
    )

    skill_config = config_skills.EntrypointSkillConfig.from_skill(original)
    found = skill_config.skill

    assert found is original


@pytest.mark.parametrize(
    "w_kw",
    [
        {},
        {
            "state_type": SkillTypeTest,
            "state_namespace": SKILL_TYPE_NAMESPACE,
        },
    ],
)
def test_entrypointskillconfig_agui_feature_names(w_kw):
    skill_config = config_skills.EntrypointSkillConfig(
        _skill_metadata=hs_models.SkillMetadata(
            name=SKILL_NAME,
            description=SKILL_DESC,
        ),
        **w_kw,
    )

    found = skill_config.agui_feature_names

    if w_kw:
        assert found == (w_kw["state_namespace"],)
    else:
        assert found == ()


@pytest.mark.parametrize(
    "w_metadata_kw, w_kw, exp_model",
    [
        (
            {
                "name": SKILL_NAME,
                "description": SKILL_DESC,
            },
            {},
            None,
        ),
        (
            {
                "name": SKILL_NAME,
                "description": SKILL_DESC,
                "license": SKILL_LICENSE,
                "compatibility": SKILL_COMPAT,
                "allowed_tools": SKILL_ALLOWED_TOOLS,
                "metadata": SKILL_METADATA,
            },
            {
                "state_type": SkillTypeTest,
                "state_namespace": SKILL_TYPE_NAMESPACE,
                "model_name": SKILL_MODEL_NAME,
            },
            SKILL_MODEL_NAME,
        ),
        (
            {
                "name": SKILL_NAME,
                "description": SKILL_DESC,
            },
            {
                "state_type": SkillTypeTest,
                "state_namespace": SKILL_TYPE_NAMESPACE,
                "agent_config": USE_MODEL_AGENT_CONFIG,
            },
            GMFC_RETURN_VALUE,
        ),
    ],
)
@mock.patch("soliplex.config.agents.get_model_from_config")
def test_entrypointskillconfig_skill(
    gmfc,
    skill_path,
    model_agent_config,
    openai_test_model,
    w_metadata_kw,
    w_kw,
    exp_model,
):
    if "agent_config" in w_kw:
        w_kw |= {"agent_config": model_agent_config}
        exp_model = gmfc.return_value = openai_test_model

    skill_config = config_skills.EntrypointSkillConfig(
        _skill_metadata=hs_models.SkillMetadata(**w_metadata_kw),
        **w_kw,
    )

    found = skill_config.skill

    assert isinstance(found, hs_models.Skill)
    assert found.source == hs_models.SkillSource.ENTRYPOINT
    assert found.metadata.name == skill_config.name
    assert found.metadata.description == skill_config.description
    assert found.metadata.license == skill_config.license
    assert found.metadata.compatibility == skill_config.compatibility
    assert found.metadata.allowed_tools == skill_config.allowed_tools
    assert found.metadata.metadata == skill_config.metadata
    assert found.state_type is w_kw.get("state_type")
    assert found.state_namespace is w_kw.get("state_namespace")
    assert found.model is exp_model

    if "agent_config" in w_kw:
        gmfc.assert_called_once_with(agent_config=model_agent_config)
    else:
        gmfc.assert_not_called()


@pytest.fixture
def haiku_rag_config():
    return hr_config.AppConfig(environment="testing")


@pytest.fixture
def lancedb(temp_dir):
    result = temp_dir / "rag.lancedb"
    result.mkdir()
    return result


@pytest.fixture
def config_path(temp_dir):
    return temp_dir / "config_file.yaml"


@pytest.fixture
def derived_hrskillconfig():
    skill_module = mock.Mock(
        spec_set=[
            "skill_metadata",
            "STATE_NAMESPACE",
            "STATE_TYPE",
            "create_skill",
        ],
    )

    class TestHRSkllConfig(config_skills._HR_SkillConfigBase):
        _hr_skill_module = skill_module
        rag_lancedb_path = mock.Mock(spec_set=())
        haiku_rag_config = mock.Mock(spec_set=())

    return skill_module, TestHRSkllConfig(rag_lancedb_stem="test")


def test__hrskillconfigbase_skill_metadata(derived_hrskillconfig):
    skill_module, inst = derived_hrskillconfig
    skill_metadata = skill_module.skill_metadata.return_value

    assert inst.skill_metadata is skill_metadata
    assert inst.name is skill_metadata.name
    assert inst.description is skill_metadata.description
    assert inst.license is skill_metadata.license
    assert inst.compatibility is skill_metadata.compatibility
    assert inst.allowed_tools is skill_metadata.allowed_tools
    assert inst.metadata is skill_metadata.metadata
    assert inst.extra_parameters == {"rag_lancedb_path": inst.rag_lancedb_path}


def test__hrskillconfigbase_agui_skill_namespace(derived_hrskillconfig):
    skill_module, inst = derived_hrskillconfig

    assert inst.state_namespace is skill_module.STATE_NAMESPACE


def test__hrskillconfigbase_agui_skill_type(derived_hrskillconfig):
    skill_module, inst = derived_hrskillconfig

    assert inst.state_type is skill_module.STATE_TYPE


def test__hrskillconfigbase_agui_feature_names(derived_hrskillconfig):
    skill_module, inst = derived_hrskillconfig

    assert inst.agui_feature_names == [skill_module.STATE_NAMESPACE]


def test_hrskillconfigbbase_skill(derived_hrskillconfig):
    skill_module, inst = derived_hrskillconfig

    found = inst.skill

    assert found is skill_module.create_skill.return_value

    skill_module.create_skill.assert_called_once_with(
        db_path=inst.rag_lancedb_path,
        config=inst.haiku_rag_config,
    )


def test_hr_rag_skillconfig_metadata(
    installation_config,
    haiku_rag_config,
    lancedb,
    config_path,
):

    inst = config_skills.HR_RAG_SkillConfig(
        rag_lancedb_override_path=lancedb,
        _haiku_rag_config=haiku_rag_config,
        _config_path=config_path,
        _installation_config=installation_config,
    )

    found = inst.skill_metadata

    assert found.name == "rag"


def test_hr_rag_skillconfig_skill(
    installation_config,
    haiku_rag_config,
    lancedb,
    config_path,
):
    inst = config_skills.HR_RAG_SkillConfig(
        rag_lancedb_override_path=lancedb,
        _haiku_rag_config=haiku_rag_config,
        _config_path=config_path,
        _installation_config=installation_config,
    )

    found = inst.skill

    assert isinstance(found, hs_models.Skill)
    assert found.metadata == hr_skills_rag.skill_metadata()


@pytest.mark.parametrize(
    "w_config, expectation",
    [
        # kwargs, expected_warning_count or exception type
        (
            {"not_a_valid_key": "FAIL"},
            pytest.raises(config_exc.FromYamlException),
        ),
        ({}, contextlib.nullcontext(0)),
        (
            {"tool_names": ["get_document", "list_documents"]},
            contextlib.nullcontext(1),
        ),
        ({"rag_features": ["search"]}, contextlib.nullcontext(1)),
        ({"rag_features": ["bogus"]}, contextlib.nullcontext(1)),
        ({"rag_features": ["analysis"]}, contextlib.nullcontext(1)),
        (
            {"tool_names": ["ask"], "rag_features": ["search"]},
            contextlib.nullcontext(2),
        ),
    ],
)
def test_hr_rag_skillconfig_from_yaml(
    lancedb,
    config_path,
    installation_config,
    w_config,
    expectation,
):
    config_dict = {
        "rag_lancedb_override_path": lancedb,
    } | w_config

    with (
        warnings.catch_warnings(record=True) as warned,
        expectation as expected,
    ):
        inst = config_skills.HR_RAG_SkillConfig.from_yaml(
            installation_config=installation_config,
            config_path=config_path,
            config_dict=config_dict,
        )

    if not isinstance(expected, pytest.ExceptionInfo):
        assert len(warned) == expected
        for warning in warned:
            assert warning.category is DeprecationWarning

        assert inst.rag_lancedb_path == lancedb
        assert inst.haiku_rag_config is installation_config.haiku_rag_config
        assert inst.tool_names == []  # See #773


def test_hr_analysis_skillconfig_metadata(
    installation_config,
    haiku_rag_config,
    lancedb,
    config_path,
):
    inst = config_skills.HR_Analysis_SkillConfig(
        rag_lancedb_override_path=lancedb,
        _haiku_rag_config=haiku_rag_config,
        _config_path=config_path,
        _installation_config=installation_config,
    )

    found = inst.skill_metadata

    assert found.name == "rag-analysis"


def test_hr_analysis_skillconfig_skill(
    installation_config,
    haiku_rag_config,
    lancedb,
    config_path,
):
    inst = config_skills.HR_Analysis_SkillConfig(
        rag_lancedb_override_path=lancedb,
        _haiku_rag_config=haiku_rag_config,
        _config_path=config_path,
        _installation_config=installation_config,
    )

    found = inst.skill

    assert isinstance(found, hs_models.Skill)
    assert found.metadata == hr_skills_analysis.skill_metadata()


@pytest.mark.parametrize(
    "w_config, expectation",
    [
        # kwargs, expected_warning_count or exception type
        (
            {"not_a_valid_key": "FAIL"},
            pytest.raises(config_exc.FromYamlException),
        ),
        ({}, contextlib.nullcontext(0)),
    ],
)
def test_hr_analysis_skillconfig_from_yaml(
    lancedb,
    config_path,
    installation_config,
    w_config,
    expectation,
):
    config_dict = {
        "rag_lancedb_override_path": lancedb,
    } | w_config

    with (
        warnings.catch_warnings(record=True) as warned,
        expectation as expected,
    ):
        inst = config_skills.HR_Analysis_SkillConfig.from_yaml(
            installation_config=installation_config,
            config_path=config_path,
            config_dict=config_dict,
        )

    if not isinstance(expected, pytest.ExceptionInfo):
        assert len(warned) == expected
        for warning in warned:  # pragma: NO COVER
            assert warning.category is DeprecationWarning

        assert inst.rag_lancedb_path == lancedb
        assert inst.haiku_rag_config is installation_config.haiku_rag_config


TEST_SKILL_CONFIG_ID = "test-bwrap-sandbox-id"
TEST_DEFAULT_ENVIRONMENT = "test-environment"
TEST_EXEC_TIMEOUT_SECS = 60


@pytest.mark.parametrize(
    "w_config, expectation",
    [
        # kwargs, expected_warning_count or exception type
        (
            {"not_a_valid_key": "FAIL"},
            pytest.raises(config_exc.FromYamlException),
        ),
        ({}, contextlib.nullcontext(0)),
        (
            {
                "id": TEST_SKILL_CONFIG_ID,
                "default_environment": TEST_DEFAULT_ENVIRONMENT,
                "allowed_environments": [TEST_DEFAULT_ENVIRONMENT],
                "sandbox_config": {
                    "execution_timeout_seconds": TEST_EXEC_TIMEOUT_SECS,
                },
            },
            contextlib.nullcontext(0),
        ),
    ],
)
def test_bwrapsandboxskillconfig_from_yaml(
    temp_dir,
    installation_config,
    w_config,
    expectation,
):
    config_path = temp_dir / "config_file.yaml"

    with expectation as expected:
        inst = config_skills.BwrapSandboxSkillConfig.from_yaml(
            installation_config=installation_config,
            config_path=config_path,
            config_dict=w_config.copy(),
        )

    if not isinstance(expected, pytest.ExceptionInfo):
        assert inst.id == w_config.get("id")
        assert inst.default_environment == w_config.get(
            "default_environment",
            "bare",
        )
        assert isinstance(inst.sandbox_config, bs_config.Config)
        sb_config = w_config.get("sandbox_config", {})
        exp_config = bs_config.Config(
            config_file_path=config_path,
            **sb_config,
        )
        assert inst.sandbox_config == exp_config

        if "default_environment" in w_config:
            assert (
                inst.extra_parameters["default_environment"]
                == w_config["default_environment"]
            )
        else:
            assert inst.extra_parameters["default_environment"] == "bare"

        if "allowed_environments" in w_config:
            assert (
                inst.extra_parameters["allowed_environments"]
                == w_config["allowed_environments"]
            )
        else:
            assert "allowed_environments" not in inst.extra_parameters


def test_bwrapsandboxskillconfig_agui_feature_names():
    bssc = config_skills.BwrapSandboxSkillConfig()

    (found,) = bssc.agui_feature_names

    assert found == sk_bwrap_sandbox.STATE_NAMESPACE


@pytest.mark.parametrize("w_allowed_environments", [None, ["one"]])
@pytest.mark.parametrize(
    "w_volumes",
    [
        {},
        {"foo": bs_models.VolumeInfo(host_path="/tmp/foo", writable=False)},
    ],
)
@mock.patch("soliplex.skills.bwrap_sandbox.create_bwrap_sandbox_skill")
def test_bwrapsandboxskillconfig_skill(
    cbss,
    w_volumes,
    w_allowed_environments,
):
    installation_config = mock.create_autospec(
        config_installation.InstallationConfig
    )
    bssc = config_skills.BwrapSandboxSkillConfig(
        id=TEST_SKILL_CONFIG_ID,
        default_environment=TEST_DEFAULT_ENVIRONMENT,
        allowed_environments=w_allowed_environments,
        sandbox_config=bs_config.Config(
            execution_timeout_seconds=TEST_EXEC_TIMEOUT_SECS,
        ),
        volumes=w_volumes,
        _installation_config=installation_config,
    )

    found = bssc.skill

    assert found is cbss.return_value

    cbss.assert_called_once_with(
        id=bssc.id,
        default_environment=bssc.default_environment,
        allowed_environments=w_allowed_environments,
        sandbox_config=bssc.sandbox_config,
        volumes=w_volumes,
        installation_config=installation_config,
    )

    assert found._factory is cbss


@pytest.mark.parametrize(
    "w_invalid_kind, expectation",
    [
        (False, contextlib.nullcontext(0)),
        (True, pytest.raises(config_skills.InvalidSkillKind)),
    ],
)
def test_extractskillconfigs(
    installation_config,
    temp_dir,
    w_invalid_kind,
    expectation,
):
    config_path = temp_dir / "rooms" / "test" / "room_config.yaml"
    config_dict = {
        "skill_configs": [
            {
                "kind": "haiku.rag.skills.rag",
                "rag_lancedb_stem": "test-foo",
            },
            {
                "kind": "haiku.rag.skills.analysis",
                "rag_lancedb_stem": "test-bar",
            },
        ]
    }
    if w_invalid_kind:
        config_dict["skill_configs"].append(
            {
                "kind": "BOGUS",
                "rag_lancedb_stem": "test-baz",
            }
        )

    with (
        warnings.catch_warnings(record=True) as warned,
        expectation as expected,
    ):
        found = config_skills.extract_skill_configs(
            installation_config=installation_config,
            config_path=config_path,
            config_dict=config_dict,
        )

    if not isinstance(expected, pytest.ExceptionInfo):
        assert len(warned) == expected
        for warning in warned:  # pragma: NO COVER
            assert warning.category is DeprecationWarning

        assert isinstance(found["rag"], config_skills.HR_RAG_SkillConfig)
        assert found["rag"].rag_lancedb_stem == "test-foo"

        assert isinstance(
            found["rag-analysis"], config_skills.HR_Analysis_SkillConfig
        )
        assert found["rag-analysis"].rag_lancedb_stem == "test-bar"

        assert "skill_configs" not in config_dict


@pytest.mark.parametrize(
    "config_yaml, expectation",
    [
        (
            BOGUS_ROOM_SKILLS_CONFIG_YAML,
            pytest.raises(config_exc.FromYamlException),
        ),
        (
            W_MISSING_INSTALLATION_SKILLS_ROOM_SKILLS_CONFIG_YAML,
            pytest.raises(
                config_exc.FromYamlException,
                check=lambda exc: isinstance(
                    exc.__cause__, config_skills.MissingSkillNames
                ),
            ),
        ),
        (
            BARE_ROOM_SKILLS_CONFIG_YAML,
            contextlib.nullcontext(
                BARE_ROOM_SKILLS_CONFIG_KW,
            ),
        ),
        (
            W_INSTALLATION_SKILLS_ROOM_SKILLS_CONFIG_YAML,
            contextlib.nullcontext(
                W_INSTALLATION_SKILLS_ROOM_SKILLS_CONFIG_KW,
            ),
        ),
    ],
)
def test_roomskillsconfig_from_yaml(
    installation_config,
    config_path,
    config_yaml,
    expectation,
):
    installation_config.skill_configs = {SKILL_NAME: object()}
    config_path.write_text(config_yaml)

    with config_path.open() as stream:
        config_dict = yaml.safe_load(stream)

    with expectation as expected:
        found = config_skills.RoomSkillsConfig.from_yaml(
            installation_config,
            config_path,
            config_dict,
        )

    if isinstance(expected, pytest.ExceptionInfo):
        assert expected.value._config_path == config_path

    else:
        expected = config_skills.RoomSkillsConfig(**expected)
        expected = dataclasses.replace(
            expected,
            _installation_config=installation_config,
            _config_path=config_path,
        )

        assert found == expected


def test_roomskillsconfig_skill_configs(installation_config):
    skill_config = mock.create_autospec(
        config_skills._DiscoveredSkillConfigBase,
    )
    installation_config.skill_configs = {
        SKILL_NAME: skill_config,
        "other_skill": object(),
    }

    room_skills_config_kw = {"installation_skill_names": [SKILL_NAME]}
    room_skills_config = config_skills.RoomSkillsConfig(
        **room_skills_config_kw,
        _installation_config=installation_config,
    )

    found = room_skills_config.skill_configs

    assert found == {SKILL_NAME: skill_config}


def test_roomskillsconfig_skills(installation_config):
    skill = mock.create_autospec(hs_models.Skill)
    skill_config = mock.create_autospec(
        config_skills._DiscoveredSkillConfigBase, skill=skill
    )
    installation_config.skill_configs = {
        SKILL_NAME: skill_config,
        "other_skill": object(),
    }

    room_skill_config_kw = {"installation_skill_names": [SKILL_NAME]}
    room_skill_config = config_skills.RoomSkillsConfig(
        **room_skill_config_kw,
        _installation_config=installation_config,
    )

    found = room_skill_config.skills

    assert found == {SKILL_NAME: skill_config.skill}


def test_roomskillsconfig_skill_preambles(
    installation_config,
    haiku_rag_config,
    lancedb,
    config_path,
):
    haiku_rag_config.prompts.domain_preamble = DOMAIN_PREAMBLE
    skill_config = config_skills.HR_RAG_SkillConfig(
        rag_lancedb_override_path=lancedb,
        _haiku_rag_config=haiku_rag_config,
        _config_path=config_path,
        _installation_config=installation_config,
    )
    installation_config.skill_configs = {
        SKILL_NAME: skill_config,
        "other_skill": object(),
    }

    room_skill_config_kw = {"installation_skill_names": [SKILL_NAME]}
    room_skill_config = config_skills.RoomSkillsConfig(
        **room_skill_config_kw,
        _installation_config=installation_config,
    )

    found = room_skill_config.skill_preambles

    assert found == [DOMAIN_PREAMBLE]


@pytest.mark.parametrize(
    "w_kw, exp_model",
    [
        (
            {},
            None,
        ),
        (
            {
                "model_name": ROOM_SKILLS_MODEL_NAME,
            },
            ROOM_SKILLS_MODEL_NAME,
        ),
        (
            {
                "agent_config": USE_MODEL_AGENT_CONFIG,
            },
            GMFC_RETURN_VALUE,
        ),
    ],
)
@mock.patch("soliplex.config.agents.get_model_from_config")
def test_roomskillsconfig_skill_toolset(
    gmfc,
    installation_config,
    model_agent_config,
    openai_test_model,
    w_kw,
    exp_model,
):
    if "agent_config" in w_kw:
        w_kw |= {"agent_config": model_agent_config}
        exp_model = gmfc.return_value = openai_test_model

    skill = mock.create_autospec(hs_models.Skill)
    skill.metadata = mock.create_autospec(hs_models.SkillMetadata)
    skill.metadata.name = SKILL_NAME
    skill.metadata.description = SKILL_DESC

    skill_config = mock.create_autospec(
        config_skills._DiscoveredSkillConfigBase, skill=skill
    )

    installation_config.skill_configs = {
        SKILL_NAME: skill_config,
        "other_skill": object(),
    }

    room_skill_config = config_skills.RoomSkillsConfig(
        installation_skill_names=[SKILL_NAME],
        _installation_config=installation_config,
        **w_kw,
    )

    found = room_skill_config.skill_toolset

    assert isinstance(found, config_skills.SoliplexSkillToolset)
    catalog_lines = found.skill_catalog.splitlines()
    assert f"- **{SKILL_NAME}**: {SKILL_DESC}" in catalog_lines
    assert found._skill_model is exp_model

    if "agent_config" in w_kw:
        gmfc.assert_called_once_with(agent_config=model_agent_config)
    else:
        gmfc.assert_not_called()


@pytest.mark.anyio
@pytest.mark.parametrize(
    "w_deps",
    [
        None,
        mock.Mock(spec_set=["state"], state={}),  # Use outside soliplex app
        mock.Mock(
            room_id=TEST_ROOM_ID,
            thread_id=TEST_THREAD_ID,
            run_id=TEST_RUN_ID,
            state={},
        ),
    ],
)
@pytest.mark.parametrize("w_namespace", [False, True])
async def test_soliplex_skill_toolset_for_run(
    w_namespace,
    w_deps,
):
    toolset = config_skills.SoliplexSkillToolset()

    ns = sk_bwrap_sandbox.SandboxState()
    if w_namespace:
        toolset._namespaces[sk_bwrap_sandbox.STATE_NAMESPACE] = ns

    ctx = mock.Mock(deps=w_deps)
    result = await toolset.for_run(ctx)

    assert result is toolset

    if w_namespace and getattr(w_deps, "room_id", None):
        assert ns.room_id == TEST_ROOM_ID
        assert ns.thread_id == TEST_THREAD_ID
        assert ns.run_id == TEST_RUN_ID
    else:
        assert ns.room_id is None
        assert ns.thread_id is None
        assert ns.run_id is None
