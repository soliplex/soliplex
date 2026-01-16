"""Functional test configuration.

Includes fixtures for test clients and pytest-anyio httpx client management.
"""

import httpx
import pydantic_ai.models
import pytest
from fastapi import testclient

from soliplex import agents as agents_mod
from soliplex import main


@pytest.fixture(scope="session")
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
    for agent in agents_mod._agent_cache.values():
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
            await httpx_client.aclose()

    # Clear the agent cache so fresh agents are created per test
    agents_mod._agent_cache.clear()


@pytest.fixture(scope="module")
def client():
    with testclient.TestClient(
        main.create_app("example/minimal.yaml")
    ) as client:
        yield client


@pytest.fixture(scope="module")
def client_no_llm():
    with testclient.TestClient(
        main.create_app("example/functest_no_llm.yaml")
    ) as client:
        yield client
