import contextlib
from unittest import mock

import fastapi
import pytest
from ag_ui import core as agui_core
from haiku.rag.graph import agui as hr_agui
from sqlalchemy.ext import asyncio as sqla_asyncio

from soliplex import agents
from soliplex import config
from soliplex import installation
from soliplex import models
from soliplex import secrets

KEY = "test-key"
VALUE = "test-value"
DEFAULT = "test-default"

SECRET_NAME_1 = "TEST_SECRET"
SECRET_NAME_2 = "OTHER_SECRET"
SECRET_CONFIG_1 = config.SecretConfig(SECRET_NAME_1)
SECRET_CONFIG_2 = config.SecretConfig(SECRET_NAME_2)
MISS_ERROR = object()
OLLAMA_BASE_URL = "http://ollama.example.com:11434"

THREAD_ID = "test-agui-thread"
RUN_ID = "test-agui-run"

RUN_AGENT_INPUT = mock.create_autospec(
    agui_core.RunAgentInput,
    thread_id=THREAD_ID,
    run_id=RUN_ID,
)

NoSuchSecret = pytest.raises(KeyError)
RaisesSecretError = pytest.raises(secrets.SecretError)
NoRaise = contextlib.nullcontext()


@pytest.fixture
def test_user() -> models.UserProfile:
    return models.UserProfile(
        given_name="Phreddy",
        family_name="Phlyntstone",
        email="phreddy@example.com",
        preferred_username="phreddy",
    )


@pytest.mark.parametrize(
    "secrets_map, expectation",
    [
        ({}, NoSuchSecret),
        ({SECRET_NAME_1: SECRET_CONFIG_1}, NoRaise),
    ],
)
@mock.patch("soliplex.secrets.get_secret")
def test_installation_get_secret(gs, secrets_map, expectation):
    i_config = mock.create_autospec(
        config.InstallationConfig,
        secrets_map=secrets_map,
    )
    the_installation = installation.Installation(i_config)

    with mock.patch("os.environ", clear=True):
        with expectation as expected:
            found = the_installation.get_secret(SECRET_NAME_1)

    if expected is None:
        assert found is gs.return_value
        gs.assert_called_once_with(SECRET_CONFIG_1)
    else:
        gs.assert_not_called()


@pytest.mark.parametrize(
    "secret_configs, expectation",
    [
        ((), NoRaise),
        ([SECRET_CONFIG_1], RaisesSecretError),
        ([SECRET_CONFIG_1, SECRET_CONFIG_2], RaisesSecretError),
    ],
)
@mock.patch("soliplex.secrets.resolve_secrets")
def test_installation_resolve_secrets(srs, secret_configs, expectation):
    i_config = mock.create_autospec(
        config.InstallationConfig,
    )
    i_config.secrets = secret_configs
    the_installation = installation.Installation(i_config)

    with expectation as expected:
        if expected is not None:
            srs.side_effect = secrets.SecretError("testing")

        the_installation.resolve_secrets()

    srs.assert_called_once_with(secret_configs)


@pytest.mark.parametrize("w_default", [False, True])
def test_installation_get_environment(w_default):
    i_config = mock.create_autospec(config.InstallationConfig)
    the_installation = installation.Installation(i_config)

    kwargs = {}

    if w_default:
        kwargs["default"] = DEFAULT

    found = the_installation.get_environment(KEY, **kwargs)

    assert found is i_config.get_environment.return_value

    if w_default:
        i_config.get_environment.assert_called_once_with(KEY, DEFAULT)
    else:
        i_config.get_environment.assert_called_once_with(KEY, None)


@pytest.mark.parametrize("w_raise", [False, True])
def test_installation_resolve_environment(w_raise):
    i_config = mock.create_autospec(config.InstallationConfig)

    if w_raise:
        i_config.resolve_environment.side_effect = config.MissingEnvVars(
            "test1,test2",
            [
                config.MissingEnvVar("test1"),
                config.MissingEnvVar("test2"),
            ],
        )
    else:
        i_config.resolve_environment.return_value = None

    the_installation = installation.Installation(i_config)

    if w_raise:
        with pytest.raises(config.MissingEnvVars):
            the_installation.resolve_environment()
    else:
        the_installation.resolve_environment()


def test_installation_haiku_rag_config():
    i_config = mock.create_autospec(config.InstallationConfig)
    the_installation = installation.Installation(i_config)

    assert the_installation.haiku_rag_config is i_config.haiku_rag_config


def test_installation_get_all_models():
    # Create mock agent configs
    standalone_agent = mock.create_autospec(config.AgentConfig)
    standalone_agent.model_name = "standalone-model"

    # Create mock room config with agent and quizzes
    room_agent = mock.create_autospec(config.AgentConfig)
    room_agent.model_name = "room-model"

    judge_agent = mock.create_autospec(config.AgentConfig)
    judge_agent.model_name = "judge-model"

    quiz = mock.create_autospec(config.QuizConfig)
    quiz.judge_agent = judge_agent

    room_config = mock.create_autospec(config.RoomConfig)
    room_config.agent_config = room_agent
    room_config.quizzes = [quiz]

    # Create mock completion config
    completion_agent = mock.create_autospec(config.AgentConfig)
    completion_agent.model_name = "completion-model"

    completion_config = mock.create_autospec(config.CompletionConfig)
    completion_config.agent_config = completion_agent

    # Create mock haiku_rag_config with no models
    hr_config = mock.MagicMock()
    hr_config.embeddings = None
    hr_config.qa = None
    hr_config.reranking = None
    hr_config.research = None

    # Create installation config
    i_config = mock.create_autospec(config.InstallationConfig)
    i_config.agent_configs = [standalone_agent]
    i_config.room_configs = {"room1": room_config}
    i_config.completion_configs = {"completion1": completion_config}
    i_config.haiku_rag_config = hr_config
    i_config.environment = {}

    the_installation = installation.Installation(i_config)

    models = the_installation.get_all_models()

    assert models == {
        "standalone-model",
        "room-model",
        "judge-model",
        "completion-model",
    }


def test_installation_get_all_models_handles_none_model_names():
    # Test that None model names are handled gracefully
    standalone_agent = mock.create_autospec(config.AgentConfig)
    standalone_agent.model_name = None

    room_agent = mock.create_autospec(config.AgentConfig)
    room_agent.model_name = "valid-model"

    room_config = mock.create_autospec(config.RoomConfig)
    room_config.agent_config = room_agent
    room_config.quizzes = []

    hr_config = mock.MagicMock()
    hr_config.embeddings = None
    hr_config.qa = None
    hr_config.reranking = None
    hr_config.research = None

    i_config = mock.create_autospec(config.InstallationConfig)
    i_config.agent_configs = [standalone_agent]
    i_config.room_configs = {"room1": room_config}
    i_config.completion_configs = {}
    i_config.haiku_rag_config = hr_config
    i_config.environment = {}

    the_installation = installation.Installation(i_config)

    models = the_installation.get_all_models()

    assert models == {"valid-model"}


def test_installation_get_all_models_empty_configs():
    hr_config = mock.MagicMock()
    hr_config.embeddings = None
    hr_config.qa = None
    hr_config.reranking = None
    hr_config.research = None

    i_config = mock.create_autospec(config.InstallationConfig)
    i_config.agent_configs = []
    i_config.room_configs = {}
    i_config.completion_configs = {}
    i_config.haiku_rag_config = hr_config
    i_config.environment = {}

    the_installation = installation.Installation(i_config)

    models = the_installation.get_all_models()

    assert models == set()


def test_installation_get_all_models_none_in_room_and_completion():
    # Test None model_name in room config, quiz judge, and completion config
    room_agent = mock.create_autospec(config.AgentConfig)
    room_agent.model_name = None  # Branch: line 54->57

    # Quiz with no judge_agent
    quiz_no_judge = mock.create_autospec(config.QuizConfig)
    quiz_no_judge.judge_agent = None  # Branch: line 58->57

    # Quiz with judge but None model_name
    judge_agent_no_model = mock.create_autospec(config.AgentConfig)
    judge_agent_no_model.model_name = None

    quiz_judge_no_model = mock.create_autospec(config.QuizConfig)
    quiz_judge_no_model.judge_agent = judge_agent_no_model

    room_config = mock.create_autospec(config.RoomConfig)
    room_config.agent_config = room_agent
    room_config.quizzes = [quiz_no_judge, quiz_judge_no_model]

    # Completion config with None model_name
    completion_agent = mock.create_autospec(config.AgentConfig)
    completion_agent.model_name = None  # Branch: line 63->62

    completion_config = mock.create_autospec(config.CompletionConfig)
    completion_config.agent_config = completion_agent

    hr_config = mock.MagicMock()
    hr_config.embeddings = None
    hr_config.qa = None
    hr_config.reranking = None
    hr_config.research = None

    i_config = mock.create_autospec(config.InstallationConfig)
    i_config.agent_configs = []
    i_config.room_configs = {"room1": room_config}
    i_config.completion_configs = {"completion1": completion_config}
    i_config.haiku_rag_config = hr_config
    i_config.environment = {}

    the_installation = installation.Installation(i_config)

    models = the_installation.get_all_models()

    # All model names were None, so no models should be collected
    assert models == set()


def test_installation_get_all_models_from_haiku_rag_config():
    # Test models extracted from haiku.rag config sections
    embeddings_model = mock.MagicMock()
    embeddings_model.name = "embedding-model"

    qa_model = mock.MagicMock()
    qa_model.name = "qa-model"

    hr_config = mock.MagicMock()
    hr_config.embeddings.model = embeddings_model
    hr_config.qa.model = qa_model
    hr_config.reranking = None
    hr_config.research.model = None

    i_config = mock.create_autospec(config.InstallationConfig)
    i_config.agent_configs = []
    i_config.room_configs = {}
    i_config.completion_configs = {}
    i_config.haiku_rag_config = hr_config
    i_config.environment = {}

    the_installation = installation.Installation(i_config)

    models = the_installation.get_all_models()

    assert models == {"embedding-model", "qa-model"}


def test_installation_get_all_models_from_config_environment():
    # Test models extracted from installation config environment
    hr_config = mock.MagicMock()
    hr_config.embeddings = None
    hr_config.qa = None
    hr_config.reranking = None
    hr_config.research = None

    i_config = mock.create_autospec(config.InstallationConfig)
    i_config.agent_configs = []
    i_config.room_configs = {}
    i_config.completion_configs = {}
    i_config.haiku_rag_config = hr_config
    i_config.environment = {
        "DEFAULT_AGENT_MODEL": "env-model",
        "QA_MODEL": "qa-env-model",
    }

    the_installation = installation.Installation(i_config)

    models = the_installation.get_all_models()

    assert models == {"env-model", "qa-env-model"}


@mock.patch.dict("os.environ", {"EMBEDDINGS_MODEL": "os-embedding-model"})
def test_installation_get_all_models_from_os_environ():
    # Test models extracted from OS environment variables
    hr_config = mock.MagicMock()
    hr_config.embeddings = None
    hr_config.qa = None
    hr_config.reranking = None
    hr_config.research = None

    i_config = mock.create_autospec(config.InstallationConfig)
    i_config.agent_configs = []
    i_config.room_configs = {}
    i_config.completion_configs = {}
    i_config.haiku_rag_config = hr_config
    i_config.environment = {}

    the_installation = installation.Installation(i_config)

    models = the_installation.get_all_models()

    assert "os-embedding-model" in models


def test_installation_thread_persistence_dburi_sync():
    i_config = mock.create_autospec(config.InstallationConfig)
    the_installation = installation.Installation(i_config)

    assert (
        the_installation.thread_persistence_dburi_sync
        is i_config.thread_persistence_dburi_sync
    )


def test_installation_thread_persistence_dburi_async():
    i_config = mock.create_autospec(config.InstallationConfig)
    the_installation = installation.Installation(i_config)

    assert (
        the_installation.thread_persistence_dburi_async
        is i_config.thread_persistence_dburi_async
    )


def test_installation_room_authz_dburi_sync():
    i_config = mock.create_autospec(config.InstallationConfig)
    the_installation = installation.Installation(i_config)

    assert (
        the_installation.room_authz_dburi_sync
        is i_config.room_authz_dburi_sync
    )


def test_installation_room_authz_dburi_async():
    i_config = mock.create_autospec(config.InstallationConfig)
    the_installation = installation.Installation(i_config)

    assert (
        the_installation.room_authz_dburi_async
        is i_config.room_authz_dburi_async
    )


@pytest.mark.parametrize("w_oidc_configs", [[], [object()]])
def test_installation_auth_disabled(w_oidc_configs):
    i_config = mock.create_autospec(config.InstallationConfig)
    i_config.oidc_auth_system_configs = w_oidc_configs

    the_installation = installation.Installation(i_config)

    assert the_installation.auth_disabled == (not w_oidc_configs)


def test_installation_oidc_auth_system_configs():
    i_config = mock.create_autospec(config.InstallationConfig)
    the_installation = installation.Installation(i_config)

    assert (
        the_installation.oidc_auth_system_configs
        is i_config.oidc_auth_system_configs
    )


@pytest.fixture
def r_configs():
    r_config = mock.create_autospec(config.RoomConfig)
    return {"room_id": r_config}


class FauxRoomAuthz:
    def __init__(self, allowed):
        self.allowed = allowed

    async def check_room_access(self, room_id, user_token):
        return self.allowed

    async def filter_room_ids(self, room_ids, user_token):
        if self.allowed:
            return room_ids
        else:
            return []


@pytest.fixture(params=[None, False, True])
def room_authz(request):
    kw = {}
    if request.param is not None:
        kw["the_room_authz"] = FauxRoomAuthz(request.param)
    return kw


@pytest.mark.anyio
async def test_installation_get_room_configs(
    test_user,
    room_authz,
    r_configs,
):
    i_config = mock.create_autospec(config.InstallationConfig)
    i_config.room_configs = r_configs

    the_installation = installation.Installation(i_config)

    found = await the_installation.get_room_configs(
        user=test_user,
        **room_authz,
    )

    if room_authz:
        allowed = room_authz["the_room_authz"].allowed
        if allowed:
            assert found == r_configs
        else:
            assert found == {}
    else:
        assert found == r_configs


@pytest.mark.anyio
@pytest.mark.parametrize(
    "w_room_id, raises", [("room_id", False), ("nonesuch", True)]
)
async def test_installation_get_room_config(
    test_user,
    room_authz,
    r_configs,
    w_room_id,
    raises,
):
    i_config = mock.create_autospec(config.InstallationConfig)
    i_config.room_configs = r_configs

    the_installation = installation.Installation(i_config)

    if room_authz:
        allowed = room_authz["the_room_authz"].allowed
    else:
        allowed = True

    if raises:
        with pytest.raises(KeyError):
            await the_installation.get_room_config(
                room_id=w_room_id,
                user=test_user,
                **room_authz,
            )
    else:
        if not allowed:
            with pytest.raises(KeyError):
                await the_installation.get_room_config(
                    room_id=w_room_id,
                    user=test_user,
                    **room_authz,
                )
        else:
            found = await the_installation.get_room_config(
                room_id=w_room_id,
                user=test_user,
                **room_authz,
            )

            assert found is r_configs[w_room_id]


@pytest.mark.anyio
async def test_installation_get_completion_configs(test_user):
    c_config = mock.create_autospec(config.CompletionConfig)
    c_configs = {"completion_id": c_config}
    i_config = mock.create_autospec(config.InstallationConfig)
    i_config.completion_configs = c_configs

    the_installation = installation.Installation(i_config)

    found = await the_installation.get_completion_configs(user=test_user)

    assert found == c_configs


@pytest.mark.anyio
@pytest.mark.parametrize(
    "w_completion_id, raises", [("completion_id", False), ("nonesuch", True)]
)
async def test_installation_get_completion_config(
    test_user,
    w_completion_id,
    raises,
):
    c_config = mock.create_autospec(config.CompletionConfig)
    c_configs = {"completion_id": c_config}
    i_config = mock.create_autospec(config.InstallationConfig)
    i_config.completion_configs = c_configs

    the_installation = installation.Installation(i_config)

    if raises:
        with pytest.raises(KeyError):
            await the_installation.get_completion_config(
                completion_id=w_completion_id,
                user=test_user,
            )
    else:
        found = await the_installation.get_completion_config(
            completion_id=w_completion_id,
            user=test_user,
        )

        assert found is c_config


@pytest.mark.parametrize(
    "w_agent_id, raises", [("agent_id", False), ("nonesuch", True)]
)
@mock.patch("soliplex.agents.get_agent_from_configs")
def test_installation_get_agent_by_id(gafc, w_agent_id, raises):
    a_config = mock.create_autospec(config.AgentConfig)

    i_config = mock.create_autospec(config.InstallationConfig)
    i_config.agent_configs_map = {"agent_id": a_config}

    the_installation = installation.Installation(i_config)

    if raises:
        with pytest.raises(KeyError):
            the_installation.get_agent_by_id(w_agent_id)
    else:
        found = the_installation.get_agent_by_id(w_agent_id)
        assert found is gafc.return_value
        gafc.assert_called_once_with(a_config, {}, {})


@pytest.mark.anyio
@pytest.mark.parametrize(
    "w_room_id, raises", [("room_id", False), ("nonesuch", True)]
)
@mock.patch("soliplex.agents.get_agent_from_configs")
async def test_installation_get_agent_for_room(
    gafc,
    test_user,
    room_authz,
    w_room_id,
    raises,
):
    a_config = mock.create_autospec(config.AgentConfig)

    tc_config = mock.create_autospec(config.ToolConfig)
    sdtc_config = mock.create_autospec(config.SearchDocumentsToolConfig)

    mcp_stdio_config = mock.create_autospec(
        config.Stdio_MCP_ClientToolsetConfig
    )
    mcp_http_streaming_config = mock.create_autospec(
        config.HTTP_MCP_ClientToolsetConfig
    )

    r_config = mock.create_autospec(config.RoomConfig)
    r_config.agent_config = a_config
    t_configs = r_config.tool_configs = {
        "test_tool": tc_config,
        "test_sdtc": sdtc_config,
    }
    mcp_configs = r_config.mcp_client_toolset_configs = {
        "test_stdio": mcp_stdio_config,
        "test_http": mcp_http_streaming_config,
    }

    r_configs = {"room_id": r_config}
    i_config = mock.create_autospec(config.InstallationConfig)
    i_config.room_configs = r_configs

    if room_authz:
        allowed = room_authz["the_room_authz"].allowed
    else:
        allowed = True

    the_installation = installation.Installation(i_config)

    if raises:
        with pytest.raises(KeyError):
            await the_installation.get_agent_for_room(
                room_id=w_room_id,
                user=test_user,
                **room_authz,
            )
    else:
        if not allowed:
            with pytest.raises(KeyError):
                await the_installation.get_agent_for_room(
                    room_id=w_room_id,
                    user=test_user,
                    **room_authz,
                )

            gafc.assert_not_called()

        else:
            found = await the_installation.get_agent_for_room(
                room_id=w_room_id,
                user=test_user,
                **room_authz,
            )

            assert found is gafc.return_value

            gafc.assert_called_once_with(a_config, t_configs, mcp_configs)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "w_completion_id, raises", [("completion_id", False), ("nonesuch", True)]
)
@mock.patch("soliplex.agents.get_agent_from_configs")
async def test_installation_get_agent_for_completion(
    gafc,
    test_user,
    w_completion_id,
    raises,
):
    a_config = mock.create_autospec(config.AgentConfig)

    tc_config = mock.create_autospec(config.ToolConfig)
    sdtc_config = mock.create_autospec(config.SearchDocumentsToolConfig)

    mcp_stdio_config = mock.create_autospec(
        config.Stdio_MCP_ClientToolsetConfig
    )
    mcp_http_streaming_config = mock.create_autospec(
        config.HTTP_MCP_ClientToolsetConfig
    )

    c_config = mock.create_autospec(config.CompletionConfig)
    c_config.agent_config = a_config
    t_configs = c_config.tool_configs = {
        "test_tool": tc_config,
        "test_sdtc": sdtc_config,
    }
    mcp_configs = c_config.mcp_client_toolset_configs = {
        "test_stdio": mcp_stdio_config,
        "test_http": mcp_http_streaming_config,
    }

    c_configs = {"completion_id": c_config}
    i_config = mock.create_autospec(config.InstallationConfig)
    i_config.completion_configs = c_configs

    the_installation = installation.Installation(i_config)

    if raises:
        with pytest.raises(KeyError):
            await the_installation.get_agent_for_completion(
                completion_id=w_completion_id,
                user=test_user,
            )
        gafc.assert_not_called()
    else:
        found = await the_installation.get_agent_for_completion(
            completion_id=w_completion_id,
            user=test_user,
        )
        assert found is gafc.return_value
        gafc.assert_called_once_with(a_config, t_configs, mcp_configs)


@pytest.mark.anyio
@pytest.mark.parametrize("w_run_agent_input", [False, True])
@pytest.mark.parametrize(
    "w_room_id, raises", [("room_id", False), ("nonesuch", True)]
)
async def test_installation_get_agent_deps_for_room(
    test_user,
    room_authz,
    w_room_id,
    raises,
    w_run_agent_input,
):
    tc_config = mock.create_autospec(config.ToolConfig)
    sdtc_config = mock.create_autospec(config.SearchDocumentsToolConfig)

    r_config = mock.create_autospec(config.RoomConfig)
    t_configs = r_config.tool_configs = {
        "test_tool": tc_config,
        "test_sdtc": sdtc_config,
    }

    r_configs = {"room_id": r_config}
    i_config = mock.create_autospec(config.InstallationConfig)
    i_config.room_configs = r_configs

    if room_authz:
        allowed = room_authz["the_room_authz"].allowed
    else:
        allowed = True

    the_installation = installation.Installation(i_config)

    kw = {}
    if w_run_agent_input:
        kw["run_agent_input"] = RUN_AGENT_INPUT

    if raises:
        with pytest.raises(KeyError):
            await the_installation.get_agent_deps_for_room(
                room_id=w_room_id,
                user=test_user,
                **room_authz,
                **kw,
            )
    else:
        if not allowed:
            with pytest.raises(KeyError):
                await the_installation.get_agent_deps_for_room(
                    room_id=w_room_id,
                    user=test_user,
                    **room_authz,
                    **kw,
                )
        else:
            found = await the_installation.get_agent_deps_for_room(
                room_id=w_room_id,
                user=test_user,
                **room_authz,
                **kw,
            )

            assert isinstance(found, agents.AgentDependencies)

            assert found.the_installation is the_installation
            assert found.user == test_user
            assert found.tool_configs == t_configs

            if w_run_agent_input:
                assert isinstance(found.agui_emitter, hr_agui.AGUIEmitter)
                assert found.agui_emitter.thread_id == THREAD_ID
                assert found.agui_emitter.run_id == RUN_ID
            else:
                assert found.agui_emitter is None


@pytest.mark.anyio
@pytest.mark.parametrize("w_run_agent_input", [False, True])
@pytest.mark.parametrize(
    "w_completion_id, raises", [("completion_id", False), ("nonesuch", True)]
)
async def test_installation_get_agent_deps_for_completion(
    test_user,
    w_completion_id,
    raises,
    w_run_agent_input,
):
    tc_config = mock.create_autospec(config.ToolConfig)
    sdtc_config = mock.create_autospec(config.SearchDocumentsToolConfig)

    c_config = mock.create_autospec(config.CompletionConfig)
    t_configs = c_config.tool_configs = {
        "test_tool": tc_config,
        "test_sdtc": sdtc_config,
    }

    c_configs = {"completion_id": c_config}
    i_config = mock.create_autospec(config.InstallationConfig)
    i_config.completion_configs = c_configs

    the_installation = installation.Installation(i_config)

    kw = {}
    if w_run_agent_input:
        kw["run_agent_input"] = RUN_AGENT_INPUT

    if raises:
        with pytest.raises(KeyError):
            await the_installation.get_agent_deps_for_completion(
                completion_id=w_completion_id,
                user=test_user,
                **kw,
            )
    else:
        found = await the_installation.get_agent_deps_for_completion(
            completion_id=w_completion_id,
            user=test_user,
            **kw,
        )

        assert isinstance(found, agents.AgentDependencies)

        assert found.the_installation is the_installation
        assert found.user == test_user
        assert found.tool_configs == t_configs

        if w_run_agent_input:
            assert isinstance(found.agui_emitter, hr_agui.AGUIEmitter)
            assert found.agui_emitter.thread_id == THREAD_ID
            assert found.agui_emitter.run_id == RUN_ID
        else:
            assert found.agui_emitter is None


@pytest.mark.anyio
async def test_get_the_installation():
    i_config = mock.create_autospec(config.InstallationConfig)
    the_installation = installation.Installation(i_config)
    request = mock.create_autospec(fastapi.Request)
    request.state.the_installation = the_installation

    found = await installation.get_the_installation(request)

    assert found is the_installation


def _mock_mcp_app(key):
    async def _mock_lifespan(_ignored):
        yield None

    result = mock.MagicMock(spec_set=["lifespan"])
    result.lifespan = contextlib.asynccontextmanager(_mock_lifespan)
    return result


@pytest.fixture
def mcp_apps():
    return {key: _mock_mcp_app(key) for key in ["room1", "room2"]}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "w_no_auth_mode, exp_oidc_paths",
    [
        (None, ["oidc"]),
        (False, ["oidc"]),
        (True, []),
    ],
)
@mock.patch("soliplex.secrets.resolve_secrets")
@mock.patch("soliplex.mcp_server.setup_mcp_for_rooms")
@mock.patch("soliplex.config.load_installation")
async def test_lifespan(
    load_installation,
    smfr,
    srs,
    mcp_apps,
    w_no_auth_mode,
    exp_oidc_paths,
):
    INSTALLATION_PATH = "/path/to/installation"

    smfr.return_value = mcp_apps

    i_config = mock.create_autospec(
        config.InstallationConfig,
        secrets=(),
        oidc_paths=["oidc"],
        environment={"OLLAMA_BASE_URL": OLLAMA_BASE_URL},
        thread_persistence_dburi_async=config.ASYNC_MEMORY_ENGINE_URL,
    )
    load_installation.return_value = i_config
    app = mock.create_autospec(fastapi.FastAPI)

    kwargs = {}
    if w_no_auth_mode is not None:
        kwargs["no_auth_mode"] = w_no_auth_mode

    found = [
        item
        async for item in installation.lifespan(
            app,
            INSTALLATION_PATH,
            **kwargs,
        )
    ]

    assert len(found) == 1

    the_installation = found[0]["the_installation"]
    assert isinstance(the_installation, installation.Installation)
    assert the_installation._config is i_config

    assert i_config.oidc_paths == exp_oidc_paths

    i_config.reload_configurations.assert_called_once_with()

    load_installation.assert_called_once_with(INSTALLATION_PATH)

    threads_engine = found[0]["threads_engine"]
    assert isinstance(threads_engine, sqla_asyncio.AsyncEngine)

    room_authz_engine = found[0]["room_authz_engine"]
    assert isinstance(room_authz_engine, sqla_asyncio.AsyncEngine)

    for f_call, (key, mcp_app) in zip(
        app.mount.call_args_list,
        mcp_apps.items(),
        strict=True,
    ):
        assert f_call.args == ("/mcp/" + key, mcp_app)

    srs.assert_called_once_with(the_installation._config.secrets)
    smfr.assert_called_once_with(the_installation)
