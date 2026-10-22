from unittest import mock

import pydantic
import pytest
from ag_ui import core as agui_core
from sqlalchemy.ext import asyncio as sqla_asyncio

from soliplex import auto_labels


def _awaitable(value):
    async def getter():
        return value

    return getter()


def _label(id_, name):
    label = mock.MagicMock()
    label.id_ = id_
    label.name = name
    return label


def _thread(*, runs=1, labels=()):
    thread = mock.MagicMock()
    thread.awaitable_attrs.runs = _awaitable([object()] * runs)
    thread.awaitable_attrs.labels = _awaitable(list(labels))
    return thread


CATALOGUE = [_label(1, "Manuals"), _label(2, "Billing"), _label(3, "Ops")]


@pytest.fixture
def threads_engine():
    return mock.create_autospec(sqla_asyncio.AsyncEngine)


@pytest.fixture
def the_threads():
    return mock.AsyncMock()


@pytest.fixture
def mock_async_session():
    class FakeSession:
        async def __aenter__(self):
            return mock.MagicMock()

        async def __aexit__(self, *args):
            pass

    return mock.patch(
        "soliplex.auto_labels.sqla_asyncio.AsyncSession",
        side_effect=lambda **_: FakeSession(),
    )


@pytest.fixture
def mock_thread_storage(the_threads):
    return mock.patch(
        "soliplex.auto_labels.agui_persistence.ThreadStorage",
        return_value=the_threads,
    )


class TestLabelsOutputType:
    def test_admits_catalogue_names(self):
        output_type = auto_labels.labels_output_type(["Manuals", "Ops"])

        found = output_type(label_names=["Ops", "Manuals"])

        assert found.label_names == ["Ops", "Manuals"]

    def test_defaults_to_none_chosen(self):
        output_type = auto_labels.labels_output_type(["Manuals"])

        assert output_type().label_names == []

    def test_rejects_a_name_outside_the_catalogue(self):
        output_type = auto_labels.labels_output_type(["Manuals"])

        with pytest.raises(pydantic.ValidationError):
            output_type(label_names=["Invented"])

    def test_rejects_more_than_the_maximum(self):
        names = [f"L{i}" for i in range(auto_labels.MAX_AUTO_LABELS + 1)]
        output_type = auto_labels.labels_output_type(names)

        with pytest.raises(pydantic.ValidationError):
            output_type(label_names=names)


def test_label_instructions_name_every_label():
    found = auto_labels.label_instructions(["Manuals", "Ops"])

    assert found.startswith(auto_labels.LABEL_PROMPT)
    assert found.endswith("Allowed labels:\n- Manuals\n- Ops")


class TestGenerateLabels:
    @pytest.mark.anyio
    @pytest.mark.parametrize("assistant_text", ["", "Hi there!"])
    @mock.patch("pydantic_ai.Agent")
    @mock.patch("soliplex.config.agents.get_model_from_config")
    async def test_maps_chosen_names_to_ids(
        self, get_model_from_config, agent_klass, assistant_text
    ):
        agent_config = mock.MagicMock()
        messages = [agui_core.UserMessage(id="1", content="Hello")]

        run_result = mock.MagicMock()
        run_result.output.label_names = ["Ops", "Manuals", "Ops"]
        agent_klass.return_value.run = mock.AsyncMock(
            return_value=run_result,
        )

        found = await auto_labels.generate_labels(
            agent_config, CATALOGUE, messages, assistant_text=assistant_text
        )

        assert found == [3, 1]

        get_model_from_config.assert_called_once_with(
            agent_config=agent_config,
        )
        agent_kwargs = agent_klass.call_args.kwargs
        assert agent_kwargs["model"] is get_model_from_config.return_value
        assert agent_kwargs["instructions"] == (
            auto_labels.label_instructions(["Manuals", "Billing", "Ops"])
        )
        output_type = agent_kwargs["output_type"]
        with pytest.raises(pydantic.ValidationError):
            output_type(label_names=["Invented"])

        expected_text = "user: Hello"
        if assistant_text:
            expected_text += f"\nassistant: {assistant_text}"
        agent_klass.return_value.run.assert_awaited_once_with(expected_text)


@pytest.mark.anyio
async def test_candidate_labels_is_the_catalogue(the_threads):
    the_threads.list_labels.return_value = CATALOGUE

    assert await auto_labels.candidate_labels(the_threads) is CATALOGUE


class TestMaybeApplyLabels:
    async def _apply(self, threads_engine, event_list=()):
        await auto_labels.maybe_apply_labels(
            label_agent_config=self.label_agent_config,
            threads_engine=threads_engine,
            room_id="room1",
            thread_id="thread1",
            user_name="user1",
            messages=self.messages,
            event_list=event_list,
        )

    def setup_method(self):
        self.label_agent_config = mock.MagicMock()
        self.messages = [agui_core.UserMessage(id="1", content="Hello")]

    @pytest.mark.anyio
    @mock.patch("soliplex.auto_labels.titles.extract_assistant_text")
    @mock.patch("soliplex.auto_labels.generate_labels")
    async def test_applies_chosen_labels(
        self,
        gen_labels,
        extract_at,
        threads_engine,
        the_threads,
        mock_async_session,
        mock_thread_storage,
    ):
        gen_labels.return_value = [3, 1]
        extract_at.return_value = "assistant response"
        the_threads.list_labels.return_value = CATALOGUE
        # Unlabelled when checked; by the time the agent has chosen, the
        # owner has attached one of the same labels and one other.
        the_threads.get_thread.side_effect = [
            _thread(),
            _thread(labels=[_label(1, "Manuals"), _label(9, "Mine")]),
        ]
        event_list = [mock.MagicMock()]

        with mock_async_session, mock_thread_storage:
            await self._apply(threads_engine, event_list)

        extract_at.assert_called_once_with(event_list)
        gen_labels.assert_awaited_once_with(
            self.label_agent_config,
            CATALOGUE,
            self.messages,
            "assistant response",
        )
        the_threads.set_thread_labels.assert_awaited_once_with(
            user_name="user1",
            room_id="room1",
            thread_id="thread1",
            label_ids=[1, 9, 3, 1],
        )

    @pytest.mark.anyio
    @pytest.mark.parametrize(
        "thread_kw",
        [{"runs": 2}, {"labels": [_label(1, "Manuals")]}],
        ids=["not_first_run", "already_labelled"],
    )
    @mock.patch("soliplex.auto_labels.generate_labels")
    async def test_skips_without_asking(
        self,
        gen_labels,
        thread_kw,
        threads_engine,
        the_threads,
        mock_async_session,
        mock_thread_storage,
    ):
        the_threads.get_thread.return_value = _thread(**thread_kw)

        with mock_async_session, mock_thread_storage:
            await self._apply(threads_engine)

        the_threads.list_labels.assert_not_awaited()
        gen_labels.assert_not_awaited()
        the_threads.set_thread_labels.assert_not_awaited()

    @pytest.mark.anyio
    @mock.patch("soliplex.auto_labels.generate_labels")
    async def test_skips_with_empty_catalogue(
        self,
        gen_labels,
        threads_engine,
        the_threads,
        mock_async_session,
        mock_thread_storage,
    ):
        the_threads.get_thread.return_value = _thread()
        the_threads.list_labels.return_value = []

        with mock_async_session, mock_thread_storage:
            await self._apply(threads_engine)

        gen_labels.assert_not_awaited()
        the_threads.set_thread_labels.assert_not_awaited()

    @pytest.mark.anyio
    @mock.patch("soliplex.auto_labels.generate_labels")
    async def test_writes_nothing_when_none_chosen(
        self,
        gen_labels,
        threads_engine,
        the_threads,
        mock_async_session,
        mock_thread_storage,
    ):
        gen_labels.return_value = []
        the_threads.get_thread.return_value = _thread()
        the_threads.list_labels.return_value = CATALOGUE

        with mock_async_session, mock_thread_storage:
            await self._apply(threads_engine)

        gen_labels.assert_awaited_once()
        the_threads.set_thread_labels.assert_not_awaited()

    @pytest.mark.anyio
    @mock.patch("soliplex.auto_labels.logfire")
    async def test_logs_and_swallows_failure(
        self,
        logfire,
        threads_engine,
        the_threads,
        mock_async_session,
        mock_thread_storage,
    ):
        the_threads.get_thread.side_effect = Exception("db down")

        with mock_async_session, mock_thread_storage:
            await self._apply(threads_engine)

        logfire.exception.assert_called_once_with(
            "Failed to apply thread labels"
        )
