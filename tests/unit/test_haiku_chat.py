import pathlib
from unittest import mock

import pytest
import yaml
from haiku.rag.agents import chat as hr_agents_chat
from haiku.rag.tools import context as hr_tools_context

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

W_FEATURES_AGENT_CONFIG_KW = W_RAG_STEM_CHAT_AGENT_CONFIG_KW | {
    "features": ["search", "qa"],
}
W_FEATURES_AGENT_CONFIG_YAML = f"""\
{W_RAG_STEM_CHAT_AGENT_CONFIG_YAML}
features:
    - search
    - qa
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
def mock_deps():
    deps = mock.MagicMock(spec=agents.AgentDependencies)
    deps.thread_id = "test-thread"
    deps.state = {}
    return deps


@pytest.fixture
def mock_agent():
    agent = mock.MagicMock()

    async def mock_events():
        yield "event1"
        yield "event2"

    agent.run_stream_events.return_value = mock_events()
    return agent


@pytest.fixture
def state_capturer():
    """Creates a ChatDeps stand-in that captures state assignments."""
    captured = []

    def make(real_cls):
        class _Capturer:
            def __init__(self, **kwargs):
                self._real = real_cls(**kwargs)

            def __getattr__(self, name):  # pragma: NO COVER
                return getattr(self._real, name)

            @property
            def state(self):  # pragma: NO COVER
                return self._real.state

            @state.setter
            def state(self, value):
                captured.append(value)
                self._real.state = value

        return _Capturer

    return make, captured


@pytest.mark.asyncio
@mock.patch("soliplex.haiku_chat.hr_agents_chat_agent")
@mock.patch("soliplex.haiku_chat.hr_client")
async def test_wrapper_run_stream_events_wo_state(
    hr_client,
    hr_agents_chat_agent,
    mock_deps,
    mock_agent,
):
    mock_config = mock.MagicMock()
    mock_client = mock.MagicMock()
    hr_client.HaikuRAG.return_value.__aenter__.return_value = mock_client
    hr_agents_chat_agent.create_chat_agent.return_value = mock_agent

    wrapper = haiku_chat.ChatAgentWrapper(
        config=mock_config,
        db_path=pathlib.Path(RAG_DB_PATH),
    )

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

    hr_agents_chat_agent.create_chat_agent.assert_called_once_with(
        mock_config,
        mock_client,
        mock.ANY,
        features=None,
    )

    call_kwargs = mock_agent.run_stream_events.call_args.kwargs
    assert call_kwargs["message_history"] == []

    hr_agents_chat_agent.ChatDeps.assert_called_once_with(
        config=mock_config,
        tool_context=mock.ANY,
        state_key=haiku_chat.AGUI_STATE_KEY,
    )


@pytest.mark.asyncio
@mock.patch("soliplex.haiku_chat.hr_agents_chat_agent")
@mock.patch("soliplex.haiku_chat.hr_client")
async def test_wrapper_run_stream_events_w_state(
    hr_client,
    hr_agents_chat_agent,
    mock_deps,
    mock_agent,
):
    mock_config = mock.MagicMock()
    mock_client = mock.MagicMock()
    hr_client.HaikuRAG.return_value.__aenter__.return_value = mock_client
    hr_agents_chat_agent.create_chat_agent.return_value = mock_agent

    wrapper = haiku_chat.ChatAgentWrapper(
        config=mock_config,
        db_path=pathlib.Path(RAG_DB_PATH),
    )

    mock_deps.state = {
        hr_agents_chat.AGUI_STATE_KEY: {
            "citations": [],
            "qa_history": [],
        },
    }

    events = []
    async for event in wrapper.run_stream_events(
        message_history=[],
        deps=mock_deps,
    ):
        events.append(event)

    hr_agents_chat_agent.ChatDeps.assert_called_once_with(
        config=mock_config,
        tool_context=mock.ANY,
        state_key=haiku_chat.AGUI_STATE_KEY,
    )


@pytest.mark.asyncio
@mock.patch("soliplex.haiku_chat.hr_agents_chat_agent")
@mock.patch("soliplex.haiku_chat.hr_client")
async def test_wrapper_passes_kwargs(
    hr_client,
    hr_agents_chat_agent,
    mock_deps,
    mock_agent,
):
    mock_config = mock.MagicMock()
    mock_client = mock.MagicMock()
    hr_client.HaikuRAG.return_value.__aenter__.return_value = mock_client
    hr_agents_chat_agent.create_chat_agent.return_value = mock_agent

    wrapper = haiku_chat.ChatAgentWrapper(
        config=mock_config,
        db_path=pathlib.Path(RAG_DB_PATH),
    )

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
@mock.patch("soliplex.haiku_chat.hr_agents_chat_agent")
@mock.patch("soliplex.haiku_chat.hr_client")
async def test_wrapper_passes_features(
    hr_client,
    hr_agents_chat_agent,
    mock_deps,
    mock_agent,
):
    mock_config = mock.MagicMock()
    mock_client = mock.MagicMock()
    hr_client.HaikuRAG.return_value.__aenter__.return_value = mock_client
    hr_agents_chat_agent.create_chat_agent.return_value = mock_agent

    wrapper = haiku_chat.ChatAgentWrapper(
        config=mock_config,
        db_path=pathlib.Path(RAG_DB_PATH),
        features=["search", "qa"],
    )

    events = []
    async for event in wrapper.run_stream_events(
        message_history=[],
        deps=mock_deps,
    ):
        events.append(event)

    hr_agents_chat_agent.create_chat_agent.assert_called_once_with(
        mock_config,
        mock_client,
        mock.ANY,
        features=["search", "qa"],
    )


@pytest.mark.asyncio
@mock.patch("soliplex.haiku_chat.hr_agents_chat_agent")
@mock.patch("soliplex.haiku_chat.hr_client")
async def test_wrapper_sets_background_context(
    hr_client,
    hr_agents_chat_agent,
    mock_deps,
    mock_agent,
    state_capturer,
):
    """background_context injects initial_context into state."""
    mock_config = mock.MagicMock()
    mock_client = mock.MagicMock()
    hr_client.HaikuRAG.return_value.__aenter__.return_value = mock_client
    hr_agents_chat_agent.create_chat_agent.return_value = mock_agent

    make_capturer, captured = state_capturer
    hr_agents_chat_agent.ChatDeps = make_capturer(
        hr_agents_chat_agent.ChatDeps,
    )

    wrapper = haiku_chat.ChatAgentWrapper(
        config=mock_config,
        db_path=pathlib.Path(RAG_DB_PATH),
        background_context="Configured context from room.",
    )

    events = []
    async for event in wrapper.run_stream_events(
        message_history=[],
        deps=mock_deps,
    ):
        events.append(event)

    chat_state = captured[0].get(haiku_chat.AGUI_STATE_KEY, {})
    assert chat_state.get("initial_context") == "Configured context from room."


@pytest.mark.asyncio
@mock.patch("soliplex.haiku_chat.hr_agents_chat_agent")
@mock.patch("soliplex.haiku_chat.hr_client")
async def test_wrapper_does_not_override_existing_initial_context(
    hr_client,
    hr_agents_chat_agent,
    mock_deps,
    mock_agent,
    state_capturer,
):
    """Existing initial_context is preserved over background_context."""
    mock_config = mock.MagicMock()
    mock_client = mock.MagicMock()
    hr_client.HaikuRAG.return_value.__aenter__.return_value = mock_client
    hr_agents_chat_agent.create_chat_agent.return_value = mock_agent

    make_capturer, captured = state_capturer
    hr_agents_chat_agent.ChatDeps = make_capturer(
        hr_agents_chat_agent.ChatDeps,
    )

    wrapper = haiku_chat.ChatAgentWrapper(
        config=mock_config,
        db_path=pathlib.Path(RAG_DB_PATH),
        background_context="Configured context from room.",
    )

    mock_deps.state = {
        hr_agents_chat.AGUI_STATE_KEY: {
            "initial_context": "Existing context.",
        },
    }

    events = []
    async for event in wrapper.run_stream_events(
        message_history=[],
        deps=mock_deps,
    ):
        events.append(event)

    # background_context used setdefault, so existing initial_context wins
    chat_state = captured[0].get(haiku_chat.AGUI_STATE_KEY, {})
    assert chat_state.get("initial_context") == "Existing context."


@pytest.mark.asyncio
@mock.patch("soliplex.haiku_chat.hr_agents_chat_agent")
@mock.patch("soliplex.haiku_chat.hr_client")
async def test_wrapper_uses_thread_id_for_context_cache(
    hr_client,
    hr_agents_chat_agent,
    mock_deps,
    mock_agent,
):
    """ToolContextCache is keyed by thread_id from deps."""
    mock_config = mock.MagicMock()
    mock_client = mock.MagicMock()
    hr_client.HaikuRAG.return_value.__aenter__.return_value = mock_client
    hr_agents_chat_agent.create_chat_agent.return_value = mock_agent

    mock_cache = mock.MagicMock(spec=hr_tools_context.ToolContextCache)
    mock_context = mock.MagicMock(spec=hr_tools_context.ToolContext)
    mock_cache.get_or_create.return_value = (mock_context, True)

    wrapper = haiku_chat.ChatAgentWrapper(
        config=mock_config,
        db_path=pathlib.Path(RAG_DB_PATH),
        _context_cache=mock_cache,
    )

    mock_deps.thread_id = "my-thread-123"

    events = []
    async for event in wrapper.run_stream_events(
        message_history=[],
        deps=mock_deps,
    ):
        events.append(event)

    mock_cache.get_or_create.assert_called_once_with("my-thread-123")


@pytest.mark.asyncio
@mock.patch("soliplex.haiku_chat.hr_agents_chat_agent")
@mock.patch("soliplex.haiku_chat.hr_client")
async def test_wrapper_defaults_thread_id_when_none(
    hr_client,
    hr_agents_chat_agent,
    mock_deps,
    mock_agent,
):
    """When thread_id is None, defaults to 'default'."""
    mock_config = mock.MagicMock()
    mock_client = mock.MagicMock()
    hr_client.HaikuRAG.return_value.__aenter__.return_value = mock_client
    hr_agents_chat_agent.create_chat_agent.return_value = mock_agent

    mock_cache = mock.MagicMock(spec=hr_tools_context.ToolContextCache)
    mock_context = mock.MagicMock(spec=hr_tools_context.ToolContext)
    mock_cache.get_or_create.return_value = (mock_context, True)

    wrapper = haiku_chat.ChatAgentWrapper(
        config=mock_config,
        db_path=pathlib.Path(RAG_DB_PATH),
        _context_cache=mock_cache,
    )

    mock_deps.thread_id = None

    events = []
    async for event in wrapper.run_stream_events(
        message_history=[],
        deps=mock_deps,
    ):
        events.append(event)

    mock_cache.get_or_create.assert_called_once_with("default")


@pytest.mark.asyncio
@mock.patch("soliplex.haiku_chat.hr_agents_chat_agent")
@mock.patch("soliplex.haiku_chat.hr_client")
async def test_wrapper_translates_document_filter(
    hr_client,
    hr_agents_chat_agent,
    mock_deps,
    mock_agent,
    state_capturer,
):
    """Document IDs from filter_documents are translated to names."""
    mock_config = mock.MagicMock()
    mock_client = mock.MagicMock()
    hr_client.HaikuRAG.return_value.__aenter__.return_value = mock_client
    hr_agents_chat_agent.create_chat_agent.return_value = mock_agent

    mock_doc = mock.MagicMock()
    mock_doc.title = "My Document"
    mock_client.get_document_by_id = mock.AsyncMock(return_value=mock_doc)

    make_capturer, captured = state_capturer
    hr_agents_chat_agent.ChatDeps = make_capturer(
        hr_agents_chat_agent.ChatDeps,
    )

    wrapper = haiku_chat.ChatAgentWrapper(
        config=mock_config,
        db_path=pathlib.Path(RAG_DB_PATH),
    )

    mock_deps.state = {
        "filter_documents": {"document_ids": ["doc-id-1"]},
    }

    events = []
    async for event in wrapper.run_stream_events(
        message_history=[],
        deps=mock_deps,
    ):
        events.append(event)

    mock_client.get_document_by_id.assert_called_once_with("doc-id-1")

    assert len(captured) == 1
    chat_state = captured[0].get(haiku_chat.AGUI_STATE_KEY, {})
    assert chat_state.get("document_filter") == ["My Document"]


@pytest.mark.asyncio
@mock.patch("soliplex.haiku_chat.hr_agents_chat_agent")
@mock.patch("soliplex.haiku_chat.hr_client")
async def test_wrapper_skips_filter_w_empty_doc_ids(
    hr_client,
    hr_agents_chat_agent,
    mock_deps,
    mock_agent,
):
    """Empty document_ids results in no document_filter."""
    mock_config = mock.MagicMock()
    mock_client = mock.MagicMock()
    hr_client.HaikuRAG.return_value.__aenter__.return_value = mock_client
    hr_agents_chat_agent.create_chat_agent.return_value = mock_agent

    mock_client.get_document_by_id = mock.AsyncMock()

    wrapper = haiku_chat.ChatAgentWrapper(
        config=mock_config,
        db_path=pathlib.Path(RAG_DB_PATH),
    )

    mock_deps.state = {
        "filter_documents": {"document_ids": []},
    }

    events = []
    async for event in wrapper.run_stream_events(
        message_history=[],
        deps=mock_deps,
    ):
        events.append(event)

    mock_client.get_document_by_id.assert_not_called()


@pytest.mark.asyncio
@mock.patch("soliplex.haiku_chat.hr_agents_chat_agent")
@mock.patch("soliplex.haiku_chat.hr_client")
async def test_wrapper_filter_skips_missing_documents(
    hr_client,
    hr_agents_chat_agent,
    mock_deps,
    mock_agent,
    state_capturer,
):
    """Documents that return None are skipped in the filter."""
    mock_config = mock.MagicMock()
    mock_client = mock.MagicMock()
    hr_client.HaikuRAG.return_value.__aenter__.return_value = mock_client
    hr_agents_chat_agent.create_chat_agent.return_value = mock_agent

    mock_client.get_document_by_id = mock.AsyncMock(return_value=None)

    make_capturer, captured = state_capturer
    hr_agents_chat_agent.ChatDeps = make_capturer(
        hr_agents_chat_agent.ChatDeps,
    )

    wrapper = haiku_chat.ChatAgentWrapper(
        config=mock_config,
        db_path=pathlib.Path(RAG_DB_PATH),
    )

    mock_deps.state = {
        "filter_documents": {"document_ids": ["bad-id"]},
    }

    events = []
    async for event in wrapper.run_stream_events(
        message_history=[],
        deps=mock_deps,
    ):
        events.append(event)

    # Missing doc should result in no document_filter
    assert len(captured) == 1
    chat_state = captured[0].get(haiku_chat.AGUI_STATE_KEY, {})
    assert "document_filter" not in chat_state


@pytest.mark.asyncio
@mock.patch("soliplex.haiku_chat.hr_agents_chat_agent")
@mock.patch("soliplex.haiku_chat.hr_client")
async def test_wrapper_triggers_background_summarization(
    hr_client,
    hr_agents_chat_agent,
    mock_deps,
    mock_agent,
):
    mock_config = mock.MagicMock()
    mock_client = mock.MagicMock()
    hr_client.HaikuRAG.return_value.__aenter__.return_value = mock_client
    hr_agents_chat_agent.create_chat_agent.return_value = mock_agent

    wrapper = haiku_chat.ChatAgentWrapper(
        config=mock_config,
        db_path=pathlib.Path(RAG_DB_PATH),
    )

    events = []
    async for event in wrapper.run_stream_events(
        message_history=[],
        deps=mock_deps,
    ):
        events.append(event)

    hr_agents_chat_agent.trigger_background_summarization.assert_called_once()


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
        (
            W_FEATURES_AGENT_CONFIG_YAML,
            W_FEATURES_AGENT_CONFIG_KW.copy(),
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
        W_FEATURES_AGENT_CONFIG_KW.copy(),
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
def test_chatagentconfig_factory(
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

    assert found.config is i_config.haiku_rag_config
    assert found.db_path == rag_path.resolve()
    assert found.background_context == cac.background_context
    assert found.features == cac.features


def test_chatagentconfig_factory_with_features(temp_dir):
    db_path = temp_dir / "db"
    db_path.mkdir()
    ic_enviro = {"RAG_LANCE_DB_PATH": str(db_path)}
    i_config = mock.create_autospec(config.InstallationConfig)
    i_config.get_environment = ic_enviro.get

    rag_path = db_path / f"{RAG_LANCEDB_STEM}.lancedb"
    rag_path.mkdir(parents=True)

    cac = haiku_chat.ChatAgentConfig(
        id=AGENT_ID,
        rag_lancedb_stem=RAG_LANCEDB_STEM,
        features=["search", "qa"],
        _installation_config=i_config,
        _config_path=temp_dir / "test.yaml",
    )

    found = cac.factory()

    assert isinstance(found, haiku_chat.ChatAgentWrapper)
    assert found.features == ["search", "qa"]
