from unittest import mock

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


class TestFormatMessage:
    def test_user_message(self):
        msg = agui_core.UserMessage(id="1", content="Hello")
        assert titles.format_message(msg) == "user: Hello"

    def test_assistant_message(self):
        msg = agui_core.AssistantMessage(id="1", content="Hi!")
        assert titles.format_message(msg) == "assistant: Hi!"

    def test_system_message_returns_none(self):
        msg = agui_core.SystemMessage(id="1", content="System prompt")
        assert titles.format_message(msg) is None

    def test_none_content_returns_none(self):
        msg = agui_core.AssistantMessage(id="1", content=None)
        assert titles.format_message(msg) is None

    def test_list_content(self):
        msg = agui_core.UserMessage(
            id="1",
            content=[
                agui_core.TextInputContent(text="Part one"),
                agui_core.ImageInputContent(
                    source=agui_core.InputContentDataSource(
                        mime_type="image/png",
                        value="abc",
                    ),
                ),
                agui_core.TextInputContent(text="Part two"),
            ],
        )
        assert titles.format_message(msg) == "user: Part one\nPart two"

    def test_list_content_no_text_returns_none(self):
        msg = agui_core.UserMessage(
            id="1",
            content=[
                agui_core.ImageInputContent(
                    source=agui_core.InputContentDataSource(
                        mime_type="image/png",
                        value="abc",
                    ),
                ),
            ],
        )
        assert titles.format_message(msg) is None


class TestFormatMessages:
    def test_empty_messages(self):
        assert titles.format_messages([]) == ""

    def test_joins_and_filters(self):
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


class TestExtractAssistantText:
    def test_empty_event_list(self):
        assert titles.extract_assistant_text([]) == ""

    def test_extracts_text_content_deltas(self):
        events = [
            agui_core.events.TextMessageStartEvent(
                message_id="m1",
            ),
            agui_core.events.TextMessageContentEvent(
                message_id="m1",
                delta="Hello ",
            ),
            agui_core.events.TextMessageContentEvent(
                message_id="m1",
                delta="world",
            ),
            agui_core.events.RunFinishedEvent(
                thread_id="t1",
                run_id="r1",
            ),
        ]
        assert titles.extract_assistant_text(events) == "Hello world"


class TestGenerateTitle:
    @pytest.mark.anyio
    @pytest.mark.parametrize("assistant_text", ["", "Hi there!"])
    @mock.patch("pydantic_ai.Agent")
    @mock.patch("soliplex.config.agents.get_model_from_config")
    async def test_generate_title(
        self, get_model_from_config, agent_klass, assistant_text
    ):
        agent_config = mock.MagicMock()
        messages = [
            agui_core.UserMessage(id="1", content="Hello"),
        ]

        run_result = mock.MagicMock()
        run_result.output = titles.ThreadTitle(title="Greeting")
        agent_klass.return_value.run = mock.AsyncMock(
            return_value=run_result,
        )

        result = await titles.generate_title(
            agent_config, messages, assistant_text=assistant_text
        )

        assert result == "Greeting"

        expected_text = "user: Hello"
        if assistant_text:
            expected_text += f"\nassistant: {assistant_text}"
        agent_klass.return_value.run.assert_awaited_once_with(
            expected_text,
        )

    @pytest.mark.anyio
    @mock.patch("pydantic_ai.Agent")
    @mock.patch("soliplex.config.agents.get_model_from_config")
    async def test_returns_none(self, get_model_from_config, agent_klass):
        run_result = mock.MagicMock()
        run_result.output = titles.ThreadTitle(title=None)
        agent_klass.return_value.run = mock.AsyncMock(
            return_value=run_result,
        )

        result = await titles.generate_title(
            mock.MagicMock(),
            [agui_core.UserMessage(id="1", content="Hi")],
        )

        assert result is None


class TestMaybeGenerateTitle:
    @pytest.mark.anyio
    @mock.patch("soliplex.titles.extract_assistant_text")
    @mock.patch("soliplex.titles.generate_title")
    async def test_generates_and_updates(
        self,
        gen_title,
        extract_at,
        threads_engine,
        the_threads,
        mock_async_session,
        mock_thread_storage,
    ):
        gen_title.return_value = "My Chat Title"
        extract_at.return_value = "assistant response"

        title_agent_config = mock.MagicMock()

        thread = mock.MagicMock()
        thread.awaitable_attrs.thread_metadata = _awaitable(None)
        the_threads.get_thread.return_value = thread

        messages = [
            agui_core.UserMessage(id="1", content="Hello"),
        ]
        event_list = [mock.MagicMock()]

        with mock_async_session, mock_thread_storage:
            await titles.maybe_generate_title(
                title_agent_config=title_agent_config,
                threads_engine=threads_engine,
                room_id="room1",
                thread_id="thread1",
                user_name="user1",
                messages=messages,
                event_list=event_list,
            )

        extract_at.assert_called_once_with(event_list)
        gen_title.assert_awaited_once_with(
            title_agent_config,
            messages,
            "assistant response",
        )
        the_threads.update_thread_metadata.assert_awaited_once_with(
            user_name="user1",
            room_id="room1",
            thread_id="thread1",
            thread_metadata={"name": "My Chat Title"},
        )

    @pytest.mark.anyio
    @pytest.mark.parametrize(
        "name",
        ["Existing Title", None, titles.DEFAULT_THREAD_NAME],
    )
    @mock.patch("soliplex.titles.generate_title")
    async def test_skips_or_generates_based_on_existing_title(
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

        with mock_async_session, mock_thread_storage:
            await titles.maybe_generate_title(
                title_agent_config=mock.MagicMock(),
                threads_engine=threads_engine,
                room_id="room1",
                thread_id="thread1",
                user_name="user1",
                messages=[
                    agui_core.UserMessage(id="1", content="Hello"),
                ],
            )

        should_skip = name not in (None, titles.DEFAULT_THREAD_NAME)
        if should_skip:
            gen_title.assert_not_awaited()
        else:
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

        with mock_async_session, mock_thread_storage:
            await titles.maybe_generate_title(
                title_agent_config=mock.MagicMock(),
                threads_engine=threads_engine,
                room_id="room1",
                thread_id="thread1",
                user_name="user1",
                messages=[
                    agui_core.UserMessage(id="1", content="Hello"),
                ],
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

        with mock_async_session, mock_thread_storage:
            await titles.maybe_generate_title(
                title_agent_config=mock.MagicMock(),
                threads_engine=threads_engine,
                room_id="room1",
                thread_id="thread1",
                user_name="user1",
                messages=[
                    agui_core.UserMessage(id="1", content="Hello"),
                ],
            )

        logfire_exception.assert_called_once()
