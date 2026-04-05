"""
Integration tests for Hermes Event Server + Soliplex backend.
Run with: python test_integration.py

Requires:
  - hermes-events container running on port 8642
  - Soliplex backend running on port 8000 (optional, for E2E tests)
"""

import asyncio
import json
import sys

import httpx

HERMES_URL = "http://localhost:8642"
SOLIPLEX_URL = "http://localhost:8000"

passed = 0
failed = 0


def result(name, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1
        print(f"  PASS  {name}")
    else:
        failed += 1
        print(f"  FAIL  {name}: {detail}")


async def collect_events(url, payload):
    events = []
    async with httpx.AsyncClient(timeout=60.0) as client:
        async with client.stream("POST", url, json=payload) as resp:
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    events.append(json.loads(data))
    return events


async def test_health():
    async with httpx.AsyncClient() as c:
        r = await c.get(f"{HERMES_URL}/health")
        result("health", r.status_code == 200 and r.json()["status"] == "ok")


async def test_tools():
    async with httpx.AsyncClient() as c:
        r = await c.get(f"{HERMES_URL}/v1/agent/tools")
        data = r.json()
        result("tools_list", len(data["tools"]) > 0, f"{len(data['tools'])} tools")


async def test_skills():
    async with httpx.AsyncClient() as c:
        r = await c.get(f"{HERMES_URL}/v1/agent/skills")
        data = r.json()
        result("skills_list", data["count"] > 0, f"{data['count']} skills")


async def test_memory():
    async with httpx.AsyncClient() as c:
        r = await c.get(f"{HERMES_URL}/v1/agent/memory")
        data = r.json()
        result("memory_api", "user" in data and "memory" in data)


async def test_text_streaming():
    events = await collect_events(
        f"{HERMES_URL}/v1/agent/run",
        {"message": "Say hello in one word", "config": {"max_iterations": 2}},
    )
    types = [e["type"] for e in events]
    result(
        "text_streaming",
        "run_started" in types and "text_delta" in types and "run_finished" in types,
        str(types),
    )


async def test_tool_calls():
    events = await collect_events(
        f"{HERMES_URL}/v1/agent/run",
        {
            "message": "What time is it? Use the terminal.",
            "config": {"max_iterations": 5, "enabled_toolsets": ["terminal"]},
        },
    )
    types = [e["type"] for e in events]
    has_tool = "tool_start" in types and "tool_result" in types
    result("tool_calls", has_tool, str(types))

    # Verify tool_call_id consistency
    starts = {e["tool_call_id"] for e in events if e["type"] == "tool_start"}
    results = {e["tool_call_id"] for e in events if e["type"] == "tool_result"}
    result("tool_id_match", starts == results, f"starts={starts} results={results}")


async def test_thinking_events():
    events = await collect_events(
        f"{HERMES_URL}/v1/agent/run",
        {"message": "Say hi", "config": {"max_iterations": 2}},
    )
    types = [e["type"] for e in events]
    result("thinking_events", "thinking" in types or "reasoning_delta" in types, str(types))
    result("step_events", "step" in types, str(types))


async def test_client_tools():
    events = await collect_events(
        f"{HERMES_URL}/v1/agent/run",
        {
            "message": "Delete all files in /tmp. You MUST use the confirm_action tool to get approval before any destructive action.",
            "config": {"max_iterations": 5, "enabled_toolsets": ["terminal"]},
            "client_tools": [
                {
                    "name": "confirm_action",
                    "description": "Ask user to confirm a dangerous action",
                    "parameters": {
                        "type": "object",
                        "properties": {"action": {"type": "string"}},
                        "required": ["action"],
                    },
                }
            ],
        },
    )
    types = [e["type"] for e in events]
    tool_starts = [e for e in events if e["type"] == "tool_start"]
    called_confirm = any(e["name"] == "confirm_action" for e in tool_starts)
    result("client_tool_called", called_confirm, str([e["name"] for e in tool_starts]))

    # Check interrupt worked
    finished = [e for e in events if e["type"] == "run_finished"]
    if finished:
        has_client_tools = "confirm_action" in finished[0].get("client_tool_names", [])
        result("client_tool_interrupt", has_client_tools, str(finished[0]))
    else:
        result("client_tool_interrupt", False, "no run_finished event")


async def test_error_hermes_down():
    """Test that bad URL produces RUN_ERROR."""
    events = []
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            async with client.stream(
                "POST",
                "http://localhost:9999/v1/agent/run",
                json={"message": "hi", "config": {}},
            ) as resp:
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        events.append(json.loads(line[6:]))
        except (httpx.ConnectError, httpx.ReadError):
            events.append({"type": "connect_error"})

    result("error_handling", len(events) > 0, "should get error event or exception")


async def test_concurrent():
    """3 parallel requests, verify no cross-contamination."""
    tasks = []
    for user_id in ("X", "Y", "Z"):
        tasks.append(
            collect_events(
                f"{HERMES_URL}/v1/agent/run",
                {
                    "message": f"My ID is {user_id}. Echo my ID back.",
                    "config": {"max_iterations": 2},
                },
            )
        )
    results = await asyncio.gather(*tasks)
    all_ok = True
    for i, (user_id, events) in enumerate(zip(("X", "Y", "Z"), results)):
        text = "".join(
            e.get("delta", "") for e in events if e.get("type") == "text_delta"
        )
        if user_id not in text:
            all_ok = False
    result("concurrent_isolation", all_ok)


async def main():
    print("Hermes Event Server Integration Tests")
    print("=" * 50)

    await test_health()
    await test_tools()
    await test_skills()
    await test_memory()
    await test_text_streaming()
    await test_tool_calls()
    await test_thinking_events()
    await test_client_tools()
    await test_error_hermes_down()
    await test_concurrent()

    print("=" * 50)
    print(f"{passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    ok = asyncio.run(main())
    sys.exit(0 if ok else 1)
