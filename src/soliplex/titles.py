from __future__ import annotations

import logfire
import pydantic
import pydantic_ai
from ag_ui import core as agui_core

from soliplex import agents
from soliplex import config

TITLE_PROMPT = """\
Generate a short, concise title (max 8 words) for this conversation.
The title should capture the main topic or intent.
Return null if there isn't enough context to generate a meaningful title.\
"""


class ThreadTitle(pydantic.BaseModel):
    title: str | None = None


def format_messages(messages: list[agui_core.Message]) -> str:
    lines = []
    for msg in messages:
        if msg.role not in ("user", "assistant"):
            continue
        content = msg.content
        if content is None:
            continue
        if isinstance(content, list):
            parts = [
                part.text
                for part in content
                if isinstance(part, agui_core.TextInputContent)
            ]
            content = "\n".join(parts)
        lines.append(f"{msg.role}: {content}")
    return "\n".join(lines)


async def generate_title(
    agent_config: config.AgentConfig,
    messages: list[agui_core.Message],
) -> str | None:
    model = agents.make_model(agent_config)
    agent = pydantic_ai.Agent(
        model=model,
        output_type=ThreadTitle,
        instructions=TITLE_PROMPT,
    )
    formatted = format_messages(messages)
    result = await agent.run(formatted)
    return result.output.title


async def maybe_generate_title(
    *,
    the_threads,
    the_installation,
    room_id: str,
    thread_id: str,
    user_name: str,
    messages: list[agui_core.Message],
):
    try:
        thread = await the_threads.get_thread(
            user_name=user_name,
            room_id=room_id,
            thread_id=thread_id,
        )
        if thread.thread_metadata is not None:
            return

        agent_config = the_installation.get_title_agent_config(
            room_id,
        )
        title = await generate_title(agent_config, messages)
        if title is None:
            return

        await the_threads.update_thread_metadata(
            user_name=user_name,
            room_id=room_id,
            thread_id=thread_id,
            thread_metadata={"name": title},
        )
    except Exception:
        logfire.exception("Failed to generate thread title")
