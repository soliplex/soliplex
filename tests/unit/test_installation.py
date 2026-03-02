import contextlib
import dataclasses
from unittest import mock

import fastapi
import pytest
import sqlalchemy
from ag_ui import core as agui_core
from sqlalchemy.ext import asyncio as sqla_asyncio

from soliplex import agents
from soliplex import config
from soliplex import installation
from soliplex import loggers
from soliplex import models
from soliplex import secrets
from soliplex import util

KEY = "test-key"
VALUE = "test-value"
DEFAULT = "test-default"

ADMIN_USER_EMAIL = "admin@example.com"
LOG_CONFIG_FILE = "logging.yaml"

SECRET_NAME_1 = "TEST_SECRET"
SECRET_NAME_2 = "OTHER_SECRET"
SECRET_CONFIG_1 = config.SecretConfig(secret_name=SECRET_NAME_1)
SECRET_CONFIG_2 = config.SecretConfig(secret_name=SECRET_NAME_2)
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


@pytest.fixture(params=[None, "agent", "factory"])
def standalone_agents(request):
    kw = {}
    agent_configs = kw["agent_configs"] = []

    if request.param == "agent":
        standalone_agent = mock.create_autospec(
            config.AgentConfig,
            id="standalone-agent",
            provider_type=config.LLMProviderType.OLLAMA,
            llm_provider_base_url=OLLAMA_BASE_URL,
            model_name="standalone-model",
        )

        agent_configs.append(
            standalone_agent,
        )

    elif request.param == "factory":
        standalone_factory_agent = mock.create_autospec(
            config.FactoryAgentConfig,
            id="standalone-factory-agent",
        )

        agent_configs.append(
            standalone_factory_agent,
        )

    return kw


@pytest.fixture(params=[False, True])
def quiz_judge_agents(request):
    kw = {}

    if request.param:
        kw["judge_agent"] = mock.create_autospec(
            config.AgentConfig,
            id="judge-agent",
            provider_type=config.LLMProviderType.OLLAMA,
            llm_provider_base_url=OLLAMA_BASE_URL,
            model_name="judge-model",
        )
    else:
        kw["judge_agent"] = None

    return kw


@pytest.fixture(params=[False, True])
def room_quizzes(request, quiz_judge_agents):
    kw = {"quizzes": []}

    if request.param:
        kw["quizzes"].append(
            mock.create_autospec(
                config.QuizConfig,
                **quiz_judge_agents,
            )
        )

    return kw


@pytest.fixture(params=[False, True])
def rooms_with_agents(request, room_quizzes):
    kw = {}
    room_configs = kw["room_configs"] = {}

    if request.param:
        room_agent = mock.create_autospec(
            config.AgentConfig,
            id="room-agent",
            provider_type=config.LLMProviderType.OLLAMA,
            llm_provider_base_url=OLLAMA_BASE_URL,
            model_name="room-model",
        )
        room_config = mock.create_autospec(
            config.RoomConfig,
            id="test-room",
            agent_config=room_agent,
            **room_quizzes,
        )
        room_configs["test-room"] = room_config

    return kw


@pytest.fixture(params=[False, True])
def completions_with_agents(request):
    kw = {}
    completion_configs = kw["completion_configs"] = {}

    if request.param:
        completion_agent = mock.create_autospec(
            config.AgentConfig,
            id="completion-agent",
            provider_type=config.LLMProviderType.OLLAMA,
            llm_provider_base_url=OLLAMA_BASE_URL,
            model_name="completion-model",
        )
        completion_config = mock.create_autospec(
            config.CompletionConfig,
            id="test-completion",
            agent_config=completion_agent,
        )
        completion_configs["test-completion"] = completion_config

    return kw


def test_installation_all_agent_configs(
    standalone_agents,
    rooms_with_agents,
    completions_with_agents,
):
    i_config = mock.create_autospec(
        config.InstallationConfig,
        **standalone_agents,
        **rooms_with_agents,
        **completions_with_agents,
    )

    expected = {}

    if standalone_agents["agent_configs"]:
        expected |= {
            agent.id: agent for agent in standalone_agents["agent_configs"]
        }

    if rooms_with_agents["room_configs"]:
        expected |= {
            room.agent_config.id: room.agent_config
            for room in rooms_with_agents["room_configs"].values()
        }
        quizzes = []

        for room in rooms_with_agents["room_configs"].values():
            quizzes.extend(room.quizzes)

        expected |= {
            quiz.judge_agent.id: quiz.judge_agent
            for quiz in quizzes
            if quiz.judge_agent is not None
        }

    if completions_with_agents["completion_configs"]:
        expected |= {
            completion.agent_config.id: completion.agent_config
            for completion in (
                completions_with_agents["completion_configs"].values()
            )
        }

    the_installation = installation.Installation(i_config)

    found = the_installation.all_agent_configs

    assert found == expected


def test_installation_agent_provider_info(
    standalone_agents,
    rooms_with_agents,
    completions_with_agents,
):
    i_config = mock.create_autospec(
        config.InstallationConfig,
        **standalone_agents,
        **rooms_with_agents,
        **completions_with_agents,
    )

    expected = {}

    def _add_agent(agent):
        # FactoryAgentConfig has no provider info or model
        provider_type = getattr(agent, "provider_type", None)

        if provider_type is not None:
            type_urls = expected.setdefault(agent.provider_type, {})
            url_models = type_urls.setdefault(
                agent.llm_provider_base_url, set()
            )
            url_models.add(agent.model_name)

    if standalone_agents["agent_configs"]:
        for agent in standalone_agents["agent_configs"]:
            _add_agent(agent)

    if rooms_with_agents["room_configs"]:
        for room in rooms_with_agents["room_configs"].values():
            _add_agent(room.agent_config)

            for quiz in room.quizzes:
                if quiz.judge_agent:
                    _add_agent(quiz.judge_agent)

    if completions_with_agents["completion_configs"]:
        completion_configs = completions_with_agents["completion_configs"]
        for completion in completion_configs.values():
            _add_agent(completion.agent_config)

    the_installation = installation.Installation(i_config)

    found = the_installation.agent_provider_info

    assert found == expected


HR_CONFIG_SECTIONS = ["embeddings", "qa", "reranking", "research"]
TEST_MODEL_PROVIDER = "test-model-provider"
TEST_MODEL_BASE_URL = "https://provider.example.com:11434"
TEST_MODEL_NAME = "test-model-name"


@dataclasses.dataclass
class FauxHRModel:
    provider: str = TEST_MODEL_PROVIDER
    base_url: str = TEST_MODEL_BASE_URL
    name: str = TEST_MODEL_NAME


@pytest.fixture(params=[None] + HR_CONFIG_SECTIONS)
def hr_config_w_providers(request):
    hr_config = mock.Mock(
        spec_set=HR_CONFIG_SECTIONS + ["which"],
        which=request.param,
        embeddings=None,
        qa=None,
        reranking=None,
        research=None,
    )
    model = FauxHRModel()
    section = mock.Mock(spec_set=["model"], model=model)

    for section_name in HR_CONFIG_SECTIONS:
        if section_name == request.param:
            setattr(hr_config, section_name, section)

    return hr_config


def test_installation_haiku_rag_provider_info(hr_config_w_providers):
    i_config = mock.create_autospec(
        config.InstallationConfig,
        haiku_rag_config=hr_config_w_providers,
    )
    the_installation = installation.Installation(i_config)

    expected = {}

    if hr_config_w_providers.which is not None:
        expected[TEST_MODEL_PROVIDER] = {
            TEST_MODEL_BASE_URL: set([TEST_MODEL_NAME]),
        }

    found = the_installation.haiku_rag_provider_info

    assert found == expected


def test_installation_all_provider_info(
    standalone_agents,
    rooms_with_agents,
    completions_with_agents,
    hr_config_w_providers,
):
    i_config = mock.create_autospec(
        config.InstallationConfig,
        haiku_rag_config=hr_config_w_providers,
        **standalone_agents,
        **rooms_with_agents,
        **completions_with_agents,
    )
    i_config.get_environment.side_effect = {
        "OLLAMA_BASE_URL": OLLAMA_BASE_URL,
    }.get
    the_installation = installation.Installation(i_config)

    expected = {}

    def _add_agent(agent):
        # FactoryAgentConfig has no provider info or model
        provider_type = getattr(agent, "provider_type", None)

        if provider_type is not None:
            type_urls = expected.setdefault(agent.provider_type, {})
            url_models = type_urls.setdefault(
                agent.llm_provider_base_url, set()
            )
            url_models.add(agent.model_name)

    if standalone_agents["agent_configs"]:
        for agent in standalone_agents["agent_configs"]:
            _add_agent(agent)

    if rooms_with_agents["room_configs"]:
        for room in rooms_with_agents["room_configs"].values():
            _add_agent(room.agent_config)

            for quiz in room.quizzes:
                if quiz.judge_agent:
                    _add_agent(quiz.judge_agent)

    if completions_with_agents["completion_configs"]:
        completion_configs = completions_with_agents["completion_configs"]
        for completion in completion_configs.values():
            _add_agent(completion.agent_config)

    if hr_config_w_providers.which is not None:
        expected[TEST_MODEL_PROVIDER] = {
            TEST_MODEL_BASE_URL: set([TEST_MODEL_NAME]),
        }

    found = the_installation.all_provider_info

    assert found == expected


def test_installation_logfire_config():
    i_config = mock.create_autospec(config.InstallationConfig)
    the_installation = installation.Installation(i_config)

    assert the_installation.logfire_config is i_config.logfire_config


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


def test_installation_authorization_dburi_sync():
    i_config = mock.create_autospec(config.InstallationConfig)
    the_installation = installation.Installation(i_config)

    assert (
        the_installation.authorization_dburi_sync
        is i_config.authorization_dburi_sync
    )


def test_installation_authorization_dburi_async():
    i_config = mock.create_autospec(config.InstallationConfig)
    the_installation = installation.Installation(i_config)

    assert (
        the_installation.authorization_dburi_async
        is i_config.authorization_dburi_async
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
def authz_kwargs(request):
    kw = {}
    if request.param is not None:
        kw["the_authz_policy"] = FauxRoomAuthz(request.param)
    return kw


@pytest.fixture
def the_logger():
    return mock.create_autospec(loggers.LogWrapper)


@pytest.mark.anyio
@pytest.mark.parametrize("w_the_logger", [False, True])
@mock.patch("soliplex.loggers.LogWrapper")
async def test_installation_get_room_configs(
    lw_klass,
    test_user,
    authz_kwargs,
    r_configs,
    the_logger,
    w_the_logger,
):
    i_config = mock.create_autospec(config.InstallationConfig)
    i_config.room_configs = r_configs

    the_installation = installation.Installation(i_config)

    if w_the_logger:
        exp_logger = the_logger.bind.return_value

        found = await the_installation.get_room_configs(
            user=test_user,
            **authz_kwargs,
            the_logger=the_logger,
        )

        the_logger.bind.assert_called_once_with(
            loggers.AUTHZ_LOGGER_NAME,
            user=test_user,
        )

    else:
        exp_logger = lw_klass.return_value

        found = await the_installation.get_room_configs(
            user=test_user,
            **authz_kwargs,
        )

        lw_klass.assert_called_once_with(
            loggers.AUTHZ_LOGGER_NAME,
            the_installation=the_installation,
            user=test_user,
        )

    if authz_kwargs:
        allowed = authz_kwargs["the_authz_policy"].allowed
        exp_logger.debug.assert_called_once_with(
            loggers.AUTHZ_FILTERING_ROOMS,
        )
        if allowed:
            assert found == r_configs
        else:
            assert found == {}
    else:
        assert found == r_configs
        exp_logger.debug.assert_called_once_with(
            loggers.AUTHZ_NOT_FILTERING_ROOMS,
        )


@pytest.mark.anyio
@pytest.mark.parametrize("w_the_logger", [False, True])
@pytest.mark.parametrize(
    "w_room_id, raises", [("room_id", False), ("nonesuch", True)]
)
@mock.patch("soliplex.loggers.LogWrapper")
async def test_installation_get_room_config(
    lw_klass,
    test_user,
    authz_kwargs,
    r_configs,
    the_logger,
    w_room_id,
    raises,
    w_the_logger,
):
    i_config = mock.create_autospec(config.InstallationConfig)
    i_config.room_configs = r_configs

    the_installation = installation.Installation(i_config)

    if authz_kwargs:
        allowed = authz_kwargs["the_authz_policy"].allowed
    else:
        allowed = True

    logger_kw = {}

    if w_the_logger:
        logger_kw["the_logger"] = the_logger
        exp_logger = the_logger.bind.return_value
    else:
        exp_logger = lw_klass.return_value

    if raises:
        with pytest.raises(KeyError):
            await the_installation.get_room_config(
                room_id=w_room_id,
                user=test_user,
                **authz_kwargs,
                **logger_kw,
            )
    else:
        if not allowed:
            with pytest.raises(KeyError):
                await the_installation.get_room_config(
                    room_id=w_room_id,
                    user=test_user,
                    **authz_kwargs,
                    **logger_kw,
                )
            exp_logger.error.assert_called_once_with(
                loggers.AUTHZ_ROOM_NOT_AUTHORIZED,
            )
        else:
            found = await the_installation.get_room_config(
                room_id=w_room_id,
                user=test_user,
                **authz_kwargs,
                **logger_kw,
            )

            assert found is r_configs[w_room_id]

            if authz_kwargs:
                exp_logger.debug.assert_called_once_with(
                    loggers.AUTHZ_ROOM_AUTHORIZED,
                )

    if w_the_logger:
        the_logger.bind.assert_called_once_with(
            loggers.AUTHZ_LOGGER_NAME,
            user=test_user,
        )
    else:
        lw_klass.assert_called_once_with(
            loggers.AUTHZ_LOGGER_NAME,
            the_installation=the_installation,
            user=test_user,
        )


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
        gafc.assert_called_once_with(
            agent_config=a_config,
            tool_configs={},
            mcp_client_toolset_configs={},
        )


@pytest.mark.anyio
@pytest.mark.parametrize("w_the_logger", [False, True])
@pytest.mark.parametrize(
    "w_room_id, raises", [("room_id", False), ("nonesuch", True)]
)
@mock.patch("soliplex.agents.get_agent_from_configs")
@mock.patch("soliplex.loggers.LogWrapper")
async def test_installation_get_agent_for_room(
    lw_klass,
    gafc,
    test_user,
    authz_kwargs,
    the_logger,
    w_room_id,
    raises,
    w_the_logger,
):
    a_config = mock.create_autospec(config.AgentConfig)

    tc_config = mock.create_autospec(config.ToolConfig)
    sdtc_config = mock.create_autospec(config.ToolConfig)

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

    if authz_kwargs:
        allowed = authz_kwargs["the_authz_policy"].allowed
    else:
        allowed = True

    the_installation = installation.Installation(i_config)

    logger_kw = {}

    if w_the_logger:
        logger_kw["the_logger"] = the_logger

    if raises:
        with pytest.raises(KeyError):
            await the_installation.get_agent_for_room(
                room_id=w_room_id,
                user=test_user,
                **authz_kwargs,
                **logger_kw,
            )
    else:
        if not allowed:
            with pytest.raises(KeyError):
                await the_installation.get_agent_for_room(
                    room_id=w_room_id,
                    user=test_user,
                    **authz_kwargs,
                    **logger_kw,
                )

            gafc.assert_not_called()

        else:
            found = await the_installation.get_agent_for_room(
                room_id=w_room_id,
                user=test_user,
                **authz_kwargs,
                **logger_kw,
            )

            assert found is gafc.return_value

            gafc.assert_called_once_with(
                agent_config=a_config,
                tool_configs=t_configs,
                mcp_client_toolset_configs=mcp_configs,
            )

    if w_the_logger:
        the_logger.bind.assert_called_once_with(
            loggers.AUTHZ_LOGGER_NAME,
            user=test_user,
        )
    else:
        lw_klass.assert_called_once_with(
            loggers.AUTHZ_LOGGER_NAME,
            the_installation=the_installation,
            user=test_user,
        )


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
    sdtc_config = mock.create_autospec(config.ToolConfig)

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
        gafc.assert_called_once_with(
            agent_config=a_config,
            tool_configs=t_configs,
            mcp_client_toolset_configs=mcp_configs,
        )


@pytest.mark.anyio
@pytest.mark.parametrize("w_the_logger", [False, True])
@pytest.mark.parametrize("w_run_agent_input", [False, True])
@pytest.mark.parametrize(
    "w_room_id, raises", [("room_id", False), ("nonesuch", True)]
)
@mock.patch("soliplex.loggers.LogWrapper")
async def test_installation_get_agent_deps_for_room(
    lw_klass,
    test_user,
    authz_kwargs,
    the_logger,
    w_room_id,
    raises,
    w_run_agent_input,
    w_the_logger,
):
    tc_config = mock.create_autospec(config.ToolConfig)
    sdtc_config = mock.create_autospec(config.ToolConfig)

    r_config = mock.create_autospec(config.RoomConfig)
    t_configs = r_config.tool_configs = {
        "test_tool": tc_config,
        "test_sdtc": sdtc_config,
    }

    r_configs = {"room_id": r_config}
    i_config = mock.create_autospec(config.InstallationConfig)
    i_config.room_configs = r_configs

    if authz_kwargs:
        allowed = authz_kwargs["the_authz_policy"].allowed
    else:
        allowed = True

    the_installation = installation.Installation(i_config)

    kw = {}
    if w_run_agent_input:
        kw["run_agent_input"] = RUN_AGENT_INPUT

    if w_the_logger:
        kw["the_logger"] = the_logger

    if raises:
        with pytest.raises(KeyError):
            await the_installation.get_agent_deps_for_room(
                room_id=w_room_id,
                user=test_user,
                **authz_kwargs,
                **kw,
            )
    else:
        if not allowed:
            with pytest.raises(KeyError):
                await the_installation.get_agent_deps_for_room(
                    room_id=w_room_id,
                    user=test_user,
                    **authz_kwargs,
                    **kw,
                )
        else:
            found = await the_installation.get_agent_deps_for_room(
                room_id=w_room_id,
                user=test_user,
                **authz_kwargs,
                **kw,
            )

            assert isinstance(found, agents.AgentDependencies)

            assert found.the_installation is the_installation
            assert found.user == test_user
            assert found.tool_configs == t_configs

    if w_the_logger:
        the_logger.bind.assert_called_once_with(
            loggers.AUTHZ_LOGGER_NAME,
            user=test_user,
        )
    else:
        lw_klass.assert_called_once_with(
            loggers.AUTHZ_LOGGER_NAME,
            the_installation=the_installation,
            user=test_user,
        )


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
    sdtc_config = mock.create_autospec(config.ToolConfig)

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


@pytest.mark.anyio
async def test_get_the_installation():
    i_config = mock.create_autospec(config.InstallationConfig)
    the_installation = installation.Installation(i_config)
    request = mock.create_autospec(fastapi.Request)
    request.state.the_installation = the_installation

    found = await installation.get_the_installation(request)

    assert found is the_installation


@pytest.mark.parametrize("w_disable_lc", [None, False, True])
@pytest.mark.parametrize("w_logfire_config", [None, "bare", "ipydai", "ifapi"])
@mock.patch("soliplex.installation.logfire")
def test_apply_logfire_configuration(logfire, w_logfire_config, w_disable_lc):
    app = mock.Mock(spec_set=())
    the_installation = mock.Mock(spec_set=["logfire_config"])

    kwargs = {}

    if w_disable_lc is not None:
        kwargs["disable_logfire_console"] = w_disable_lc

    if w_logfire_config is not None:
        logfire_config = mock.create_autospec(config.LogfireConfig)
        logfire_config.logfire_config_kwargs = {"foo": "bar"}

        if w_logfire_config == "ipydai":
            ipydai = logfire_config.instrument_pydantic_ai
            ipydai.instrument_pydantic_ai_kwargs = {"baz": "bam"}
        else:
            logfire_config.instrument_pydantic_ai = None

        if w_logfire_config == "ifapi":
            ifapi = logfire_config.instrument_fast_api
            ifapi.instrument_fast_api_kwargs = {"qux": "spam"}
        else:
            logfire_config.instrument_fast_api = None

        the_installation.logfire_config = logfire_config
    else:
        the_installation.logfire_config = None

    installation.apply_logfire_configuration(app, the_installation, **kwargs)

    if w_logfire_config is not None:
        logfire.configure.assert_called_once_with(
            foo="bar",
            console=False,
        )

        if w_logfire_config == "ipydai":
            logfire.instrument_pydantic_ai.assert_called_once_with(
                baz="bam",
            )
        elif w_logfire_config == "ifapi":
            logfire.instrument_fastapi.assert_called_once_with(
                app,
                qux="spam",
            )
    else:
        if w_disable_lc:
            logfire.configure.assert_called_once_with(
                send_to_logfire="if-token-present",
                console=False,
            )
        else:
            logfire.configure.assert_called_once_with(
                send_to_logfire="if-token-present",
            )

        logfire.instrument_pydantic_ai.assert_called_with()
        logfire.instrument_fastapi.assert_called_with(
            app,
            capture_headers=True,
        )


def test_add_user_as_admin():
    conn = mock.create_autospec(sqlalchemy.Connection)

    installation.add_user_as_admin(conn, email=ADMIN_USER_EMAIL)

    (insert_call,) = conn.execute.call_args_list
    (insert,) = insert_call.args
    assert insert.table.name == "admin_users"


@pytest.mark.parametrize("w_admin_user", [False, True])
@mock.patch("soliplex.installation.add_user_as_admin")
def test_add_no_auth_user_as_admin(auaa, w_admin_user):
    already = object()
    query_result = mock.Mock(spec_set=["first"])
    insert_result = mock.Mock(spec_set=())

    if w_admin_user:
        query_result.first.return_value = already
    else:
        query_result.first.return_value = None

    conn = mock.create_autospec(sqlalchemy.Connection)

    if w_admin_user:  # no call to insert
        conn.execute.side_effect = [
            query_result,
        ]
    else:
        conn.execute.side_effect = [
            query_result,
            insert_result,
        ]

    installation.add_no_auth_user_as_admin(conn)

    (query_call,) = conn.execute.call_args_list
    (query,) = query_call.args
    assert str(query).startswith("SELECT admin_users")

    if not w_admin_user:
        (auaa_called,) = auaa.call_args_list
        (conn,) = auaa_called.args
        assert isinstance(conn, sqlalchemy.Connection)
        assert auaa_called.kwargs == {
            "email": installation.NO_AUTH_MODE_USER_TOKEN["email"],
        }


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
@pytest.mark.parametrize("w_add_admin_user", [None, ADMIN_USER_EMAIL])
@pytest.mark.parametrize(
    "w_ic_logging_config",
    [
        None,
        {"version": 1, "root": {"level": "DEBUG"}},
    ],
)
@pytest.mark.parametrize("w_log_config_file", [None, LOG_CONFIG_FILE])
@pytest.mark.parametrize(
    "w_no_auth_mode, exp_oidc_paths",
    [
        (None, ["oidc"]),
        (False, ["oidc"]),
        (True, []),
    ],
)
@mock.patch("soliplex.installation.add_no_auth_user_as_admin")
@mock.patch("soliplex.installation.add_user_as_admin")
@mock.patch("soliplex.installation.apply_logfire_configuration")
@mock.patch("soliplex.secrets.resolve_secrets")
@mock.patch("soliplex.mcp_server.setup_mcp_for_rooms")
@mock.patch("soliplex.config.load_installation")
@mock.patch("logging.config.dictConfig")
async def test_lifespan(
    lcdc,
    load_installation,
    smfr,
    srs,
    alc,
    auaa,
    anauaa,
    mcp_apps,
    temp_dir,
    w_no_auth_mode,
    exp_oidc_paths,
    w_log_config_file,
    w_ic_logging_config,
    w_add_admin_user,
):
    INSTALLATION_PATH = "/path/to/installation"

    smfr.return_value = mcp_apps

    i_config = mock.create_autospec(
        config.InstallationConfig,
        secrets=(),
        oidc_paths=["oidc"],
        environment={"OLLAMA_BASE_URL": OLLAMA_BASE_URL},
        logging_config=w_ic_logging_config,
        thread_persistence_dburi_async=config.ASYNC_MEMORY_ENGINE_URL,
        authorization_dburi_async=config.ASYNC_MEMORY_ENGINE_URL,
    )
    load_installation.return_value = i_config
    app = mock.create_autospec(fastapi.FastAPI)

    kwargs = {
        "installation_path": INSTALLATION_PATH,
    }
    if w_no_auth_mode is not None:
        exp_no_auth_mode = kwargs["no_auth_mode"] = w_no_auth_mode
    else:
        exp_no_auth_mode = False

    if w_log_config_file is not None:
        w_log_config_file = temp_dir / w_log_config_file
        w_log_config_file.write_text("""\
version: 1

root:
    level: INFO
""")
        kwargs["log_config_file"] = str(w_log_config_file)

    if w_add_admin_user is not None:
        kwargs["add_admin_user"] = w_add_admin_user

    found = [
        item
        async for item in installation.lifespan(
            app,
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
    assert threads_engine.dialect._json_serializer is util.serialize_sqla_json

    authorization_engine = found[0]["authorization_engine"]
    assert isinstance(authorization_engine, sqla_asyncio.AsyncEngine)
    assert threads_engine.dialect._json_serializer is util.serialize_sqla_json

    for f_call, (key, mcp_app) in zip(
        app.mount.call_args_list,
        mcp_apps.items(),
        strict=True,
    ):
        assert f_call.args == ("/mcp/" + key, mcp_app)

    if w_log_config_file is not None:
        lcdc.assert_called_once_with({"version": 1, "root": {"level": "INFO"}})
        exp_lc_disable = True
    elif w_ic_logging_config is not None:
        lcdc.assert_called_once_with(w_ic_logging_config)
        exp_lc_disable = True
    else:
        lcdc.assert_not_called()
        exp_lc_disable = False

    if w_add_admin_user:
        (auaa_called,) = auaa.call_args_list
        (conn,) = auaa_called.args
        assert isinstance(conn, sqlalchemy.Connection)
        assert auaa_called.kwargs == {"email": w_add_admin_user}
    elif exp_no_auth_mode:
        (anauaa_called,) = anauaa.call_args_list
        (conn,) = anauaa_called.args
        assert isinstance(conn, sqlalchemy.Connection)
        assert anauaa_called.kwargs == {}
    else:
        anauaa.assert_not_called()

    alc.assert_called_once_with(app, the_installation, exp_lc_disable)
    srs.assert_called_once_with(the_installation._config.secrets)
    smfr.assert_called_once_with(the_installation)
