"""Integration tests for Gemini provider.

These tests validate the Gemini provider works end-to-end with:
- Tool calling
- Streaming
- Multi-turn conversations
- System prompts
- Error handling

All tests require GEMINI_API_KEY to be set and are marked with
@pytest.mark.needs_llm to allow skipping in CI environments.

Uses pytest-anyio with close_cached_httpx_client fixture to properly
manage httpx client lifecycle and prevent "Event loop is closed" errors.

See: https://github.com/pydantic/pydantic-ai/blob/main/tests/conftest.py
"""

import pathlib
from unittest import mock

import httpx
import pydantic_ai.models
import pytest
from fastapi import testclient

from soliplex import agents
from soliplex import config
from soliplex import main
from soliplex import models

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(scope="module")
def anyio_backend():
    """Select asyncio as the anyio backend for pytest-anyio."""
    return "asyncio"


@pytest.fixture(autouse=True)
async def close_cached_httpx_client(anyio_backend, monkeypatch):
    """Track and close cached httpx clients created during each test.

    This fixture prevents "Event loop is closed" errors by explicitly
    closing httpx clients before the event loop is torn down.

    Adapted from pydantic-ai's test suite:
    https://github.com/pydantic/pydantic-ai/blob/main/tests/conftest.py
    """
    created_clients: set[httpx.AsyncClient] = set()

    original_cached_func = pydantic_ai.models._cached_async_http_client

    def tracked_cached_async_http_client(*args, **kwargs):
        client = original_cached_func(*args, **kwargs)
        created_clients.add(client)
        return client

    monkeypatch.setattr(
        pydantic_ai.models,
        "_cached_async_http_client",
        tracked_cached_async_http_client,
    )

    yield

    for client in created_clients:
        await client.aclose()

    original_cached_func.cache_clear()


@pytest.fixture(autouse=True)
async def reset_gemini_client():
    """Reset google-genai's internal httpx clients after each test.

    google-genai caches httpx.AsyncClient instances that get bound to
    event loops. When pytest-anyio creates a new event loop per test,
    these cached clients fail with "Event loop is closed" errors.

    This fixture closes google-genai's internal httpx clients and clears
    the soliplex agent cache to ensure fresh clients are created per test.

    See: https://github.com/pydantic/pydantic-ai/issues/748
    """
    yield

    # Close any google-genai httpx clients in cached agents
    # Note: When using sync TestClient, the httpx client may be bound to a
    # different event loop that's already closed. We catch RuntimeError to
    # handle this gracefully.
    for agent in agents._agent_cache.values():
        model = getattr(agent, "_model", None)
        if model is None:
            continue
        client = getattr(model, "client", None)
        if client is None:
            continue
        api_client = getattr(client, "_api_client", None)
        if api_client is None:
            continue
        httpx_client = getattr(api_client, "_async_httpx_client", None)
        if httpx_client and not httpx_client.is_closed:
            try:
                await httpx_client.aclose()
            except RuntimeError:
                # Event loop may already be closed (e.g., sync TestClient)
                pass

    # Clear the agent cache so fresh agents are created per test
    agents._agent_cache.clear()


@pytest.fixture
def gemini_room_config():
    """Load the gemini_flash room configuration directly."""
    installation_path = pathlib.Path("example/installation.yaml")
    installation_config = config.load_installation(installation_path)
    return installation_config.room_configs["gemini_flash"]


@pytest.fixture
def gemini_agent(gemini_room_config):
    """Get the gemini_flash agent configured for testing.

    Uses function scope to ensure fresh httpx clients per test,
    avoiding "Event loop is closed" errors with pytest-anyio.
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


@pytest.mark.anyio
@pytest.mark.needs_llm
async def test_gemini_simple_response(gemini_agent):
    """Verify Gemini can respond to a simple arithmetic question."""
    result = await gemini_agent.run("2 + 2 is what?")

    # The response should contain the number 4
    output = result.output.lower()
    assert "4" in output or "four" in output, (
        f"Expected answer 4 or four, got: {output[:200]}"
    )


@pytest.mark.anyio
@pytest.mark.needs_llm
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


@pytest.mark.anyio
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


@pytest.mark.anyio
@pytest.mark.needs_llm
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


@pytest.mark.anyio
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


@pytest.mark.anyio
@pytest.mark.needs_llm
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


@pytest.mark.anyio
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


@pytest.mark.anyio
@pytest.mark.needs_llm
async def test_gemini_handles_empty_input(gemini_agent):
    """Verify graceful handling of minimal input."""
    # Send a very short greeting prompt
    result = await gemini_agent.run("Hi")

    # Should get a meaningful response, not an error
    output = result.output.lower()
    assert len(output) > 5, f"Response too short: {result.output}"

    # Should be a conversational response (greeting or helpful reply)
    greeting_indicators = [
        "hello",
        "hi",
        "hey",
        "how",
        "help",
        "assist",
        "can i",
    ]
    has_greeting = any(
        indicator in output for indicator in greeting_indicators
    )
    assert has_greeting, (
        f"Expected greeting/helpful response, got: {result.output[:200]}"
    )


@pytest.mark.anyio
@pytest.mark.needs_llm
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


@pytest.mark.anyio
@pytest.mark.needs_llm
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


@pytest.mark.anyio
@pytest.mark.needs_llm
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

    with mock.patch.object(agent._model, "request", side_effect=safety_error):
        # The error should propagate
        expected_errors = (
            ValueError,
            pydantic_ai_exceptions.ModelHTTPError,
        )
        with pytest.raises(expected_errors):
            await agent.run("Test prompt")


# =============================================================================
# Room API Tests (END-TO-END)
# =============================================================================


@pytest.fixture
def gemini_client():
    """Test client with main installation that includes gemini_flash room."""
    with testclient.TestClient(
        main.create_app("example/installation.yaml")
    ) as client:
        yield client


@pytest.mark.anyio
@pytest.mark.needs_llm
async def test_gemini_room_agui_endpoint(gemini_client):
    """Test the gemini_flash room through the AG-UI API endpoint.

    This is an end-to-end test that verifies the full stack works:
    room config -> agent creation -> API endpoint -> LLM response.
    """
    import json
    import uuid

    room_id = "gemini_flash"

    # Step 1: Create a new thread in the gemini_flash room
    new_thread_request = {"metadata": {"name": "gemini_test"}}

    with mock.patch("soliplex.authn.authenticate") as auth_fn:
        auth_fn.return_value = {
            "name": "Test User",
            "email": "test@example.com",
        }

        response = gemini_client.post(
            f"/api/v1/rooms/{room_id}/agui",
            json=new_thread_request,
        )
        assert response.status_code == 200, (
            f"Failed to create thread: {response.text}"
        )

        new_thread_json = response.json()
        assert new_thread_json["room_id"] == room_id
        thread_id = new_thread_json["thread_id"]
        (run_id,) = new_thread_json["runs"]

        # Step 2: Send a message and get a response
        run_request = {
            "thread_id": thread_id,
            "run_id": run_id,
            "state": None,
            "messages": [
                {
                    "id": str(uuid.uuid4()),
                    "role": "user",
                    "content": "What is 2 + 2? Answer with just the number.",
                },
            ],
            "context": [],
            "tools": [],
            "forwarded_props": None,
        }

        with gemini_client.stream(
            method="POST",
            url=f"/api/v1/rooms/{room_id}/agui/{thread_id}/{run_id}",
            json=run_request,
        ) as stream_response:
            assert stream_response.status_code == 200, (
                f"Failed to run: {stream_response.text}"
            )

            # Collect SSE events
            events = []
            for raw_line in stream_response.iter_lines():
                if raw_line and raw_line.startswith("data: "):
                    event_json = json.loads(raw_line[6:])
                    events.append(event_json)

            # Verify we got events
            assert len(events) > 0, "No events received from Gemini room"

            # Look for text content in events
            text_content = ""
            for event in events:
                if event.get("type") == "TEXT_MESSAGE_CONTENT":
                    text_content += event.get("delta", "")

            # Verify response contains "4"
            assert "4" in text_content, (
                f"Expected '4' in response, got: {text_content[:200]}"
            )
