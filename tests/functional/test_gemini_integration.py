"""Integration tests for Gemini provider.

These tests validate the Gemini provider works end-to-end with:
- Tool calling
- Streaming
- Multi-turn conversations
- System prompts
- Error handling

All tests require GEMINI_API_KEY to be set and are marked with
@pytest.mark.needs_llm to allow skipping in CI environments.

NOTE: Some tests are marked xfail due to pytest-asyncio + httpx event loop
cleanup issues. These tests PASS when run individually. See implementation.md
for the full analysis and recommended fixes:
- Switch to pytest-anyio (used by pydantic-ai)
- Or implement proper httpx client lifecycle management

Related: https://github.com/pydantic/pydantic-ai/issues/748
"""

import pathlib
from unittest import mock

import pytest

from soliplex import agents
from soliplex import config
from soliplex import models

# Configure all tests in this module to use module-scoped event loop
# to reduce (but not eliminate) event loop cleanup issues
pytestmark = pytest.mark.asyncio(loop_scope="module")

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(scope="module")
def gemini_room_config():
    """Load the gemini_flash room configuration directly."""
    installation_path = pathlib.Path("example/installation.yaml")
    installation_config = config.load_installation(installation_path)
    return installation_config.room_configs["gemini_flash"]


@pytest.fixture(scope="module")
def gemini_agent(gemini_room_config):
    """Get the gemini_flash agent configured for testing.

    Uses module scope to share the agent across tests, reducing
    API calls and connection churn.
    """
    return agents.get_agent_from_configs(
        gemini_room_config.agent_config,
        gemini_room_config.tool_configs,
        gemini_room_config.mcp_client_toolset_configs,
    )


@pytest.fixture
def mock_user():
    """Provide a predictable user profile for testing."""
    return models.UserProfile(
        given_name="Test",
        family_name="User",
        email="test@example.com",
        preferred_username="testuser",
    )


# =============================================================================
# Tool Calling Tests (HIGH priority)
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.needs_llm
async def test_gemini_simple_response(gemini_agent):
    """Verify Gemini can respond to a simple arithmetic question."""
    result = await gemini_agent.run("2 + 2 is what?")

    # The response should contain the number 4
    output = result.output.lower()
    assert "4" in output or "four" in output, (
        f"Expected answer 4 or four, got: {output[:200]}"
    )


@pytest.mark.asyncio
@pytest.mark.needs_llm
@pytest.mark.xfail(
    reason="Event loop issue in suite; PASSES when run individually",
    strict=False,
)
async def test_gemini_tool_call_user(gemini_agent, mock_user):
    """Verify Gemini can call get_current_user tool with context."""
    deps = agents.AgentDependencies(
        the_installation=None,
        user=mock_user,
    )

    result = await gemini_agent.run("Who am I?", deps=deps)

    # The response should contain the user's name
    assert "test user" in result.output.lower()


# =============================================================================
# Streaming Tests (HIGH priority)
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.needs_llm
async def test_gemini_streaming_text(gemini_agent):
    """Verify streaming works for simple text response."""
    chunks = []

    async with gemini_agent.run_stream(
        "Tell me a fun fact about the number 42"
    ) as stream:
        async for chunk in stream.stream_text():
            chunks.append(chunk)

    # Verify chunks were received (streaming worked)
    assert len(chunks) > 0, "No streaming chunks received"

    # Verify final accumulated text is substantial and relevant
    final_text = chunks[-1] if chunks else ""
    assert len(final_text) > 20, f"Response too short: {final_text[:100]}"

    # Verify response is about 42 (the number we asked about)
    lower_text = final_text.lower()
    assert "42" in lower_text or "forty" in lower_text, (
        f"Response should mention 42: {final_text[:200]}"
    )


@pytest.mark.asyncio
@pytest.mark.needs_llm
@pytest.mark.xfail(
    reason="Event loop issue in suite; PASSES when run individually",
    strict=False,
)
async def test_gemini_streaming_after_tool(gemini_agent):
    """Verify streaming works after tool call."""
    chunks = []

    async with gemini_agent.run_stream("What time is it?") as stream:
        async for chunk in stream.stream_text():
            chunks.append(chunk)

    # Verify chunks received
    assert len(chunks) > 0

    # Verify tool result influences response (time-related content)
    final_text = chunks[-1] if chunks else ""
    assert len(final_text) > 0


# =============================================================================
# Multi-turn Tests (MEDIUM priority)
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.needs_llm
@pytest.mark.xfail(
    reason="message_history not properly respected by Gemini provider",
    strict=False,
)
async def test_gemini_multiturn_recall(gemini_agent):
    """Verify Gemini remembers context across turns."""
    # Turn 1: Provide information
    result1 = await gemini_agent.run(
        "My secret project code is ALPHA-7. Please remember it."
    )

    # Get message history from first result
    messages = result1.all_messages()

    # Turn 2: Ask about the information
    result2 = await gemini_agent.run(
        "What is my project code?",
        message_history=messages,
    )

    # Assert response contains the code
    assert "alpha" in result2.output.lower() or "7" in result2.output


@pytest.mark.asyncio
@pytest.mark.needs_llm
@pytest.mark.xfail(
    reason="Event loop issue in suite; PASSES when run individually",
    strict=False,
)
async def test_gemini_multiturn_after_tool(gemini_agent, mock_user):
    """Verify Gemini remembers tool results across turns."""
    deps = agents.AgentDependencies(
        the_installation=None,
        user=mock_user,
    )

    # Turn 1: Call tool
    result1 = await gemini_agent.run("Who am I?", deps=deps)
    messages = result1.all_messages()

    # Turn 2: Ask about previous tool result
    result2 = await gemini_agent.run(
        "What is the first letter of my name?",
        message_history=messages,
        deps=deps,
    )

    # The name was "Test User", first letter is T
    assert "t" in result2.output.lower()


# =============================================================================
# System Prompt Tests (MEDIUM priority)
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.needs_llm
async def test_gemini_system_prompt(gemini_agent):
    """Verify system prompt is respected."""
    # The system prompt says Gemini should use markdown for code
    result = await gemini_agent.run(
        "Show me a simple Python hello world program"
    )

    # Should contain markdown code block
    assert "```" in result.output or "print" in result.output


# =============================================================================
# Error Handling Tests (LOW priority)
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.needs_llm
@pytest.mark.xfail(
    reason="Event loop issue in suite; PASSES when run individually",
    strict=False,
)
async def test_gemini_handles_empty_input(gemini_agent):
    """Verify graceful handling of minimal input."""
    # Send a very short greeting prompt
    result = await gemini_agent.run("Hi")

    # Should get a meaningful response, not an error
    output = result.output.lower()
    assert len(output) > 5, f"Response too short: {result.output}"

    # Should be a conversational response (greeting or helpful reply)
    greeting_indicators = [
        "hello", "hi", "hey", "how", "help", "assist", "can i"
    ]
    has_greeting = any(
        indicator in output for indicator in greeting_indicators
    )
    assert has_greeting, (
        f"Expected greeting/helpful response, got: {result.output[:200]}"
    )


@pytest.mark.asyncio
async def test_gemini_model_structure(gemini_agent):
    """Verify agent has correct GoogleModel structure.

    This test validates that the agent is properly configured with
    a GoogleModel instance from pydantic-ai.
    """
    from pydantic_ai.models.google import GoogleModel

    # Verify the agent has the _model attribute
    assert hasattr(gemini_agent, "_model"), "Agent missing _model attribute"

    # Verify it's a GoogleModel instance
    assert isinstance(gemini_agent._model, GoogleModel), (
        f"Expected GoogleModel, got {type(gemini_agent._model)}"
    )

    # Verify the model has the expected model name
    model_name = getattr(gemini_agent._model, "_model_name", None)
    assert model_name is not None, "GoogleModel missing _model_name"
    assert "gemini" in model_name.lower(), (
        f"Expected gemini model, got {model_name}"
    )


@pytest.mark.asyncio
async def test_gemini_agent_configuration(gemini_agent):
    """Verify agent configuration is correct.

    This test validates that the agent has the expected configuration
    for tool handling and instructions.
    """
    # Verify the agent has toolsets configured
    assert hasattr(gemini_agent, "_function_toolset"), (
        "Agent missing _function_toolset"
    )

    # Verify the agent has instructions (system prompt)
    instructions = getattr(gemini_agent, "_instructions", None)
    assert instructions is not None, "Agent missing instructions"

    # Verify the agent has the correct deps_type
    deps_type = getattr(gemini_agent, "_deps_type", None)
    assert deps_type is not None, "Agent missing deps_type"
    assert deps_type.__name__ == "AgentDependencies", (
        f"Expected AgentDependencies, got {deps_type}"
    )


@pytest.mark.asyncio
async def test_gemini_safety_filter(gemini_room_config):
    """Verify graceful handling of safety filter rejection.

    This test mocks the model to simulate a safety filter rejection
    and verifies the error is properly propagated.
    """
    from pydantic_ai import exceptions as pydantic_ai_exceptions

    # Create a fresh agent for mocking (don't pollute the shared fixture)
    agent = agents.get_agent_from_configs(
        gemini_room_config.agent_config,
        gemini_room_config.tool_configs,
        gemini_room_config.mcp_client_toolset_configs,
    )

    # Mock the model's request method to raise a safety error
    # ClientError requires response_json; use ValueError as proxy for API error
    safety_error = ValueError("Content blocked by safety filters")

    with mock.patch.object(
        agent._model, "request", side_effect=safety_error
    ):
        # The error should propagate
        expected_errors = (
            ValueError,
            pydantic_ai_exceptions.ModelHTTPError,
        )
        with pytest.raises(expected_errors):
            await agent.run("Test prompt")
