from unittest import mock

import pydantic
import pytest
from ag_ui import core as agui_core
from sqlalchemy.ext import asyncio as sqla_asyncio

from soliplex import titles


def _awaitable(value):
    async def getter():
        return value

    return getter()


@pytest.fixture
def threads_engine():
    return mock.create_autospec(sqla_asyncio.AsyncEngine)


@pytest.fixture
def the_threads():
    return mock.AsyncMock()


@pytest.fixture
def mock_async_session(the_threads):
    """Patch AsyncSession to yield our mock ThreadStorage."""

    class FakeSession:
        async def __aenter__(self):
            return mock.MagicMock()

        async def __aexit__(self, *args):
            pass

    return mock.patch(
        "soliplex.titles.sqla_asyncio.AsyncSession",
        return_value=FakeSession(),
    )


@pytest.fixture
def mock_thread_storage(the_threads):
    return mock.patch(
        "soliplex.titles.agui_persistence.ThreadStorage",
        return_value=the_threads,
    )


class TestThreadTitle:
    def test_title_none_by_default(self):
        tt = titles.ThreadTitle()
        assert tt.title is None

    def test_title_with_value(self):
        tt = titles.ThreadTitle(title="My Title")
        assert tt.title == "My Title"

    def test_is_pydantic_model(self):
        assert issubclass(titles.ThreadTitle, pydantic.BaseModel)


class TestFormatMessages:
    def test_empty_messages(self):
        assert titles.format_messages([]) == ""

    def test_user_message_with_str_content(self):
        msg = agui_core.UserMessage(
            id="1",
            content="Hello there",
        )
        result = titles.format_messages([msg])
        assert result == "user: Hello there"

    def test_assistant_message(self):
        msg = agui_core.AssistantMessage(
            id="1",
            content="Hi! How can I help?",
        )
        result = titles.format_messages([msg])
        assert result == "assistant: Hi! How can I help?"

    def test_mixed_messages(self):
        msgs = [
            agui_core.UserMessage(id="1", content="Hello"),
            agui_core.AssistantMessage(id="2", content="Hi!"),
            agui_core.UserMessage(id="3", content="How are you?"),
        ]
        result = titles.format_messages(msgs)
        expected = "user: Hello\nassistant: Hi!\nuser: How are you?"
        assert result == expected

    def test_skips_non_user_assistant_messages(self):
        msgs = [
            agui_core.SystemMessage(id="0", content="System prompt"),
            agui_core.UserMessage(id="1", content="Hello"),
            agui_core.ToolMessage(
                id="2",
                content="tool result",
                tool_call_id="tc1",
            ),
            agui_core.AssistantMessage(id="3", content="Response"),
        ]
        result = titles.format_messages(msgs)
        assert result == "user: Hello\nassistant: Response"

    def test_skips_messages_with_none_content(self):
        msgs = [
            agui_core.AssistantMessage(id="1", content=None),
            agui_core.UserMessage(id="2", content="Hello"),
        ]
        result = titles.format_messages([msgs[0], msgs[1]])
        assert result == "user: Hello"

    def test_user_message_with_list_content(self):
        msg = agui_core.UserMessage(
            id="1",
            content=[
                agui_core.TextInputContent(text="Part one"),
                agui_core.BinaryInputContent(
                    mime_type="image/png",
                    data="abc",
                ),
                agui_core.TextInputContent(text="Part two"),
            ],
        )
        result = titles.format_messages([msg])
        assert result == "user: Part one\nPart two"


class TestGenerateTitle:
    @pytest.mark.anyio
    @mock.patch("pydantic_ai.Agent")
    @mock.patch("soliplex.agents.make_model")
    async def test_returns_title(self, make_model, agent_klass):
        agent_config = mock.MagicMock()
        messages = [
            agui_core.UserMessage(id="1", content="Hello"),
            agui_core.AssistantMessage(id="2", content="Hi!"),
        ]

        run_result = mock.MagicMock()
        run_result.output = titles.ThreadTitle(title="Greeting")
        agent_klass.return_value.run = mock.AsyncMock(
            return_value=run_result,
        )

        result = await titles.generate_title(agent_config, messages)

        assert result == "Greeting"
        make_model.assert_called_once_with(agent_config)
        agent_klass.assert_called_once_with(
            model=make_model.return_value,
            output_type=titles.ThreadTitle,
            instructions=titles.TITLE_PROMPT,
        )
        agent_klass.return_value.run.assert_awaited_once()

    @pytest.mark.anyio
    @mock.patch("pydantic_ai.Agent")
    @mock.patch("soliplex.agents.make_model")
    async def test_returns_none(self, make_model, agent_klass):
        agent_config = mock.MagicMock()
        messages = [
            agui_core.UserMessage(id="1", content="Hi"),
        ]

        run_result = mock.MagicMock()
        run_result.output = titles.ThreadTitle(title=None)
        agent_klass.return_value.run = mock.AsyncMock(
            return_value=run_result,
        )

        result = await titles.generate_title(agent_config, messages)

        assert result is None


class TestMaybeGenerateTitle:
    @pytest.mark.anyio
    @mock.patch("soliplex.titles.generate_title")
    async def test_generates_and_updates(
        self,
        gen_title,
        threads_engine,
        the_threads,
        mock_async_session,
        mock_thread_storage,
    ):
        gen_title.return_value = "My Chat Title"

        title_agent_config = mock.MagicMock()

        thread = mock.MagicMock()
        thread.awaitable_attrs.thread_metadata = _awaitable(None)
        the_threads.get_thread.return_value = thread

        messages = [
            agui_core.UserMessage(id="1", content="Hello"),
        ]

        with mock_async_session, mock_thread_storage:
            await titles.maybe_generate_title(
                title_agent_config=title_agent_config,
                threads_engine=threads_engine,
                room_id="room1",
                thread_id="thread1",
                user_name="user1",
                messages=messages,
            )

        the_threads.get_thread.assert_awaited_once_with(
            user_name="user1",
            room_id="room1",
            thread_id="thread1",
        )
        gen_title.assert_awaited_once_with(
            title_agent_config,
            messages,
        )
        the_threads.update_thread_metadata.assert_awaited_once_with(
            user_name="user1",
            room_id="room1",
            thread_id="thread1",
            thread_metadata={"name": "My Chat Title"},
        )

    @pytest.mark.anyio
    @mock.patch("soliplex.titles.generate_title")
    async def test_skips_when_title_already_set(
        self,
        gen_title,
        threads_engine,
        the_threads,
        mock_async_session,
        mock_thread_storage,
    ):
        metadata = mock.MagicMock()
        metadata.name = "Existing Title"
        thread = mock.MagicMock()
        thread.awaitable_attrs.thread_metadata = _awaitable(metadata)
        the_threads.get_thread.return_value = thread

        messages = [
            agui_core.UserMessage(id="1", content="Hello"),
        ]

        with mock_async_session, mock_thread_storage:
            await titles.maybe_generate_title(
                title_agent_config=mock.MagicMock(),
                threads_engine=threads_engine,
                room_id="room1",
                thread_id="thread1",
                user_name="user1",
                messages=messages,
            )

        gen_title.assert_not_awaited()
        the_threads.update_thread_metadata.assert_not_awaited()

    @pytest.mark.anyio
    @pytest.mark.parametrize("name", [None, titles.DEFAULT_THREAD_NAME])
    @mock.patch("soliplex.titles.generate_title")
    async def test_generates_when_no_title_set(
        self,
        gen_title,
        name,
        threads_engine,
        the_threads,
        mock_async_session,
        mock_thread_storage,
    ):
        gen_title.return_value = "New Title"

        metadata = mock.MagicMock()
        metadata.name = name
        thread = mock.MagicMock()
        thread.awaitable_attrs.thread_metadata = _awaitable(metadata)
        the_threads.get_thread.return_value = thread

        messages = [
            agui_core.UserMessage(id="1", content="Hello"),
        ]

        with mock_async_session, mock_thread_storage:
            await titles.maybe_generate_title(
                title_agent_config=mock.MagicMock(),
                threads_engine=threads_engine,
                room_id="room1",
                thread_id="thread1",
                user_name="user1",
                messages=messages,
            )

        gen_title.assert_awaited_once()
        the_threads.update_thread_metadata.assert_awaited_once()

    @pytest.mark.anyio
    @mock.patch("soliplex.titles.generate_title")
    async def test_skips_update_when_title_is_none(
        self,
        gen_title,
        threads_engine,
        the_threads,
        mock_async_session,
        mock_thread_storage,
    ):
        gen_title.return_value = None

        thread = mock.MagicMock()
        thread.awaitable_attrs.thread_metadata = _awaitable(None)
        the_threads.get_thread.return_value = thread

        messages = [
            agui_core.UserMessage(id="1", content="Hello"),
        ]

        with mock_async_session, mock_thread_storage:
            await titles.maybe_generate_title(
                title_agent_config=mock.MagicMock(),
                threads_engine=threads_engine,
                room_id="room1",
                thread_id="thread1",
                user_name="user1",
                messages=messages,
            )

        gen_title.assert_awaited_once()
        the_threads.update_thread_metadata.assert_not_awaited()

    @pytest.mark.anyio
    @mock.patch("logfire.exception")
    @mock.patch("soliplex.titles.generate_title")
    async def test_logs_exception_on_error(
        self,
        gen_title,
        logfire_exception,
        threads_engine,
        the_threads,
        mock_async_session,
        mock_thread_storage,
    ):
        gen_title.side_effect = RuntimeError("LLM error")

        thread = mock.MagicMock()
        thread.awaitable_attrs.thread_metadata = _awaitable(None)
        the_threads.get_thread.return_value = thread

        messages = [
            agui_core.UserMessage(id="1", content="Hello"),
        ]

        with mock_async_session, mock_thread_storage:
            await titles.maybe_generate_title(
                title_agent_config=mock.MagicMock(),
                threads_engine=threads_engine,
                room_id="room1",
                thread_id="thread1",
                user_name="user1",
                messages=messages,
            )

        logfire_exception.assert_called_once()
