import pytest

SYSTEM_PROMPT = """\
You are an expert AI assistant specializing in information retrieval.

Your answers should be clear, concise, and ready for production use.

Always provide code or examples in Markdown blocks.

If asked for the current time, you must use the 'get_current_datetime_test'
tool.
"""


def get_current_datetime_test():
    return "2025-09-30T09:30:01.0+00:00"


@pytest.fixture(scope="module")
def agent(client):
    the_installation = client.app_state["the_installation"]
    agent = the_installation.get_agent_by_id("alternate_chat")
    agent.instructions = SYSTEM_PROMPT
    agent.toolsets[0].add_function(get_current_datetime_test)

    return agent


@pytest.mark.asyncio
@pytest.mark.needs_llm
async def test_agent_tool_calling_w_run(agent):
    res = await agent.run("what is the date?")
    assert "2025" in res.output
    assert "09" in res.output or "September" in res.output


@pytest.mark.asyncio
@pytest.mark.needs_llm
async def test_agent_tool_calling_w_streaming(agent):
    output = ""
    async with agent.run_stream("what is the date?") as res:
        async for message in res.stream_text():
            output = message
    assert "2025" in output
    assert "09" in output or "September" in output
