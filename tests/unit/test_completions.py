import json
import pathlib
import tempfile
from unittest import mock

import fastapi
import pytest

from soliplex import completions
from soliplex import config
from soliplex import models

COMPLETION_ID = "testing"
SYSTEM_PROMPT = "You are a test"
MODEL_NAME = "test-model"

BARE_CONFIG = config.CompletionConfig(
    COMPLETION_ID,
    agent_config=config.AgentConfig(
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

W_TOOLS_CONFIG = config.CompletionConfig(
    COMPLETION_ID,
    agent_config=config.AgentConfig(
        id=f"completions-{COMPLETION_ID}",
        system_prompt=SYSTEM_PROMPT,
        model_name=MODEL_NAME,
    ),
    tool_configs={
        "get_current_datetime": config.ToolConfig(
            tool_name="soliplex.tools.get_current_datetime",
        ),
        "search_documents": config.SearchDocumentsToolConfig(
            search_documents_limit=1,
            rag_lancedb_override_path="/dev/null/",
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
    - tool_name: "soliplex.tools.search_documents"
        search_documents_limit: 1
        rag_lancedb_override_path: "/dev/null/"
"""


@pytest.fixture
def temp_dir() -> pathlib.Path:
    with tempfile.TemporaryDirectory() as td:
        yield pathlib.Path(td)


@mock.patch("soliplex.completions.time")
def test_openai_chunk_repr(time_module):
    MODEL = "testing"
    CHUNK = "Test chunk"
    time_module.time.return_value = 123456.789

    found = completions.openai_chunk_repr(MODEL, 999, CHUNK)

    assert found.startswith("data: ")
    assert found.endswith("\n\n")

    dumped = json.loads(found[len("data: "):-len("\n\n")])

    assert dumped["id"] == "999"
    assert dumped["model"] == MODEL
    assert dumped["created"] == 123456

    choice, = dumped["choices"]
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
        chunk = TEXT[:i_chunk * chunk_len]
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
        agent, agent_deps, QUESTION, HISTORY,
    ):
        chunk_reprs.append(cr)

    chunk_reprs, done_repr = chunk_reprs[:-1], chunk_reprs[-1]

    assert done_repr == "data: [DONE]\n\n"

    for i_cr, (cr, ocr_call, chunk) in enumerate(zip(
        chunk_reprs, ocr.call_args_list, chunks, strict=True,
    )):
        assert cr is ocr.return_value
        start_index = i_cr * chunk_len
        assert ocr_call.args == (MODEL, i_cr, chunk[start_index:])

    rs.assert_called_once_with(
        QUESTION, message_history=HISTORY, deps=agent_deps,
    )


@pytest.mark.anyio
@pytest.mark.parametrize("w_exception", [False, True])
@pytest.mark.parametrize("w_history", [False, True])
@mock.patch("soliplex.completions.stream_chat_responses")
@mock.patch("fastapi.responses.StreamingResponse")
async def test_openai_chat_completion(sr_class, scp, w_history, w_exception):

    CR_MESSAGES = [
        {
            "role": "user",
            "content": "Why is blue?",
        },
    ]
    agent = mock.Mock(spec_set=["model", "run_stream"])
    agent_deps = mock.Mock(spec_set=())

    if w_history:
        CR_MESSAGES.insert(0, {
            "role": "model",
            "content": "hello",
        })

    chat_request = mock.create_autospec(models.ChatCompletionRequest)
    chat_request.model_dump.return_value = {
        "model": "NOT USED",
        "messages": CR_MESSAGES,
    }

    if w_exception:
        scp.side_effect = ValueError("testing")

    if w_exception:
        with pytest.raises(fastapi.HTTPException):
            await completions.openai_chat_completion(
                agent, agent_deps, chat_request,
            )
        return
    else:
        response = await completions.openai_chat_completion(
            agent, agent_deps, chat_request,
        )

    assert response is sr_class.return_value

    sr_class.assert_called_once_with(
        scp.return_value, media_type="text/event-stream",
    )

    # TODO not passing history
    scp.assert_called_once_with(agent, agent_deps, "Why is blue?", [])

