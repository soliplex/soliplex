from __future__ import annotations

import logfire
import pydantic
import pydantic_ai
from ag_ui import core as agui_core
from sqlalchemy.ext import asyncio as sqla_asyncio

from soliplex.agui import persistence as agui_persistence
from soliplex.config import agents as config_agents

DEFAULT_THREAD_NAME = "New Thread"

TITLE_PROMPT = """\
Generate a short, concise title (max 8 words) for this conversation.
The title should capture the main topic or intent.
Return null if there isn't enough context to generate a meaningful \
title.\
"""


class ThreadTitle(pydantic.BaseModel):
    title: str | None = None


def format_message(msg: agui_core.Message) -> str | None:
    if msg.role not in ("user", "assistant"):
        return None
    content = msg.content
    if content is None:
        return None
    if isinstance(content, list):
        parts = [
            part.text
            for part in content
            if isinstance(part, agui_core.TextInputContent)
        ]
        if not parts:
            return None
        content = "\n".join(parts)
    return f"{msg.role}: {content}"


def format_messages(messages: list[agui_core.Message]) -> str:
    return "\n".join(filter(None, map(format_message, messages)))


def extract_assistant_text(
    event_list: list[agui_core.Event],
) -> str:
    """Build assistant text from TEXT_MESSAGE_CONTENT events."""
    parts = [
        event.delta
        for event in event_list
        if event.type == agui_core.EventType.TEXT_MESSAGE_CONTENT
    ]
    return "".join(parts)


async def generate_title(
    agent_config: config_agents.AgentConfig,
    messages: list[agui_core.Message],
    assistant_text: str = "",
) -> str | None:
    model = config_agents.get_model_from_config(agent_config=agent_config)
    agent = pydantic_ai.Agent(
        model=model,
        output_type=ThreadTitle,
        instructions=TITLE_PROMPT,
    )
    formatted = format_messages(messages)
    if assistant_text:
        formatted += f"\nassistant: {assistant_text}"
    result = await agent.run(formatted)
    return result.output.title


async def maybe_generate_title(
    *,
    title_agent_config: config_agents.AgentConfig,
    threads_engine: sqla_asyncio.AsyncEngine,
    room_id: str,
    thread_id: str,
    user_name: str,
    messages: list[agui_core.Message],
    event_list: list[agui_core.Event] = (),
):
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
            thread_metadata = await thread.awaitable_attrs.thread_metadata

        if thread_metadata is not None and thread_metadata.name not in (
            None,
            DEFAULT_THREAD_NAME,
        ):
            return

        assistant_text = extract_assistant_text(event_list)
        title = await generate_title(
            title_agent_config, messages, assistant_text
        )
        if title is None:
            return

        async with sqla_asyncio.AsyncSession(
            bind=threads_engine,
        ) as session:
            the_threads = agui_persistence.ThreadStorage(session)
            await the_threads.update_thread_metadata(
                user_name=user_name,
                room_id=room_id,
                thread_id=thread_id,
                thread_metadata={"name": title},
            )
    except Exception:
        logfire.exception("Failed to generate thread title")
