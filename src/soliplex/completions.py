import json
import time

import pydantic_ai
from pydantic_ai import messages as ai_messages

from soliplex import agents


def openai_chunk_repr(model, i_chunk, chunk):
    # Convert response chunk to NLD JSON for streaming
    chunk_repr = {
        "id": str(i_chunk),
        "object": "chat.completion.chunk",
        "service_tier": "default",
        "system_fingerprint": "ragserver",
        "usage": None,
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "delta": {
                    "content": chunk,
                    "function_call": None,
                    "refusal": None,
                    "role": None,
                    "tool_calls": None,
                },
                "finish_reason": "stop",
                "index": i_chunk,
                "logprobs": None,
            }
        ],
    }
    return f"data: {json.dumps(chunk_repr)}\n\n"


async def stream_chat_responses(
    agent: pydantic_ai.Agent,
    agent_deps: agents.AgentDependencies,
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
