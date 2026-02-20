import pathlib
from unittest import mock

import pytest
import yaml
from haiku.rag.agents import chat as hr_agents_chat
from haiku.rag.tools import toolkit as hr_toolkit

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
    "rag_features": ["search", "documents"],
}
W_FEATURES_AGENT_CONFIG_YAML = f"""\
{W_RAG_STEM_CHAT_AGENT_CONFIG_YAML}
rag_features:
    - "search"
    - "documents"
"""

W_PREAMBLE_AGENT_CONFIG_KW = W_RAG_STEM_CHAT_AGENT_CONFIG_KW | {
    "preamble": "You are a helpful assistant.",
}
W_PREAMBLE_AGENT_CONFIG_YAML = f"""\
{W_RAG_STEM_CHAT_AGENT_CONFIG_YAML}
preamble: |
    You are a helpful assistant.
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


@pytest.mark.asyncio
@mock.patch("soliplex.haiku_chat.hr_agents_chat_agent")
@mock.patch("soliplex.haiku_chat.hr_client")
async def test_chat_agent_wrapper_run_stream_events_wo_state(
    hr_client,
    hr_agents_chat_agent_mod,
):
    mock_agent = mock.MagicMock()
    mock_config = mock.MagicMock()
    mock_client = mock.MagicMock()
    mock_toolkit = mock.MagicMock(spec=hr_toolkit.Toolkit)
    mock_context = mock.MagicMock()
    mock_toolkit.create_context.return_value = mock_context

    hr_client.HaikuRAG.return_value.__aenter__.return_value = mock_client

    mock_chat_deps = mock.MagicMock()
    hr_agents_chat_agent_mod.ChatDeps.return_value = mock_chat_deps

    async def mock_events():
        yield "event1"
        yield "event2"

    mock_agent.run_stream_events.return_value = mock_events()

    wrapper = haiku_chat.ChatAgentWrapper(
        agent=mock_agent,
        toolkit=mock_toolkit,
        config=mock_config,
        db_path=pathlib.Path(RAG_DB_PATH),
    )

    mock_deps = mock.MagicMock(spec=agents.AgentDependencies)
    mock_deps.thread_id = None
    mock_deps.state = {}

    events = []
    async for event in wrapper.run_stream_events(
        message_history=[],
        deps=mock_deps,
    ):
        events.append(event)

    assert events == ["event1", "event2"]

    mock_toolkit.create_context.assert_called_once_with(
        state_key=hr_agents_chat.AGUI_STATE_KEY,
    )

    hr_client.HaikuRAG.assert_called_once_with(
        db_path=pathlib.Path(RAG_DB_PATH),
        config=mock_config,
        read_only=True,
    )

    hr_agents_chat_agent_mod.ChatDeps.assert_called_once_with(
        config=mock_config,
        client=mock_client,
        tool_context=mock_context,
    )

    assert mock_chat_deps.state == {}


@pytest.mark.asyncio
@mock.patch("soliplex.haiku_chat.hr_agents_chat_agent")
@mock.patch("soliplex.haiku_chat.hr_client")
async def test_chat_agent_wrapper_run_stream_events_w_state(
    hr_client,
    hr_agents_chat_agent_mod,
):
    mock_agent = mock.MagicMock()
    mock_config = mock.MagicMock()
    mock_client = mock.MagicMock()
    mock_toolkit = mock.MagicMock(spec=hr_toolkit.Toolkit)
    mock_toolkit.create_context.return_value = mock.MagicMock()

    hr_client.HaikuRAG.return_value.__aenter__.return_value = mock_client

    mock_chat_deps = mock.MagicMock()
    hr_agents_chat_agent_mod.ChatDeps.return_value = mock_chat_deps

    agui_state = {
        hr_agents_chat.AGUI_STATE_KEY: {
            "session_id": "test-session",
            "citations": [],
            "qa_history": [],
        },
    }

    async def mock_events():
        yield "event1"

    mock_agent.run_stream_events.return_value = mock_events()

    wrapper = haiku_chat.ChatAgentWrapper(
        agent=mock_agent,
        toolkit=mock_toolkit,
        config=mock_config,
        db_path=pathlib.Path(RAG_DB_PATH),
    )

    mock_deps = mock.MagicMock(spec=agents.AgentDependencies)
    mock_deps.thread_id = None
    mock_deps.state = agui_state

    events = []
    async for event in wrapper.run_stream_events(
        message_history=[],
        deps=mock_deps,
    ):
        events.append(event)

    assert mock_chat_deps.state == agui_state


@pytest.mark.asyncio
@mock.patch("soliplex.haiku_chat.hr_agents_chat_agent")
@mock.patch("soliplex.haiku_chat.hr_client")
async def test_chat_agent_wrapper_passes_kwargs(
    hr_client,
    hr_agents_chat_agent_mod,
):
    mock_agent = mock.MagicMock()
    mock_config = mock.MagicMock()
    mock_client = mock.MagicMock()
    mock_toolkit = mock.MagicMock(spec=hr_toolkit.Toolkit)
    mock_toolkit.create_context.return_value = mock.MagicMock()

    hr_client.HaikuRAG.return_value.__aenter__.return_value = mock_client

    mock_chat_deps = mock.MagicMock()
    hr_agents_chat_agent_mod.ChatDeps.return_value = mock_chat_deps

    async def mock_events():
        yield "event"

    mock_agent.run_stream_events.return_value = mock_events()

    wrapper = haiku_chat.ChatAgentWrapper(
        agent=mock_agent,
        toolkit=mock_toolkit,
        config=mock_config,
        db_path=pathlib.Path(RAG_DB_PATH),
    )

    mock_deps = mock.MagicMock(spec=agents.AgentDependencies)
    mock_deps.thread_id = None
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
    assert call_kwargs["deps"] is mock_chat_deps


@pytest.mark.asyncio
@mock.patch("soliplex.haiku_chat.hr_agents_chat_agent")
@mock.patch("soliplex.haiku_chat.hr_client")
async def test_chat_agent_wrapper_caches_context_by_thread_id(
    hr_client,
    hr_agents_chat_agent_mod,
):
    mock_agent = mock.MagicMock()
    mock_config = mock.MagicMock()
    mock_client = mock.MagicMock()
    mock_toolkit = mock.MagicMock(spec=hr_toolkit.Toolkit)
    mock_toolkit.prepare = mock.MagicMock()

    hr_client.HaikuRAG.return_value.__aenter__.return_value = mock_client

    mock_chat_deps = mock.MagicMock()
    hr_agents_chat_agent_mod.ChatDeps.return_value = mock_chat_deps

    async def mock_events():
        yield "event"

    wrapper = haiku_chat.ChatAgentWrapper(
        agent=mock_agent,
        toolkit=mock_toolkit,
        config=mock_config,
        db_path=pathlib.Path(RAG_DB_PATH),
    )

    thread_id = "test-thread-123"

    # First request: creates and caches a new context
    mock_agent.run_stream_events.return_value = mock_events()
    mock_deps = mock.MagicMock(spec=agents.AgentDependencies)
    mock_deps.thread_id = thread_id
    mock_deps.state = {}

    async for _event in wrapper.run_stream_events(
        message_history=[],
        deps=mock_deps,
    ):
        pass

    mock_toolkit.create_context.assert_not_called()
    mock_toolkit.prepare.assert_called_once_with(
        mock.ANY, state_key=hr_agents_chat.AGUI_STATE_KEY
    )

    first_context = hr_agents_chat_agent_mod.ChatDeps.call_args.kwargs[
        "tool_context"
    ]

    # Second request: reuses the cached context
    mock_agent.run_stream_events.return_value = mock_events()
    mock_toolkit.prepare.reset_mock()

    async for _event in wrapper.run_stream_events(
        message_history=[],
        deps=mock_deps,
    ):
        pass

    # prepare() should NOT be called again (not a new context)
    mock_toolkit.prepare.assert_not_called()

    second_context = hr_agents_chat_agent_mod.ChatDeps.call_args.kwargs[
        "tool_context"
    ]
    assert first_context is second_context


@pytest.mark.asyncio
@mock.patch("soliplex.haiku_chat.hr_agents_chat_agent")
@mock.patch("soliplex.haiku_chat.hr_client")
async def test_chat_agent_wrapper_no_thread_id_creates_fresh_context(
    hr_client,
    hr_agents_chat_agent_mod,
):
    mock_agent = mock.MagicMock()
    mock_config = mock.MagicMock()
    mock_client = mock.MagicMock()
    mock_toolkit = mock.MagicMock(spec=hr_toolkit.Toolkit)
    mock_context_1 = mock.MagicMock()
    mock_context_2 = mock.MagicMock()
    mock_toolkit.create_context.side_effect = [mock_context_1, mock_context_2]

    hr_client.HaikuRAG.return_value.__aenter__.return_value = mock_client

    mock_chat_deps = mock.MagicMock()
    hr_agents_chat_agent_mod.ChatDeps.return_value = mock_chat_deps

    async def mock_events():
        yield "event"

    wrapper = haiku_chat.ChatAgentWrapper(
        agent=mock_agent,
        toolkit=mock_toolkit,
        config=mock_config,
        db_path=pathlib.Path(RAG_DB_PATH),
    )

    mock_deps = mock.MagicMock(spec=agents.AgentDependencies)
    mock_deps.thread_id = None
    mock_deps.state = {}

    # First request
    mock_agent.run_stream_events.return_value = mock_events()
    async for _event in wrapper.run_stream_events(
        message_history=[], deps=mock_deps
    ):
        pass

    first_context = hr_agents_chat_agent_mod.ChatDeps.call_args.kwargs[
        "tool_context"
    ]
    assert first_context is mock_context_1

    # Second request: creates a DIFFERENT context (no caching)
    mock_agent.run_stream_events.return_value = mock_events()
    async for _event in wrapper.run_stream_events(
        message_history=[], deps=mock_deps
    ):
        pass

    second_context = hr_agents_chat_agent_mod.ChatDeps.call_args.kwargs[
        "tool_context"
    ]
    assert second_context is mock_context_2
    assert first_context is not second_context


@pytest.mark.asyncio
@mock.patch("soliplex.haiku_chat.hr_agents_chat_agent")
@mock.patch("soliplex.haiku_chat.hr_client")
async def test_chat_agent_wrapper_sets_initial_context_from_background(
    hr_client,
    hr_agents_chat_agent_mod,
):
    mock_agent = mock.MagicMock()
    mock_config = mock.MagicMock()
    mock_client = mock.MagicMock()
    mock_toolkit = mock.MagicMock(spec=hr_toolkit.Toolkit)
    mock_toolkit.create_context.return_value = mock.MagicMock()

    hr_client.HaikuRAG.return_value.__aenter__.return_value = mock_client

    mock_chat_deps = mock.MagicMock()
    hr_agents_chat_agent_mod.ChatDeps.return_value = mock_chat_deps

    async def mock_events():
        yield "event"

    mock_agent.run_stream_events.return_value = mock_events()

    wrapper = haiku_chat.ChatAgentWrapper(
        agent=mock_agent,
        toolkit=mock_toolkit,
        config=mock_config,
        db_path=pathlib.Path(RAG_DB_PATH),
        background_context="Configured context from room.",
    )

    mock_deps = mock.MagicMock(spec=agents.AgentDependencies)
    mock_deps.thread_id = None
    mock_deps.state = {}

    events = []
    async for event in wrapper.run_stream_events(
        message_history=[],
        deps=mock_deps,
    ):
        events.append(event)

    expected_state = {
        hr_agents_chat.AGUI_STATE_KEY: {
            "initial_context": "Configured context from room.",
        },
    }
    assert mock_chat_deps.state == expected_state


@pytest.mark.asyncio
@mock.patch("soliplex.haiku_chat.hr_agents_chat_agent")
@mock.patch("soliplex.haiku_chat.hr_client")
async def test_chat_agent_wrapper_does_not_override_existing_initial_context(
    hr_client,
    hr_agents_chat_agent_mod,
):
    mock_agent = mock.MagicMock()
    mock_config = mock.MagicMock()
    mock_client = mock.MagicMock()
    mock_toolkit = mock.MagicMock(spec=hr_toolkit.Toolkit)
    mock_toolkit.create_context.return_value = mock.MagicMock()

    hr_client.HaikuRAG.return_value.__aenter__.return_value = mock_client

    mock_chat_deps = mock.MagicMock()
    hr_agents_chat_agent_mod.ChatDeps.return_value = mock_chat_deps

    async def mock_events():
        yield "event"

    mock_agent.run_stream_events.return_value = mock_events()

    wrapper = haiku_chat.ChatAgentWrapper(
        agent=mock_agent,
        toolkit=mock_toolkit,
        config=mock_config,
        db_path=pathlib.Path(RAG_DB_PATH),
        background_context="Configured context from room.",
    )

    mock_deps = mock.MagicMock(spec=agents.AgentDependencies)
    mock_deps.thread_id = None
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

    expected_state = {
        hr_agents_chat.AGUI_STATE_KEY: {
            "initial_context": "Existing context.",
        },
    }
    assert mock_chat_deps.state == expected_state


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
        (
            W_PREAMBLE_AGENT_CONFIG_YAML,
            W_PREAMBLE_AGENT_CONFIG_KW.copy(),
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
        W_PREAMBLE_AGENT_CONFIG_KW.copy(),
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
        W_FEATURES_AGENT_CONFIG_KW.copy(),
    ],
)
@mock.patch("soliplex.haiku_chat.hr_agents_chat_agent")
def test_chatagentconfig_factory(
    hr_agents_chat_agent_mod,
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

    mock_toolkit = mock.MagicMock(spec=hr_toolkit.Toolkit)
    hr_agents_chat_agent_mod.build_chat_toolkit.return_value = mock_toolkit

    mock_agent = mock.MagicMock()
    hr_agents_chat_agent_mod.create_chat_agent.return_value = mock_agent

    cac = haiku_chat.ChatAgentConfig(
        **ctor_kw,
        _installation_config=i_config,
        _config_path=temp_dir / "test.yaml",
    )

    found = cac.factory()

    assert isinstance(found, haiku_chat.ChatAgentWrapper)
    assert found.agent is mock_agent
    assert found.toolkit is mock_toolkit
    assert found.config is i_config.haiku_rag_config
    assert found.db_path == rag_path.resolve()
    assert found.background_context == cac.background_context

    hr_agents_chat_agent_mod.build_chat_toolkit.assert_called_once_with(
        i_config.haiku_rag_config,
        features=cac.rag_features,
    )
    hr_agents_chat_agent_mod.create_chat_agent.assert_called_once_with(
        i_config.haiku_rag_config,
        features=cac.rag_features,
        preamble=cac.preamble,
        toolkit=mock_toolkit,
    )


def test_chatagentconfig_haiku_rag_config_wo_config_path():
    cac = haiku_chat.ChatAgentConfig(
        id=AGENT_ID,
        rag_lancedb_stem=RAG_LANCEDB_STEM,
    )

    with pytest.raises(config.NoConfigPath):
        _ = cac.haiku_rag_config


def test_chatagentconfig_haiku_rag_config_w_override_yaml(temp_dir):
    i_config = mock.create_autospec(config.InstallationConfig)
    from haiku.rag.config import models as hr_config_models

    i_config.haiku_rag_config = hr_config_models.AppConfig()

    override_yaml = temp_dir / "haiku.rag.yaml"
    override_yaml.write_text("search:\n  limit: 42\n")

    config_path = temp_dir / "room_config.yaml"

    cac = haiku_chat.ChatAgentConfig(
        id=AGENT_ID,
        rag_lancedb_stem=RAG_LANCEDB_STEM,
        _installation_config=i_config,
        _config_path=config_path,
    )

    found = cac.haiku_rag_config
    assert found.search.limit == 42


def test_chatagentconfig_rag_lancedb_path_w_missing_stem_dir(temp_dir):
    i_config = mock.create_autospec(config.InstallationConfig)
    i_config.get_environment.return_value = str(temp_dir)

    cac = haiku_chat.ChatAgentConfig(
        id=AGENT_ID,
        rag_lancedb_stem="does_not_exist",
        _installation_config=i_config,
        _config_path=temp_dir / "test.yaml",
    )

    with pytest.raises(config.RagDbFileNotFound):
        _ = cac.rag_lancedb_path


def test_chatagentconfig_get_extra_parameters_w_missing_db(temp_dir):
    i_config = mock.create_autospec(config.InstallationConfig)
    i_config.get_environment.return_value = str(temp_dir)

    cac = haiku_chat.ChatAgentConfig(
        id=AGENT_ID,
        rag_lancedb_stem="does_not_exist",
        _installation_config=i_config,
        _config_path=temp_dir / "test.yaml",
    )

    result = cac.get_extra_parameters()
    assert "MISSING:" in result["rag_lancedb_path"]
