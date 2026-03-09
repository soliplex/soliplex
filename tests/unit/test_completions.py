import json
from unittest import mock

import pytest

from soliplex import completions
from soliplex.config import agents as config_agents
from soliplex.config import completions as config_completions
from soliplex.config import tools as config_tools

COMPLETION_ID = "testing-completion"
SYSTEM_PROMPT = "You are a test"
MODEL_NAME = "test-model"

BARE_CONFIG = config_completions.CompletionConfig(
    id=COMPLETION_ID,
    agent_config=config_agents.AgentConfig(
        id=f"completions-{COMPLETION_ID}",
        system_prompt=SYSTEM_PROMPT,
        model_name=MODEL_NAME,
    ),
)
BARE_CONFIG_YAML = f"""\
id: "{COMPLETION_ID}"
agent:
    system_prompt: "{SYSTEM_PROMPT}"
    model_name: "{MODEL_NAME}"
"""

W_TOOLS_CONFIG = config_completions.CompletionConfig(
    id=COMPLETION_ID,
    agent_config=config_agents.AgentConfig(
        id=f"completions-{COMPLETION_ID}",
        system_prompt=SYSTEM_PROMPT,
        model_name=MODEL_NAME,
    ),
    tool_configs={
        "get_current_datetime": config_tools.ToolConfig(
            tool_name="soliplex.tools.get_current_datetime",
        ),
    },
)
W_TOOLS_CONFIG_YAML = f"""\
id: "{COMPLETION_ID}"
agent:
    system_prompt: "{SYSTEM_PROMPT}"
    model_name: "{MODEL_NAME}"
tools:
    - tool_name: "soliplex.tools.get_current_datetime"
"""


@mock.patch("soliplex.completions.time")
def test_openai_chunk_repr(time_module):
    MODEL = "testing-model"
    CHUNK = "Test chunk"
    time_module.time.return_value = 123456.789

    found = completions.openai_chunk_repr(MODEL, 999, CHUNK)

    assert found.startswith("data: ")
    assert found.endswith("\n\n")

    dumped = json.loads(found[len("data: ") : -len("\n\n")])

    assert dumped["id"] == "999"
    assert dumped["model"] == MODEL
    assert dumped["created"] == 123456

    (choice,) = dumped["choices"]
    assert choice["index"] == 999
    assert choice["delta"]["content"] == CHUNK


@pytest.mark.anyio
@pytest.mark.parametrize("n_chunks", [1, 3, 5])
@mock.patch("soliplex.completions.openai_chunk_repr")
async def test_stream_chat_responses(ocr, n_chunks):
    QUESTION = "Why is blue?"
    HISTORY = ()
    TEXT = "This text is long enough to break up into chunks"
    MODEL = "test-model"

    agent = mock.Mock(spec_set=["model", "run_stream"])
    model = agent.model = mock.Mock(spec_set=["model_name"])
    model.model_name = MODEL
    agent_deps = mock.Mock(spec_set=())

    chunks = []

    chunk_len = len(TEXT) // n_chunks
    remaining = TEXT

    i_chunk = 1
    while remaining:
        chunk = TEXT[: i_chunk * chunk_len]
        remaining = remaining[chunk_len:]
        chunks.append(chunk)
        i_chunk += 1

    async def get_chunks():
        for chunk in chunks:
            yield chunk

    rs = agent.run_stream = mock.Mock()
    srr = rs.return_value = mock.AsyncMock()
    srr.__aenter__.return_value.stream_text = get_chunks

    chunk_reprs = []

    async for cr in completions.stream_chat_responses(
        agent,
        agent_deps,
        QUESTION,
        HISTORY,
    ):
        chunk_reprs.append(cr)

    chunk_reprs, done_repr = chunk_reprs[:-1], chunk_reprs[-1]

    assert done_repr == "data: [DONE]\n\n"

    for i_cr, (cr, ocr_call, chunk) in enumerate(
        zip(
            chunk_reprs,
            ocr.call_args_list,
            chunks,
            strict=True,
        )
    ):
        assert cr is ocr.return_value
        start_index = i_cr * chunk_len
        assert ocr_call.args == (MODEL, i_cr, chunk[start_index:])

    rs.assert_called_once_with(
        QUESTION,
        message_history=HISTORY,
        deps=agent_deps,
    )
