"""Attach labels from the catalogue to a thread after its first run.

The counterpart of 'titles': the same throwaway agent, run at the same
point, but choosing from the catalogue instead of writing free text.
"""

from __future__ import annotations

import typing

import logfire
import pydantic
import pydantic_ai
from ag_ui import core as agui_core
from sqlalchemy import sql as sqla_sql
from sqlalchemy.ext import asyncio as sqla_asyncio

from soliplex import titles
from soliplex.agui import persistence as agui_persistence
from soliplex.agui import schema as agui_schema
from soliplex.config import agents as config_agents

MAX_AUTO_LABELS = 3

LABEL_PROMPT = f"""\
Choose the labels that describe this conversation, from the allowed \
names only.
Pick at most {MAX_AUTO_LABELS}, and only labels that clearly apply.
Return an empty list if none of them fit.\
"""


def labels_output_type(names: list[str]) -> type[pydantic.BaseModel]:
    """Build an output type which admits only the catalogue's names."""
    choice = typing.Literal[tuple(names)]
    return pydantic.create_model(
        "ThreadLabels",
        label_names=(
            list[choice],
            pydantic.Field(default_factory=list, max_length=MAX_AUTO_LABELS),
        ),
    )


def label_instructions(names: list[str]) -> str:
    """The prompt, with the allowed names spelled out."""
    allowed = "\n".join(f"- {name}" for name in names)
    return f"{LABEL_PROMPT}\n\nAllowed labels:\n{allowed}"


async def generate_labels(
    agent_config: config_agents.AgentConfig,
    catalogue: list[agui_schema.Label],
    messages: list[agui_core.Message],
    assistant_text: str = "",
) -> list[int]:
    """Return the IDs of the labels the agent chose, in its order."""
    ids_by_name = {label.name: label.id_ for label in catalogue}
    names = list(ids_by_name)
    model = config_agents.get_model_from_config(agent_config=agent_config)
    agent = pydantic_ai.Agent(
        model=model,
        output_type=labels_output_type(names),
        instructions=label_instructions(names),
    )
    result = await agent.run(
        titles.format_conversation(messages, assistant_text)
    )
    return [
        ids_by_name[name] for name in dict.fromkeys(result.output.label_names)
    ]


async def maybe_apply_labels(
    *,
    label_agent_config: config_agents.AgentConfig,
    threads_engine: sqla_asyncio.AsyncEngine,
    room_id: str,
    thread_id: str,
    user_name: str,
    messages: list[agui_core.Message],
    event_list: list[agui_core.Event] = (),
):
    """Label a thread from the catalogue once its first run finishes.

    Only the first run: labelling again on later runs would put back
    labels the owner has since removed. A thread whose first run does
    not finish is therefore never labelled automatically.
    """
    try:
        async with sqla_asyncio.AsyncSession(
            bind=threads_engine,
        ) as session:
            the_threads = agui_persistence.ThreadStorage(session)
            thread = await the_threads.get_thread(
                user_name=user_name,
                room_id=room_id,
                thread_id=thread_id,
            )
            run_count = await session.scalar(
                sqla_sql.select(sqla_sql.func.count()).where(
                    agui_schema.Run.thread_id_ == thread.id_
                )
            )
            if run_count != 1:
                return
            # The owner got there first, during the run.
            if await thread.awaitable_attrs.labels:
                return
            catalogue = await the_threads.list_labels()

        if not catalogue:
            return

        assistant_text = titles.extract_assistant_text(event_list)
        label_ids = await generate_labels(
            label_agent_config, catalogue, messages, assistant_text
        )
        if not label_ids:
            return

        async with sqla_asyncio.AsyncSession(
            bind=threads_engine,
        ) as session:
            the_threads = agui_persistence.ThreadStorage(session)
            # This helper owns the session, so it owns the commit.
            async with session.begin():
                thread = await the_threads.get_thread(
                    user_name=user_name,
                    room_id=room_id,
                    thread_id=thread_id,
                )
                # Added to, never replacing: the owner may have attached
                # labels while the agent was choosing.
                current = [
                    label.id_ for label in await thread.awaitable_attrs.labels
                ]
                await the_threads.set_thread_labels(
                    user_name=user_name,
                    room_id=room_id,
                    thread_id=thread_id,
                    label_ids=current + label_ids,
                )
    except Exception:
        logfire.exception("Failed to apply thread labels")
