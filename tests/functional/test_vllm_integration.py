"""Functional tests for the vLLM provider against a live vLLM server.

The target server must serve a chat template that accepts one system
message, first only (for example Qwen's). The openai provider case is
expected to fail on such a server when a deferred capability is loaded.
"""

import json
import os
import pathlib

import httpx2
import pydantic_ai
import pytest
from pydantic_ai import exceptions as ai_exceptions
from pydantic_ai import messages as ai_messages
from pydantic_ai.providers import _openai_compatible

from soliplex.capabilities import filesystem as cap_fs
from soliplex.config import agents as config_agents
from soliplex.config import installation as config_installation
from soliplex.config import secrets as config_secrets

VLLM_BASE_URL = os.environ.get("VLLM_BASE_URL")
VLLM_MODEL = os.environ.get("VLLM_MODEL")

pytestmark = pytest.mark.skipif(
    not (VLLM_BASE_URL and VLLM_MODEL),
    reason="VLLM_BASE_URL and VLLM_MODEL are required",
)

INSTRUCTIONS = "Load the greeter capability when greeting, then follow it"
GREETING_SENTENCE = "Welcome aboard, weary traveler."
GREETER_INSTRUCTIONS = (
    "Read resources/g.txt with read_resource and greet the user with its "
    "sentence."
)


@pytest.fixture(scope="module")
def anyio_backend():
    """Select asyncio as the anyio backend for pytest-anyio."""
    return "asyncio"


@pytest.fixture
async def close_httpx_clients(anyio_backend, monkeypatch):
    """Track and close httpx clients created during each test."""
    created_clients: set[httpx2.AsyncClient] = set()

    original_factory = _openai_compatible.create_async_httpx2_client

    def tracked_create_async_httpx2_client(*args, **kwargs):
        client = original_factory(*args, **kwargs)
        created_clients.add(client)
        return client

    monkeypatch.setattr(
        _openai_compatible,
        "create_async_httpx2_client",
        tracked_create_async_httpx2_client,
    )

    yield

    for client in created_clients:
        try:
            await client.aclose()
        except RuntimeError:
            pass


def _build_agent(
    tmp_path: pathlib.Path,
    provider_type: str,
) -> tuple[pydantic_ai.Agent, list[list[str]]]:
    """Build an agent and request role recorder for a provider type."""
    greeter_dir = tmp_path / "greeter"
    resources_dir = greeter_dir / "resources"
    resources_dir.mkdir(parents=True)
    (resources_dir / "g.txt").write_text(
        f"{GREETING_SENTENCE}\n",
        encoding="utf-8",
    )

    capability = cap_fs.FilesystemCapability(
        id="greeter",
        description="Greets the user using a bundled resource.",
        defer_loading=True,
        instructions=GREETER_INSTRUCTIONS,
        path=greeter_dir,
    )

    installation_config = config_installation.InstallationConfig(
        id="vllm-functional-test",
        secrets=[
            config_secrets.SecretConfig(
                secret_name="DUMMY_API_KEY",
                sources=[
                    config_secrets.RandomCharsSecretSource(
                        secret_name="DUMMY_API_KEY",
                    ),
                ],
            ),
        ],
    )

    config_dict = {
        "id": f"vllm-test-{provider_type}",
        "provider_type": provider_type,
        "provider_base_url": VLLM_BASE_URL,
        "model_name": VLLM_MODEL,
    }
    if provider_type == "openai":
        config_dict["provider_key"] = "secret:DUMMY_API_KEY"

    agent_config = config_agents.extract_agent_config(
        installation_config,
        tmp_path / "agent.yaml",
        config_dict,
    )
    model = config_agents.get_model_from_config(agent_config=agent_config)

    captured_roles: list[list[str]] = []

    async def capture_request_roles(request: httpx2.Request) -> None:
        if request.content:
            payload = json.loads(request.content)
            if "messages" in payload:
                captured_roles.append(
                    [message["role"] for message in payload["messages"]]
                )

    http_client = model.provider.client._client
    http_client.event_hooks["request"].append(capture_request_roles)

    agent = pydantic_ai.Agent(
        model=model,
        instructions=INSTRUCTIONS,
        capabilities=[capability],
    )
    return agent, captured_roles


@pytest.mark.anyio
@pytest.mark.needs_llm
async def test_openai_provider_sends_mid_conversation_system_messages(
    tmp_path,
    close_httpx_clients,
):
    """Verify the openai provider fails with 400 after loading a skill."""
    agent, captured_roles = _build_agent(tmp_path, "openai")

    with pytest.raises(ai_exceptions.ModelHTTPError) as exc_info:
        await agent.run("Please greet me.")

    assert exc_info.value.status_code == 400
    assert captured_roles
    assert "system" in captured_roles[-1][1:]


@pytest.mark.anyio
@pytest.mark.needs_llm
async def test_vllm_provider_runs_deferred_skill(
    tmp_path,
    close_httpx_clients,
):
    """Verify the vllm provider loads and runs a deferred skill cleanly."""
    agent, captured_roles = _build_agent(tmp_path, "vllm")

    result = await agent.run("Please greet me.")

    tool_names = [
        part.tool_name
        for message in result.all_messages()
        for part in message.parts
        if isinstance(part, ai_messages.ToolCallPart)
    ]
    assert "load_capability" in tool_names
    assert captured_roles
    for roles in captured_roles:
        assert "system" not in roles[1:]
    assert result.output.strip()
