"""Contract tests for a run shaped the way an AG-UI host makes one.

pydantic-ai's UI adapter passes the whole conversation as
``message_history`` and never passes a prompt.  haiku.rag's evidence
capabilities settle which question a run is answering from that shape, so
a promptless run is exactly the shape the unit tests cannot reach:  they
mock both the adapter and the agent.

``FunctionModel`` means these need neither an LLM nor an embedder.  The
model answers with text and never calls a tool, so the RAG database is
never opened.
"""

import pytest
from haiku.rag.capabilities.compaction import (
    create_capability as create_compaction,
)
from haiku.rag.capabilities.policy import create_capability as create_policy
from haiku.rag.capabilities.rag import create_capability as create_rag
from haiku.rag.config.models import AppConfig
from pydantic_ai import Agent
from pydantic_ai.messages import ModelRequest
from pydantic_ai.messages import ModelResponse
from pydantic_ai.messages import TextPart
from pydantic_ai.messages import UserPromptPart
from pydantic_ai.models.function import FunctionModel

from soliplex import agents

ANSWER = "an answer"


async def _answer(_messages, _info):
    return ModelResponse(parts=[TextPart(ANSWER)])


@pytest.fixture
def agent(tmp_path):
    return Agent(
        FunctionModel(_answer),
        deps_type=agents.AgentDependencies,
        capabilities=[
            create_rag(
                db_path=tmp_path / "kb.lancedb",
                config=AppConfig(),
                defer_loading=False,
            ),
            create_compaction(),
            create_policy(),
        ],
    )


def _deps(state=None):
    return agents.AgentDependencies(
        the_installation=None,
        state=state if state is not None else {},
    )


@pytest.mark.asyncio
async def test_first_message_from_a_ui_host_starts(agent):
    """No prompt, the question in the history, no state."""
    history = [
        ModelRequest(parts=[UserPromptPart(content="a first question")]),
    ]

    result = await agent.run(message_history=history, deps=_deps())

    assert result.output == ANSWER


@pytest.mark.asyncio
async def test_reopened_thread_continues_from_restored_state(agent):
    """A new question carrying the state an earlier question recorded.

    The state is the one a run produced rather than a hand-built dict, so
    this exercises the record the capabilities require to be carried
    between a thread's runs.
    """
    first = [
        ModelRequest(parts=[UserPromptPart(content="an earlier question")]),
    ]
    first_deps = _deps()

    await agent.run(message_history=first, deps=first_deps)

    restored = first_deps.state
    assert restored, "the first run recorded no state to carry"

    reopened = [
        *first,
        ModelResponse(parts=[TextPart(ANSWER)]),
        ModelRequest(parts=[UserPromptPart(content="a follow-up")]),
    ]

    result = await agent.run(message_history=reopened, deps=_deps(restored))

    assert result.output == ANSWER
