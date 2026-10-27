from unittest import mock

import pydantic
import pydantic_ai
import pytest
import pytest_asyncio
from ag_ui import core as agui_core
from pydantic_ai import messages as ai_messages
from pydantic_ai.models import function as ai_function
from sqlalchemy.ext import asyncio as sqla_asyncio

from soliplex import auto_labels
from soliplex.agui import persistence as agui_persistence
from soliplex.agui import schema as agui_schema
from soliplex.config import installation as config_installation


def _label(id_, name):
    label = mock.MagicMock()
    label.id_ = id_
    label.name = name
    return label


CATALOGUE = [_label(1, "Manuals"), _label(2, "Billing"), _label(3, "Ops")]


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


def _answering(*answers):
    """A model which picks each of 'answers' in turn, and records calls."""
    calls = []

    def respond(messages, info: ai_function.AgentInfo):
        calls.append((messages, info))
        return ai_messages.ModelResponse(
            parts=[
                ai_messages.ToolCallPart(
                    tool_name=info.output_tools[0].name,
                    args={"label_names": answers[len(calls) - 1]},
                )
            ]
        )

    return ai_function.FunctionModel(respond), calls


class TestGenerateLabels:
    @pytest.mark.anyio
    @pytest.mark.parametrize("assistant_text", ["", "Hi there!"])
    @mock.patch("soliplex.config.agents.get_model_from_config")
    async def test_maps_chosen_names_to_ids(
        self, get_model_from_config, assistant_text
    ):
        model, calls = _answering(["Ops", "Manuals", "Ops"])
        get_model_from_config.return_value = model
        agent_config = mock.MagicMock()
        messages = [agui_core.UserMessage(id="1", content="Hello")]

        found = await auto_labels.generate_labels(
            agent_config, CATALOGUE, messages, assistant_text=assistant_text
        )

        assert found == [3, 1]

        get_model_from_config.assert_called_once_with(
            agent_config=agent_config,
        )
        ((sent, info),) = calls
        assert info.instructions == auto_labels.label_instructions(
            ["Manuals", "Billing", "Ops"]
        )
        expected_text = "user: Hello"
        if assistant_text:
            expected_text += f"\nassistant: {assistant_text}"
        assert sent[0].parts[-1].content == expected_text

    @pytest.mark.anyio
    @mock.patch("soliplex.config.agents.get_model_from_config")
    async def test_retries_a_name_outside_the_catalogue(
        self, get_model_from_config
    ):
        model, calls = _answering(["Invented"], ["Billing"])
        get_model_from_config.return_value = model

        found = await auto_labels.generate_labels(
            mock.MagicMock(),
            CATALOGUE,
            [agui_core.UserMessage(id="1", content="Hello")],
        )

        assert found == [2]
        retry = calls[1][0][-1].parts[0]
        assert isinstance(retry, ai_messages.RetryPromptPart)

    @pytest.mark.anyio
    @mock.patch("soliplex.config.agents.get_model_from_config")
    async def test_gives_up_on_names_outside_the_catalogue(
        self, get_model_from_config
    ):
        model, _ = _answering(*[["Invented"]] * 10)
        get_model_from_config.return_value = model

        with pytest.raises(pydantic_ai.UnexpectedModelBehavior):
            await auto_labels.generate_labels(
                mock.MagicMock(),
                CATALOGUE,
                [agui_core.UserMessage(id="1", content="Hello")],
            )


USER = "user1"
ROOM = "room1"


@pytest_asyncio.fixture()
async def threads_engine():
    engine = sqla_asyncio.create_async_engine(
        config_installation.ASYNC_MEMORY_ENGINE_URL,
    )
    async with engine.begin() as connection:
        await connection.run_sync(agui_schema.Base.metadata.create_all)

    yield engine

    await engine.dispose()


async def _storage(threads_engine, work):
    async with sqla_asyncio.AsyncSession(bind=threads_engine) as session:
        async with session.begin():
            return await work(agui_persistence.ThreadStorage(session))


async def _catalogue(threads_engine, *names):
    async def work(ts):
        return [(await ts.create_label(name=name)).id_ for name in names]

    return await _storage(threads_engine, work)


async def _thread(threads_engine, *, runs=1):
    async def work(ts):
        thread = await ts.new_thread(user_name=USER, email="", room_id=ROOM)
        thread_id = thread.thread_id
        for _ in range(runs - 1):
            await ts.new_run(user_name=USER, room_id=ROOM, thread_id=thread_id)
        return thread_id

    return await _storage(threads_engine, work)


async def _set_labels(threads_engine, thread_id, label_ids):
    async def work(ts):
        await ts.set_thread_labels(
            user_name=USER,
            room_id=ROOM,
            thread_id=thread_id,
            label_ids=label_ids,
        )

    await _storage(threads_engine, work)


async def _label_names(threads_engine, thread_id):
    async def work(ts):
        found = await ts.get_threads_labels(thread_ids=[thread_id])
        return [label.name for label in found.get(thread_id, [])]

    return await _storage(threads_engine, work)


class TestMaybeApplyLabels:
    async def _apply(self, threads_engine, thread_id, event_list=()):
        await auto_labels.maybe_apply_labels(
            label_agent_config=self.label_agent_config,
            threads_engine=threads_engine,
            room_id=ROOM,
            thread_id=thread_id,
            user_name=USER,
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
        self, gen_labels, extract_at, threads_engine
    ):
        manuals, _billing, ops = await _catalogue(
            threads_engine, "Manuals", "Billing", "Ops"
        )
        thread_id = await _thread(threads_engine)
        gen_labels.return_value = [ops, manuals]
        extract_at.return_value = "assistant response"
        event_list = [mock.MagicMock()]

        await self._apply(threads_engine, thread_id, event_list)

        assert await _label_names(threads_engine, thread_id) == [
            "Manuals",
            "Ops",
        ]
        extract_at.assert_called_once_with(event_list)
        catalogue = gen_labels.await_args.args[1]
        assert [label.name for label in catalogue] == [
            "Billing",
            "Manuals",
            "Ops",
        ]

    @pytest.mark.anyio
    @mock.patch("soliplex.auto_labels.generate_labels")
    async def test_keeps_labels_the_owner_attached_meanwhile(
        self, gen_labels, threads_engine
    ):
        manuals, billing, ops = await _catalogue(
            threads_engine, "Manuals", "Billing", "Ops"
        )
        thread_id = await _thread(threads_engine)

        async def owner_labels_while_choosing(*args):
            await _set_labels(threads_engine, thread_id, [manuals, billing])
            return [ops, manuals]

        gen_labels.side_effect = owner_labels_while_choosing

        await self._apply(threads_engine, thread_id)

        assert await _label_names(threads_engine, thread_id) == [
            "Billing",
            "Manuals",
            "Ops",
        ]

    @pytest.mark.anyio
    @mock.patch("soliplex.auto_labels.generate_labels")
    async def test_skips_after_the_first_run(self, gen_labels, threads_engine):
        await _catalogue(threads_engine, "Manuals")
        thread_id = await _thread(threads_engine, runs=2)

        await self._apply(threads_engine, thread_id)

        gen_labels.assert_not_awaited()
        assert await _label_names(threads_engine, thread_id) == []

    @pytest.mark.anyio
    @mock.patch("soliplex.auto_labels.generate_labels")
    async def test_skips_a_thread_the_owner_labelled(
        self, gen_labels, threads_engine
    ):
        manuals, _ops = await _catalogue(threads_engine, "Manuals", "Ops")
        thread_id = await _thread(threads_engine)
        await _set_labels(threads_engine, thread_id, [manuals])

        await self._apply(threads_engine, thread_id)

        gen_labels.assert_not_awaited()
        assert await _label_names(threads_engine, thread_id) == ["Manuals"]

    @pytest.mark.anyio
    @mock.patch("soliplex.auto_labels.generate_labels")
    async def test_skips_with_empty_catalogue(
        self, gen_labels, threads_engine
    ):
        thread_id = await _thread(threads_engine)

        await self._apply(threads_engine, thread_id)

        gen_labels.assert_not_awaited()

    @pytest.mark.anyio
    @mock.patch("soliplex.auto_labels.generate_labels")
    async def test_writes_nothing_when_none_chosen(
        self, gen_labels, threads_engine
    ):
        await _catalogue(threads_engine, "Manuals")
        thread_id = await _thread(threads_engine)
        gen_labels.return_value = []

        await self._apply(threads_engine, thread_id)

        gen_labels.assert_awaited_once()
        assert await _label_names(threads_engine, thread_id) == []

    @pytest.mark.anyio
    @mock.patch("soliplex.auto_labels.logfire")
    async def test_logs_and_swallows_failure(self, logfire, threads_engine):
        await self._apply(threads_engine, "no-such-thread")

        logfire.exception.assert_called_once_with(
            "Failed to apply thread labels"
        )
