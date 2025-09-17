import json
import time

import fastapi
import pydantic_ai
from fastapi import responses
from pydantic_ai import messages as ai_messages

from soliplex import models


def openai_chunk_repr(model, i_chunk, chunk):
    # Convert response chunk to NLD JSON for streaming
    chunk_repr = {
        "id": str(i_chunk),
        "object": "chat.completion.chunk",
        "service_tier": "default",
        "system_fingerprint":"ragserver",
        "usage": None,
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "delta": {
                    "content": chunk,
                    "function_call":None,
                    "refusal":None,
                    "role":None,
                    "tool_calls":None,
                },
                "finish_reason":"stop",
                "index": i_chunk,
                "logprobs": None,
            }
        ],
    }
    return f"data: {json.dumps(chunk_repr)}\n\n"


async def stream_chat_responses(
    agent: pydantic_ai.Agent,
    agent_deps: models.AgentDependencies,
    user_question: str,
    message_history: list[ai_messages.ModelMessage],
):

    async with agent.run_stream(
        user_question,
        message_history=message_history,
        deps=agent_deps,
    ) as response:

        i_chunk = 0
        place = 0

        async for text in response.stream_text():
            send = text[place:]
            yield openai_chunk_repr(
                agent.model.model_name,
                i_chunk,
                send,
            )
            place = len(text)
            i_chunk += 1

    yield "data: [DONE]\n\n"


async def openai_chat_completion(
    agent: pydantic_ai.Agent,
    agent_deps: models.AgentDependencies,
    chat_request: models.ChatCompletionRequest,
):
    openai_payload = chat_request.model_dump(exclude_unset=True)
    user_question = openai_payload["messages"][-1]["content"]
    # TODO: figure out how to convert mssage history to PydanticAI's
    #       format.
    # message_history = munge(openai_payload["messages"][:-1])
    message_history = []

    try:
        return responses.StreamingResponse(
            stream_chat_responses(
                agent, agent_deps, user_question, message_history,
            ),
            media_type="text/event-stream",
        )
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        raise fastapi.HTTPException(
            status_code=500,
            detail="An internal server error occurred."
        ) from None

