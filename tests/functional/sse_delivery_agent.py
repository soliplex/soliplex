"""Scripted agent for the SSE delivery functional tests.

The test sets 'SCRIPT' before starting a run.  The first model turn yields
'SCRIPT.deltas', waiting on 'SCRIPT.gate' before the delta at index
'SCRIPT.gate_before' and pausing 'SCRIPT.interval' seconds before each
delta.  If 'SCRIPT.hold' is an event, the turn then calls the 'hold' tool,
which keeps the run open until the event is set; a second turn yields
'SCRIPT.final_deltas'.
"""

import asyncio
import dataclasses

import pydantic_ai
from pydantic_ai import messages as ai_messages
from pydantic_ai.models import function as ai_function


@dataclasses.dataclass
class Script:
    deltas: list[str]
    interval: float = 0.0
    gate_before: int | None = None
    gate: asyncio.Event = dataclasses.field(default_factory=asyncio.Event)
    hold: asyncio.Event | None = None
    final_deltas: list[str] = dataclasses.field(default_factory=list)
    produced: list[tuple[float, str]] = dataclasses.field(
        default_factory=list,
    )

    @property
    def text(self):
        return "".join(self.deltas) + "".join(self.final_deltas)


SCRIPT = Script(deltas=["Hello", ", ", "world"])


def _after_tool_return(messages):
    return any(
        isinstance(part, ai_messages.ToolReturnPart)
        for message in messages
        for part in getattr(message, "parts", ())
    )


async def _stream(messages, info):
    loop = asyncio.get_running_loop()
    script = SCRIPT

    if _after_tool_return(messages):
        for delta in script.final_deltas:
            yield delta
        return

    for index, delta in enumerate(script.deltas):
        if index == script.gate_before:
            await script.gate.wait()
        if script.interval:
            await asyncio.sleep(script.interval)

        script.produced.append((loop.time(), delta))
        yield delta

    if script.hold is not None:
        yield {
            0: ai_function.DeltaToolCall(
                name="hold",
                json_args="{}",
                tool_call_id="call-hold",
            ),
        }


def agent_factory(
    tool_configs=None,
    mcp_client_toolset_configs=None,
    capability_config=None,
    **_,
):
    agent = pydantic_ai.Agent(
        ai_function.FunctionModel(stream_function=_stream),
    )

    @agent.tool_plain
    async def hold() -> str:
        await SCRIPT.hold.wait()
        return "released"

    return agent
