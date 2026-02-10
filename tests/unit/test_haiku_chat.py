import pathlib
from unittest import mock

import pytest
import yaml
from haiku.rag.agents import chat as hr_agents_chat
from haiku.rag.agents.chat import state as hr_agents_chat_state

from soliplex import agents
from soliplex import config
from soliplex import haiku_chat

ROOM_ID = "test-chat-room"
RAG_DB_PATH = "/path/to/rag.lancedb"
RAG_LANCEDB_STEM = "test_rag"
RAG_BASE_PATH = "/base/path"

BOGUS_CHAT_AGENT_CONFIG_YAML = ""
BOGUS_TEMPLATE_AGENT_ID = "BOGUS"

AGENT_ID = "test-agent-id"
TEMPLATE_AGENT_ID = "template-agent-id"
TEMPLATE_STEM = "template_rag"
BACKGROUND_CONTEXT = "Test background context"
OTHER_BACKGROUND_CONTEXT = "Other background context"

W_RAG_STEM_CHAT_AGENT_CONFIG_KW = {
    "id": AGENT_ID,
    "rag_lancedb_stem": RAG_LANCEDB_STEM,
}
W_RAG_STEM_CHAT_AGENT_CONFIG_YAML = f"""
id: "{AGENT_ID}"
rag_lancedb_stem: "{RAG_LANCEDB_STEM}"
"""

W_RAG_OVR_CHAT_AGENT_CONFIG_KW = {
    "id": AGENT_ID,
    "rag_lancedb_override_path": RAG_DB_PATH,
}
W_RAG_OVR_CHAT_AGENT_CONFIG_YAML = f"""
id: "{AGENT_ID}"
rag_lancedb_override_path: "{RAG_DB_PATH}"
"""

W_BKG_CONTEXT_AGENT_CONFIG_KW = W_RAG_STEM_CHAT_AGENT_CONFIG_KW | {
    "background_context": BACKGROUND_CONTEXT,
}
W_BKG_CONTEXT_AGENT_CONFIG_YAML = f"""\
{W_RAG_STEM_CHAT_AGENT_CONFIG_YAML}
background_context: |
    {BACKGROUND_CONTEXT}
"""

W_BOGUS_TEMPLATE_ID_CHAT_AGENT_CONFIG_YAML = f"""
id: "{AGENT_ID}"
template_id: "{BOGUS_TEMPLATE_AGENT_ID}"
"""

W_TEMPLATE_ID_W_STEM_CHAT_AGENT_CONFIG_KW = W_RAG_STEM_CHAT_AGENT_CONFIG_KW | {
    "_template_id": TEMPLATE_AGENT_ID,
}
W_TEMPLATE_ID_W_STEM_CHAT_AGENT_CONFIG_YAML = f"""
{W_RAG_STEM_CHAT_AGENT_CONFIG_YAML}
template_id: "{TEMPLATE_AGENT_ID}"
"""

W_TEMPLATE_ID_W_OVR_CHAT_AGENT_CONFIG_KW = W_RAG_OVR_CHAT_AGENT_CONFIG_KW | {
    "_template_id": TEMPLATE_AGENT_ID,
}
W_TEMPLATE_ID_W_OVR_CHAT_AGENT_CONFIG_YAML = f"""
{W_RAG_OVR_CHAT_AGENT_CONFIG_YAML}
template_id: "{TEMPLATE_AGENT_ID}"
"""


@pytest.fixture
def mock_installation_config():
    ic = mock.MagicMock(spec=config.InstallationConfig)
    ic.haiku_rag_config = mock.MagicMock()
    ic.get_environment.return_value = RAG_BASE_PATH
    return ic


@pytest.fixture
def factory_agent_config(mock_installation_config):
    ac = mock.MagicMock(spec=config.FactoryAgentConfig)
    ac.kind = "factory"
    ac.id = ROOM_ID
    ac._installation_config = mock_installation_config
    ac.extra_config = {"rag_lancedb_stem": RAG_LANCEDB_STEM}
    return ac


@pytest.fixture
def factory_agent_config_w_override(mock_installation_config):
    ac = mock.MagicMock(spec=config.FactoryAgentConfig)
    ac.kind = "factory"
    ac.id = ROOM_ID
    ac._installation_config = mock_installation_config
    ac.extra_config = {"rag_lancedb_override_path": RAG_DB_PATH}
    return ac


@mock.patch("soliplex.haiku_chat.hr_agents_chat_agent")
def test_chat_agent_factory_w_stem(
    hr_agents_chat_agent,
    factory_agent_config,
    mock_installation_config,
):
    mock_agent = mock.MagicMock()
    hr_agents_chat_agent.create_chat_agent.return_value = mock_agent

    result = haiku_chat.chat_agent_factory(
        agent_config=factory_agent_config,
        tool_configs={},
        mcp_client_toolset_configs={},
    )

    assert isinstance(result, haiku_chat.ChatAgentWrapper)
    assert result.agent is mock_agent
    assert result.config is mock_installation_config.haiku_rag_config
    assert result.db_path == (
        pathlib.Path(RAG_BASE_PATH) / f"{RAG_LANCEDB_STEM}.lancedb"
    )

    hr_agents_chat_agent.create_chat_agent.assert_called_once_with(
        mock_installation_config.haiku_rag_config
    )


@mock.patch("soliplex.haiku_chat.hr_agents_chat_agent")
def test_chat_agent_factory_w_override_path(
    hr_agents_chat_agent,
    factory_agent_config_w_override,
    mock_installation_config,
):
    mock_agent = mock.MagicMock()
    hr_agents_chat_agent.create_chat_agent.return_value = mock_agent

    result = haiku_chat.chat_agent_factory(
        agent_config=factory_agent_config_w_override,
        tool_configs={},
        mcp_client_toolset_configs={},
    )

    assert isinstance(result, haiku_chat.ChatAgentWrapper)
    assert result.db_path == pathlib.Path(RAG_DB_PATH)


@pytest.mark.asyncio
@mock.patch("soliplex.haiku_chat.hr_client")
async def test_chat_agent_wrapper_run_stream_events_wo_state(hr_client):
    mock_agent = mock.MagicMock()
    mock_config = mock.MagicMock()
    mock_client = mock.MagicMock()

    hr_client.HaikuRAG.return_value.__aenter__.return_value = mock_client

    async def mock_events():
        yield "event1"
        yield "event2"

    mock_agent.run_stream_events.return_value = mock_events()

    wrapper = haiku_chat.ChatAgentWrapper(
        agent=mock_agent,
        config=mock_config,
        db_path=pathlib.Path(RAG_DB_PATH),
    )

    mock_deps = mock.MagicMock(spec=agents.AgentDependencies)
    mock_deps.state = {}

    events = []
    async for event in wrapper.run_stream_events(
        message_history=[],
        deps=mock_deps,
    ):
        events.append(event)

    assert events == ["event1", "event2"]

    hr_client.HaikuRAG.assert_called_once_with(
        db_path=pathlib.Path(RAG_DB_PATH),
        config=mock_config,
    )

    call_kwargs = mock_agent.run_stream_events.call_args.kwargs
    assert call_kwargs["message_history"] == []
    chat_deps = call_kwargs["deps"]
    assert chat_deps.client is mock_client
    assert chat_deps.config is mock_config
    assert chat_deps.session_state is not None
    # session_id starts empty, assigned by agent layer
    assert chat_deps.session_state.session_id == ""


@pytest.mark.asyncio
@mock.patch("soliplex.haiku_chat.hr_client")
async def test_chat_agent_wrapper_run_stream_events_w_state(hr_client):
    mock_agent = mock.MagicMock()
    mock_config = mock.MagicMock()
    mock_client = mock.MagicMock()

    hr_client.HaikuRAG.return_value.__aenter__.return_value = mock_client

    async def mock_events():
        yield "event1"

    mock_agent.run_stream_events.return_value = mock_events()

    wrapper = haiku_chat.ChatAgentWrapper(
        agent=mock_agent,
        config=mock_config,
        db_path=pathlib.Path(RAG_DB_PATH),
    )

    existing_state = hr_agents_chat_state.ChatSessionState(
        session_id="test-session",
        citations=[],
        qa_history=[],
    )

    mock_deps = mock.MagicMock(spec=agents.AgentDependencies)
    mock_deps.state = {
        hr_agents_chat.AGUI_STATE_KEY: existing_state.model_dump(),
    }

    events = []
    async for event in wrapper.run_stream_events(
        message_history=[],
        deps=mock_deps,
    ):
        events.append(event)

    call_kwargs = mock_agent.run_stream_events.call_args.kwargs
    chat_deps = call_kwargs["deps"]
    assert chat_deps.session_state.session_id == "test-session"


@pytest.mark.asyncio
@mock.patch("soliplex.haiku_chat.hr_client")
async def test_chat_agent_wrapper_passes_kwargs(hr_client):
    mock_agent = mock.MagicMock()
    mock_config = mock.MagicMock()
    mock_client = mock.MagicMock()

    hr_client.HaikuRAG.return_value.__aenter__.return_value = mock_client

    async def mock_events():
        yield "event"

    mock_agent.run_stream_events.return_value = mock_events()

    wrapper = haiku_chat.ChatAgentWrapper(
        agent=mock_agent,
        config=mock_config,
        db_path=pathlib.Path(RAG_DB_PATH),
    )

    mock_deps = mock.MagicMock(spec=agents.AgentDependencies)
    mock_deps.state = {}

    mock_output_type = mock.MagicMock()
    mock_message_history = [mock.MagicMock()]
    mock_deferred = mock.MagicMock()

    events = []
    async for event in wrapper.run_stream_events(
        output_type=mock_output_type,
        message_history=mock_message_history,
        deferred_tool_results=mock_deferred,
        deps=mock_deps,
        extra_kwarg="test_value",
    ):
        events.append(event)

    call_kwargs = mock_agent.run_stream_events.call_args.kwargs
    assert call_kwargs["output_type"] is mock_output_type
    assert call_kwargs["message_history"] is mock_message_history
    assert call_kwargs["deferred_tool_results"] is mock_deferred
    assert call_kwargs["extra_kwarg"] == "test_value"


@pytest.mark.asyncio
@mock.patch("soliplex.haiku_chat.hr_client")
async def test_chat_agent_wrapper_passes_state_key(hr_client):
    """Test that state_key is passed to ChatDeps."""
    mock_agent = mock.MagicMock()
    mock_config = mock.MagicMock()
    mock_client = mock.MagicMock()

    hr_client.HaikuRAG.return_value.__aenter__.return_value = mock_client

    async def mock_events():
        yield "event"

    mock_agent.run_stream_events.return_value = mock_events()

    wrapper = haiku_chat.ChatAgentWrapper(
        agent=mock_agent,
        config=mock_config,
        db_path=pathlib.Path(RAG_DB_PATH),
    )

    mock_deps = mock.MagicMock(spec=agents.AgentDependencies)
    mock_deps.state = {}

    events = []
    async for event in wrapper.run_stream_events(
        message_history=[],
        deps=mock_deps,
    ):
        events.append(event)

    call_kwargs = mock_agent.run_stream_events.call_args.kwargs
    chat_deps = call_kwargs["deps"]
    assert chat_deps.state_key == hr_agents_chat.AGUI_STATE_KEY


def test_resolve_db_path_w_override(mock_installation_config):
    extra_config = {"rag_lancedb_override_path": RAG_DB_PATH}
    result = haiku_chat._resolve_db_path(
        extra_config, mock_installation_config
    )
    assert result == pathlib.Path(RAG_DB_PATH)


def test_resolve_db_path_w_stem(mock_installation_config):
    extra_config = {"rag_lancedb_stem": RAG_LANCEDB_STEM}
    result = haiku_chat._resolve_db_path(
        extra_config, mock_installation_config
    )
    assert result == (
        pathlib.Path(RAG_BASE_PATH) / f"{RAG_LANCEDB_STEM}.lancedb"
    )


def test_resolve_db_path_w_default_stem(mock_installation_config):
    extra_config = {}
    result = haiku_chat._resolve_db_path(
        extra_config, mock_installation_config
    )
    assert result == pathlib.Path(RAG_BASE_PATH) / "rag.lancedb"


@mock.patch("soliplex.haiku_chat.hr_agents_chat_agent")
def test_chat_agent_factory_extracts_background_context(
    hr_agents_chat_agent,
    mock_installation_config,
):
    """Test that factory extracts background_context from extra_config."""
    mock_agent = mock.MagicMock()
    hr_agents_chat_agent.create_chat_agent.return_value = mock_agent

    ac = mock.MagicMock(spec=config.FactoryAgentConfig)
    ac.kind = "factory"
    ac.id = ROOM_ID
    ac._installation_config = mock_installation_config
    ac.extra_config = {
        "rag_lancedb_stem": RAG_LANCEDB_STEM,
        "background_context": "Focus on medical regulations.",
    }

    result = haiku_chat.chat_agent_factory(
        agent_config=ac,
        tool_configs={},
        mcp_client_toolset_configs={},
    )

    assert result.background_context == "Focus on medical regulations."


@pytest.mark.asyncio
@mock.patch("soliplex.haiku_chat.hr_client")
async def test_chat_agent_wrapper_sets_initial_context_from_background(
    hr_client,
):
    """Test that background_context sets initial_context on session state."""
    mock_agent = mock.MagicMock()
    mock_config = mock.MagicMock()
    mock_client = mock.MagicMock()

    hr_client.HaikuRAG.return_value.__aenter__.return_value = mock_client

    async def mock_events():
        yield "event"

    mock_agent.run_stream_events.return_value = mock_events()

    wrapper = haiku_chat.ChatAgentWrapper(
        agent=mock_agent,
        config=mock_config,
        db_path=pathlib.Path(RAG_DB_PATH),
        background_context="Configured context from room.",
    )

    existing_state = hr_agents_chat_state.ChatSessionState()
    mock_deps = mock.MagicMock(spec=agents.AgentDependencies)
    mock_deps.state = {
        hr_agents_chat.AGUI_STATE_KEY: existing_state.model_dump(),
    }

    events = []
    async for event in wrapper.run_stream_events(
        message_history=[],
        deps=mock_deps,
    ):
        events.append(event)

    call_kwargs = mock_agent.run_stream_events.call_args.kwargs
    chat_deps = call_kwargs["deps"]
    assert chat_deps.session_state.initial_context == (
        "Configured context from room."
    )


@pytest.mark.asyncio
@mock.patch("soliplex.haiku_chat.hr_client")
async def test_chat_agent_wrapper_does_not_override_existing_initial_context(
    hr_client,
):
    """Test that existing initial_context is not overwritten by background."""
    mock_agent = mock.MagicMock()
    mock_config = mock.MagicMock()
    mock_client = mock.MagicMock()

    hr_client.HaikuRAG.return_value.__aenter__.return_value = mock_client

    async def mock_events():
        yield "event"

    mock_agent.run_stream_events.return_value = mock_events()

    wrapper = haiku_chat.ChatAgentWrapper(
        agent=mock_agent,
        config=mock_config,
        db_path=pathlib.Path(RAG_DB_PATH),
        background_context="Configured context from room.",
    )

    existing_state = hr_agents_chat_state.ChatSessionState(
        initial_context="Existing context.",
    )

    mock_deps = mock.MagicMock(spec=agents.AgentDependencies)
    mock_deps.state = {
        hr_agents_chat.AGUI_STATE_KEY: existing_state.model_dump(),
    }

    events = []
    async for event in wrapper.run_stream_events(
        message_history=[],
        deps=mock_deps,
    ):
        events.append(event)

    call_kwargs = mock_agent.run_stream_events.call_args.kwargs
    chat_deps = call_kwargs["deps"]
    assert chat_deps.session_state.initial_context == "Existing context."


@pytest.fixture
def installation_config():
    return mock.create_autospec(config.InstallationConfig)


@pytest.mark.parametrize(
    "config_yaml, expected_kw",
    [
        (BOGUS_CHAT_AGENT_CONFIG_YAML, None),
        (
            W_RAG_STEM_CHAT_AGENT_CONFIG_YAML,
            W_RAG_STEM_CHAT_AGENT_CONFIG_KW.copy(),
        ),
        (
            W_RAG_OVR_CHAT_AGENT_CONFIG_YAML,
            W_RAG_OVR_CHAT_AGENT_CONFIG_KW.copy(),
        ),
        (
            W_BKG_CONTEXT_AGENT_CONFIG_YAML,
            W_BKG_CONTEXT_AGENT_CONFIG_KW.copy(),
        ),
        (W_BOGUS_TEMPLATE_ID_CHAT_AGENT_CONFIG_YAML, None),
        (
            W_TEMPLATE_ID_W_STEM_CHAT_AGENT_CONFIG_YAML,
            W_TEMPLATE_ID_W_STEM_CHAT_AGENT_CONFIG_KW.copy(),
        ),
        (
            W_TEMPLATE_ID_W_OVR_CHAT_AGENT_CONFIG_YAML,
            W_TEMPLATE_ID_W_OVR_CHAT_AGENT_CONFIG_KW.copy(),
        ),
    ],
)
def test_chatagentconfig_from_yaml(
    installation_config,
    temp_dir,
    config_yaml,
    expected_kw,
):
    yaml_file = temp_dir / "test.yaml"
    yaml_file.write_text(config_yaml)

    with yaml_file.open() as stream:
        config_dict = yaml.safe_load(stream)

    if config_dict is not None:
        template_id = config_dict.get("template_id")
    else:
        template_id = None

    if template_id not in (None, BOGUS_TEMPLATE_AGENT_ID):
        template_kw = {
            "background_context": OTHER_BACKGROUND_CONTEXT,
            "rag_lancedb_stem": TEMPLATE_STEM,
        }
        installation_config.agent_configs = [
            haiku_chat.ChatAgentConfig(id=template_id, **template_kw),
        ]
    else:
        template_kw = {}
        installation_config.agent_configs = []

    if expected_kw is None:
        with pytest.raises(config.FromYamlException):
            haiku_chat.ChatAgentConfig.from_yaml(
                installation_config,
                yaml_file,
                config_dict,
            )
    else:
        if "rag_lancedb_stem" in expected_kw:
            template_kw.pop("rag_lancedb_override_path", None)

        if "rag_lancedb_override_path" in expected_kw:
            template_kw.pop("rag_lancedb_stem", None)

        expected = haiku_chat.ChatAgentConfig(
            _installation_config=installation_config,
            _config_path=yaml_file,
            **(template_kw | expected_kw),
        )

        found = haiku_chat.ChatAgentConfig.from_yaml(
            installation_config,
            yaml_file,
            config_dict,
        )

        assert found == expected


@pytest.mark.parametrize(
    "ctor_kw",
    [
        W_RAG_STEM_CHAT_AGENT_CONFIG_KW.copy(),
        W_RAG_OVR_CHAT_AGENT_CONFIG_KW.copy(),
    ],
)
def test_chatagentconfig_agui_feature_names(ctor_kw):
    cac = haiku_chat.ChatAgentConfig(**ctor_kw)

    assert cac.agui_feature_names == ("haiku.rag.chat",)


@pytest.mark.parametrize(
    "ctor_kw",
    [
        W_RAG_STEM_CHAT_AGENT_CONFIG_KW.copy(),
        W_RAG_OVR_CHAT_AGENT_CONFIG_KW.copy(),
        W_BKG_CONTEXT_AGENT_CONFIG_KW.copy(),
        W_TEMPLATE_ID_W_STEM_CHAT_AGENT_CONFIG_KW.copy(),
        W_TEMPLATE_ID_W_OVR_CHAT_AGENT_CONFIG_KW.copy(),
    ],
)
def test_chatagentconfig_as_yaml(ctor_kw):
    cac = haiku_chat.ChatAgentConfig(**ctor_kw)

    found = cac.as_yaml

    expected = ctor_kw.copy()
    expected.pop("_template_id", None)

    assert found == expected


@pytest.mark.parametrize(
    "ctor_kw",
    [
        W_RAG_STEM_CHAT_AGENT_CONFIG_KW.copy(),
        W_RAG_OVR_CHAT_AGENT_CONFIG_KW.copy(),
        W_BKG_CONTEXT_AGENT_CONFIG_KW.copy(),
    ],
)
@mock.patch("soliplex.haiku_chat.hr_agents_chat_agent")
def test_chatagentconfig_factory(
    hr_agents_chat_agent,
    temp_dir,
    ctor_kw,
):
    db_path = temp_dir / "db"
    db_path.mkdir()
    ic_enviro = {"RAG_LANCE_DB_PATH": str(db_path)}
    i_config = mock.create_autospec(config.InstallationConfig)
    i_config.get_environment = ic_enviro.get

    if "rag_lancedb_override_path" in ctor_kw:
        rag_path = temp_dir / "override" / "rag.lancedb"
        ctor_kw["rag_lancedb_override_path"] = rag_path
    else:
        rag_path = db_path / f"{ctor_kw['rag_lancedb_stem']}.lancedb"

    rag_path.mkdir(parents=True)

    cac = haiku_chat.ChatAgentConfig(
        **ctor_kw,
        _installation_config=i_config,
        _config_path=temp_dir / "test.yaml",
    )

    found = cac.factory()

    assert isinstance(found, haiku_chat.ChatAgentWrapper)

    assert found.agent is hr_agents_chat_agent.create_chat_agent.return_value
    assert found.config is i_config.haiku_rag_config
    assert found.db_path == rag_path.resolve()
    assert found.background_context == cac.background_context

    hr_agents_chat_agent.create_chat_agent.assert_called_once_with(
        i_config.haiku_rag_config
    )
