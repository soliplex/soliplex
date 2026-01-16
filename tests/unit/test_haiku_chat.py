from pathlib import Path
from unittest import mock

import pytest

from soliplex import agents
from soliplex import config
from soliplex import haiku_chat

ROOM_ID = "test-chat-room"
RAG_DB_PATH = "/path/to/rag.lancedb"
RAG_LANCEDB_STEM = "test_rag"
RAG_BASE_PATH = "/base/path"


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


@mock.patch("soliplex.haiku_chat.create_chat_agent")
def test_chat_agent_factory_w_stem(
    mock_create_chat_agent,
    factory_agent_config,
    mock_installation_config,
):
    mock_agent = mock.MagicMock()
    mock_create_chat_agent.return_value = mock_agent

    result = haiku_chat.chat_agent_factory(
        agent_config=factory_agent_config,
        tool_configs={},
        mcp_client_toolset_configs={},
    )

    assert isinstance(result, haiku_chat.ChatAgentWrapper)
    assert result.agent is mock_agent
    assert result.config is mock_installation_config.haiku_rag_config
    assert (
        result.db_path == Path(RAG_BASE_PATH) / f"{RAG_LANCEDB_STEM}.lancedb"
    )

    mock_create_chat_agent.assert_called_once_with(
        mock_installation_config.haiku_rag_config
    )


@mock.patch("soliplex.haiku_chat.create_chat_agent")
def test_chat_agent_factory_w_override_path(
    mock_create_chat_agent,
    factory_agent_config_w_override,
    mock_installation_config,
):
    mock_agent = mock.MagicMock()
    mock_create_chat_agent.return_value = mock_agent

    result = haiku_chat.chat_agent_factory(
        agent_config=factory_agent_config_w_override,
        tool_configs={},
        mcp_client_toolset_configs={},
    )

    assert isinstance(result, haiku_chat.ChatAgentWrapper)
    assert result.db_path == Path(RAG_DB_PATH)


@pytest.mark.asyncio
@mock.patch("soliplex.haiku_chat.HaikuRAG")
async def test_chat_agent_wrapper_run_stream_events_wo_state(mock_haiku_rag):
    mock_agent = mock.MagicMock()
    mock_config = mock.MagicMock()
    mock_client = mock.MagicMock()

    mock_haiku_rag.return_value.__aenter__.return_value = mock_client

    async def mock_events():
        yield "event1"
        yield "event2"

    mock_agent.run_stream_events.return_value = mock_events()

    wrapper = haiku_chat.ChatAgentWrapper(
        agent=mock_agent,
        config=mock_config,
        db_path=Path(RAG_DB_PATH),
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

    mock_haiku_rag.assert_called_once_with(
        db_path=Path(RAG_DB_PATH),
        config=mock_config,
    )

    call_kwargs = mock_agent.run_stream_events.call_args.kwargs
    assert call_kwargs["message_history"] == []
    chat_deps = call_kwargs["deps"]
    assert chat_deps.client is mock_client
    assert chat_deps.config is mock_config
    assert chat_deps.session_state is not None
    assert chat_deps.session_state.session_id == ""


@pytest.mark.asyncio
@mock.patch("soliplex.haiku_chat.HaikuRAG")
async def test_chat_agent_wrapper_run_stream_events_w_state(mock_haiku_rag):
    from haiku.rag.agents.chat.state import ChatSessionState

    mock_agent = mock.MagicMock()
    mock_config = mock.MagicMock()
    mock_client = mock.MagicMock()

    mock_haiku_rag.return_value.__aenter__.return_value = mock_client

    async def mock_events():
        yield "event1"

    mock_agent.run_stream_events.return_value = mock_events()

    wrapper = haiku_chat.ChatAgentWrapper(
        agent=mock_agent,
        config=mock_config,
        db_path=Path(RAG_DB_PATH),
    )

    existing_state = ChatSessionState(
        session_id="test-session",
        citations=[],
        qa_history=[],
    )

    mock_deps = mock.MagicMock(spec=agents.AgentDependencies)
    mock_deps.state = {haiku_chat.AGUI_STATE_KEY: existing_state.model_dump()}

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
@mock.patch("soliplex.haiku_chat.HaikuRAG")
async def test_chat_agent_wrapper_passes_kwargs(mock_haiku_rag):
    mock_agent = mock.MagicMock()
    mock_config = mock.MagicMock()
    mock_client = mock.MagicMock()

    mock_haiku_rag.return_value.__aenter__.return_value = mock_client

    async def mock_events():
        yield "event"

    mock_agent.run_stream_events.return_value = mock_events()

    wrapper = haiku_chat.ChatAgentWrapper(
        agent=mock_agent,
        config=mock_config,
        db_path=Path(RAG_DB_PATH),
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
@mock.patch("soliplex.haiku_chat.HaikuRAG")
async def test_chat_agent_wrapper_passes_state_key(mock_haiku_rag):
    """Test that state_key is passed to ChatDeps."""
    mock_agent = mock.MagicMock()
    mock_config = mock.MagicMock()
    mock_client = mock.MagicMock()

    mock_haiku_rag.return_value.__aenter__.return_value = mock_client

    async def mock_events():
        yield "event"

    mock_agent.run_stream_events.return_value = mock_events()

    wrapper = haiku_chat.ChatAgentWrapper(
        agent=mock_agent,
        config=mock_config,
        db_path=Path(RAG_DB_PATH),
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
    assert chat_deps.state_key == haiku_chat.AGUI_STATE_KEY


def test_resolve_db_path_w_override(mock_installation_config):
    extra_config = {"rag_lancedb_override_path": RAG_DB_PATH}
    result = haiku_chat._resolve_db_path(
        extra_config, mock_installation_config
    )
    assert result == Path(RAG_DB_PATH)


def test_resolve_db_path_w_stem(mock_installation_config):
    extra_config = {"rag_lancedb_stem": RAG_LANCEDB_STEM}
    result = haiku_chat._resolve_db_path(
        extra_config, mock_installation_config
    )
    assert result == Path(RAG_BASE_PATH) / f"{RAG_LANCEDB_STEM}.lancedb"


def test_resolve_db_path_w_default_stem(mock_installation_config):
    extra_config = {}
    result = haiku_chat._resolve_db_path(
        extra_config, mock_installation_config
    )
    assert result == Path(RAG_BASE_PATH) / "rag.lancedb"


@mock.patch("soliplex.haiku_chat.create_chat_agent")
def test_chat_agent_factory_extracts_background_context(
    mock_create_chat_agent,
    mock_installation_config,
):
    """Test that factory extracts background_context from extra_config."""
    mock_agent = mock.MagicMock()
    mock_create_chat_agent.return_value = mock_agent

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
@mock.patch("soliplex.haiku_chat.HaikuRAG")
async def test_chat_agent_wrapper_uses_configured_background_context(
    mock_haiku_rag,
):
    """Test that configured background_context is used when state has none."""
    mock_agent = mock.MagicMock()
    mock_config = mock.MagicMock()
    mock_client = mock.MagicMock()

    mock_haiku_rag.return_value.__aenter__.return_value = mock_client

    async def mock_events():
        yield "event"

    mock_agent.run_stream_events.return_value = mock_events()

    wrapper = haiku_chat.ChatAgentWrapper(
        agent=mock_agent,
        config=mock_config,
        db_path=Path(RAG_DB_PATH),
        background_context="Configured context from room.",
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
    assert chat_deps.session_state.background_context == (
        "Configured context from room."
    )


@pytest.mark.asyncio
@mock.patch("soliplex.haiku_chat.HaikuRAG")
async def test_chat_agent_wrapper_configured_context_overrides_frontend(
    mock_haiku_rag,
):
    """Test that configured background_context overrides frontend state."""
    from haiku.rag.agents.chat.state import ChatSessionState

    mock_agent = mock.MagicMock()
    mock_config = mock.MagicMock()
    mock_client = mock.MagicMock()

    mock_haiku_rag.return_value.__aenter__.return_value = mock_client

    async def mock_events():
        yield "event"

    mock_agent.run_stream_events.return_value = mock_events()

    wrapper = haiku_chat.ChatAgentWrapper(
        agent=mock_agent,
        config=mock_config,
        db_path=Path(RAG_DB_PATH),
        background_context="Configured context from room.",
    )

    existing_state = ChatSessionState(
        session_id="test-session",
        background_context="Frontend user context.",
    )

    mock_deps = mock.MagicMock(spec=agents.AgentDependencies)
    mock_deps.state = {haiku_chat.AGUI_STATE_KEY: existing_state.model_dump()}

    events = []
    async for event in wrapper.run_stream_events(
        message_history=[],
        deps=mock_deps,
    ):
        events.append(event)

    call_kwargs = mock_agent.run_stream_events.call_args.kwargs
    chat_deps = call_kwargs["deps"]
    # Configured context should override frontend
    assert (
        chat_deps.session_state.background_context
        == "Configured context from room."
    )
