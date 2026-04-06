"""
Hermes Agent Backend for Soliplex

Calls the Hermes Event Server and translates its structured SSE events
into AG-UI events for the Flutter frontend.

Hermes events → AG-UI events mapping:
  run_started   → RunStartedEvent
  text_start    → TextMessageStartEvent
  text_delta    → TextMessageContentEvent
  text_end      → TextMessageEndEvent
  tool_start    → ToolCallStartEvent + ToolCallArgsEvent + ToolCallEndEvent
  tool_result   → ToolCallResultEvent
  thinking      → (skipped for now, M10)
  run_finished  → RunFinishedEvent
  run_error     → RunErrorEvent
"""

from __future__ import annotations

import json
import logging
import typing
import uuid

import httpx
from ag_ui import core as agui_core

from soliplex.config import agents as config_agents

logger = logging.getLogger(__name__)


async def stream_hermes_events(
    hermes_url: str,
    message: str,
    *,
    session_id: str | None = None,
    task_id: str | None = None,
    history: list[dict] | None = None,
    config: dict | None = None,
    client_tools: list[dict] | None = None,
) -> typing.AsyncIterator[dict]:
    """Call Hermes Event Server and yield parsed SSE events."""

    payload = {
        "message": message,
        "config": config or {},
    }
    if session_id:
        payload["session_id"] = session_id
    if task_id:
        payload["task_id"] = task_id
    if history:
        payload["history"] = history
    if client_tools:
        payload["client_tools"] = client_tools

    async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
        async with client.stream(
            "POST",
            f"{hermes_url}/v1/agent/run",
            json=payload,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        return
                    try:
                        yield json.loads(data)
                    except json.JSONDecodeError:
                        logger.warning("Bad SSE data: %s", data[:100])


async def hermes_to_agui_events(
    hermes_config: config_agents.HermesAgentConfig,
    message: str,
    *,
    thread_id: str,
    run_id: str,
    room_id: str | None = None,
    session_id: str | None = None,
    history: list[dict] | None = None,
    prior_state: dict | None = None,
    client_tools: list[dict] | None = None,
) -> typing.AsyncIterator[agui_core.Event]:
    """Stream from Hermes Event Server, yield AG-UI events."""

    config = {
        "max_iterations": hermes_config.hermes_max_iterations,
    }
    if hermes_config.hermes_model:
        config["model"] = hermes_config.hermes_model
    if hermes_config.hermes_toolsets is not None:
        config["enabled_toolsets"] = hermes_config.hermes_toolsets
    if hermes_config.hermes_disabled_toolsets:
        config["disabled_toolsets"] = hermes_config.hermes_disabled_toolsets
    if hermes_config.hermes_system_prompt:
        config["system_prompt"] = hermes_config.hermes_system_prompt

    # Deterministic session_id from thread
    if session_id is None:
        session_id = f"soliplex-{thread_id}"

    # Build running state from prior state
    state = dict(prior_state or {})
    state["hermes_session_id"] = session_id
    if "artifacts" not in state:
        state["artifacts"] = []

    yield agui_core.RunStartedEvent(
        type=agui_core.EventType.RUN_STARTED,
        thread_id=thread_id,
        run_id=run_id,
    )

    current_msg_id = None
    thinking_msg_id = None  # tracks open thinking block
    current_step_name = None  # tracks open step

    def _close_open_blocks():
        """Yield events to cleanly close any open AG-UI blocks."""
        nonlocal thinking_msg_id, current_msg_id, current_step_name
        events = []
        if thinking_msg_id is not None:
            events.append(agui_core.ThinkingTextMessageEndEvent(
                type=agui_core.EventType.THINKING_TEXT_MESSAGE_END,
                message_id=thinking_msg_id,
            ))
            thinking_msg_id = None
        if current_msg_id is not None:
            events.append(agui_core.TextMessageEndEvent(
                type=agui_core.EventType.TEXT_MESSAGE_END,
                message_id=current_msg_id,
            ))
            current_msg_id = None
        if current_step_name is not None:
            events.append(agui_core.StepFinishedEvent(
                type=agui_core.EventType.STEP_FINISHED,
                step_name=current_step_name,
            ))
            current_step_name = None
        return events

    try:
        async for event in stream_hermes_events(
            hermes_config.hermes_url,
            message,
            session_id=session_id,
            task_id=room_id,  # Daytona sandbox reused per room
            history=history,
            config=config,
            client_tools=client_tools,
        ):
            etype = event.get("type")

            # --- Thinking events ---
            if etype == "thinking":
                if thinking_msg_id is None:
                    thinking_msg_id = str(uuid.uuid4())
                    yield agui_core.ThinkingTextMessageStartEvent(
                        type=agui_core.EventType.THINKING_TEXT_MESSAGE_START,
                        message_id=thinking_msg_id,
                        role="assistant",
                    )
                yield agui_core.ThinkingTextMessageContentEvent(
                    type=agui_core.EventType.THINKING_TEXT_MESSAGE_CONTENT,
                    message_id=thinking_msg_id,
                    delta=event.get("content", ""),
                )
                continue

            elif etype == "thinking_end":
                if thinking_msg_id is not None:
                    yield agui_core.ThinkingTextMessageEndEvent(
                        type=agui_core.EventType.THINKING_TEXT_MESSAGE_END,
                        message_id=thinking_msg_id,
                    )
                    thinking_msg_id = None
                continue

            elif etype == "reasoning_delta":
                # Reasoning goes into thinking block
                if thinking_msg_id is None:
                    thinking_msg_id = str(uuid.uuid4())
                    yield agui_core.ThinkingTextMessageStartEvent(
                        type=agui_core.EventType.THINKING_TEXT_MESSAGE_START,
                        message_id=thinking_msg_id,
                        role="assistant",
                    )
                yield agui_core.ThinkingTextMessageContentEvent(
                    type=agui_core.EventType.THINKING_TEXT_MESSAGE_CONTENT,
                    message_id=thinking_msg_id,
                    delta=event.get("delta", ""),
                )
                continue

            elif etype == "step":
                # Close prior step if open
                if current_step_name is not None:
                    yield agui_core.StepFinishedEvent(
                        type=agui_core.EventType.STEP_FINISHED,
                        step_name=current_step_name,
                    )
                iteration = event.get("iteration", 1)
                max_iter = event.get("max_iterations", 10)
                current_step_name = f"Step {iteration}/{max_iter}"
                yield agui_core.StepStartedEvent(
                    type=agui_core.EventType.STEP_STARTED,
                    step_name=current_step_name,
                )
                continue

            # --- Close thinking before content events ---
            if thinking_msg_id is not None and etype in (
                "text_start", "text_delta", "tool_start",
            ):
                yield agui_core.ThinkingTextMessageEndEvent(
                    type=agui_core.EventType.THINKING_TEXT_MESSAGE_END,
                    message_id=thinking_msg_id,
                )
                thinking_msg_id = None

            if etype == "text_start":
                current_msg_id = str(uuid.uuid4())
                yield agui_core.TextMessageStartEvent(
                    type=agui_core.EventType.TEXT_MESSAGE_START,
                    message_id=current_msg_id,
                    role="assistant",
                )

            elif etype == "text_delta":
                if current_msg_id is None:
                    current_msg_id = str(uuid.uuid4())
                    yield agui_core.TextMessageStartEvent(
                        type=agui_core.EventType.TEXT_MESSAGE_START,
                        message_id=current_msg_id,
                        role="assistant",
                    )
                yield agui_core.TextMessageContentEvent(
                    type=agui_core.EventType.TEXT_MESSAGE_CONTENT,
                    message_id=current_msg_id,
                    delta=event.get("delta", ""),
                )

            elif etype == "text_end":
                if current_msg_id is not None:
                    yield agui_core.TextMessageEndEvent(
                        type=agui_core.EventType.TEXT_MESSAGE_END,
                        message_id=current_msg_id,
                    )
                    current_msg_id = None

            elif etype == "tool_start":
                # Close any open text segment
                if current_msg_id is not None:
                    yield agui_core.TextMessageEndEvent(
                        type=agui_core.EventType.TEXT_MESSAGE_END,
                        message_id=current_msg_id,
                    )
                    current_msg_id = None

                tc_id = event.get("tool_call_id", str(uuid.uuid4()))
                yield agui_core.ToolCallStartEvent(
                    type=agui_core.EventType.TOOL_CALL_START,
                    tool_call_id=tc_id,
                    tool_call_name=event.get("name", "unknown"),
                )
                # Emit args as single chunk
                args = event.get("args", {})
                if args:
                    yield agui_core.ToolCallArgsEvent(
                        type=agui_core.EventType.TOOL_CALL_ARGS,
                        tool_call_id=tc_id,
                        delta=json.dumps(args),
                    )
                yield agui_core.ToolCallEndEvent(
                    type=agui_core.EventType.TOOL_CALL_END,
                    tool_call_id=tc_id,
                )

            elif etype == "tool_result":
                tc_id = event.get("tool_call_id", str(uuid.uuid4()))
                tool_name = event.get("name", "")
                content = event.get("content", "")

                # Track file artifacts from write_file / terminal
                if tool_name in ("write_file", "patch_replace"):
                    try:
                        result_data = json.loads(content)
                        if isinstance(result_data, dict):
                            path = result_data.get("path")
                            if path and path not in state["artifacts"]:
                                state["artifacts"].append(path)
                    except (json.JSONDecodeError, TypeError):
                        pass

                yield agui_core.ToolCallResultEvent(
                    type=agui_core.EventType.TOOL_CALL_RESULT,
                    tool_call_id=tc_id,
                    message_id=str(uuid.uuid4()),
                    role="tool",
                    content=content,
                )

            elif etype == "run_finished":
                # Close any open thinking block
                if thinking_msg_id is not None:
                    yield agui_core.ThinkingTextMessageEndEvent(
                        type=agui_core.EventType.THINKING_TEXT_MESSAGE_END,
                        message_id=thinking_msg_id,
                    )
                    thinking_msg_id = None

                if current_msg_id is not None:
                    yield agui_core.TextMessageEndEvent(
                        type=agui_core.EventType.TEXT_MESSAGE_END,
                        message_id=current_msg_id,
                    )
                    current_msg_id = None

                # Close any open step
                if current_step_name is not None:
                    yield agui_core.StepFinishedEvent(
                        type=agui_core.EventType.STEP_FINISHED,
                        step_name=current_step_name,
                    )
                    current_step_name = None

                # Update state with run results
                usage = event.get("usage", {})
                hermes_session_id = event.get("session_id", session_id)
                state["hermes_session_id"] = hermes_session_id
                state["last_usage"] = usage
                state["run_count"] = state.get("run_count", 0) + 1

                # Emit STATE_SNAPSHOT so Flutter persists state
                yield agui_core.StateSnapshotEvent(
                    type=agui_core.EventType.STATE_SNAPSHOT,
                    snapshot=state,
                )

                yield agui_core.RunFinishedEvent(
                    type=agui_core.EventType.RUN_FINISHED,
                    thread_id=thread_id,
                    run_id=run_id,
                )
                return

            elif etype == "run_error":
                for _evt in _close_open_blocks():
                    yield _evt
                yield agui_core.RunErrorEvent(
                    type=agui_core.EventType.RUN_ERROR,
                    message=event.get("message", "Unknown error"),
                )
                return

            elif etype == "status":
                # Log but don't surface to AG-UI for now
                logger.info(
                    "Hermes status [%s]: %s",
                    event.get("status_type"),
                    event.get("message"),
                )

    except httpx.HTTPStatusError as exc:
        for _evt in _close_open_blocks():
            yield _evt
        yield agui_core.RunErrorEvent(
            type=agui_core.EventType.RUN_ERROR,
            message=f"Hermes server error: HTTP {exc.response.status_code}",
        )

    except httpx.TimeoutException:
        for _evt in _close_open_blocks():
            yield _evt
        yield agui_core.RunErrorEvent(
            type=agui_core.EventType.RUN_ERROR,
            message="Hermes agent timed out",
        )

    except (
        httpx.ConnectError,
        httpx.ReadError,
        httpx.RemoteProtocolError,
    ) as exc:
        for _evt in _close_open_blocks():
            yield _evt
        yield agui_core.RunErrorEvent(
            type=agui_core.EventType.RUN_ERROR,
            message=f"Cannot reach Hermes agent: {type(exc).__name__}",
        )

    except Exception as exc:
        logger.exception("Unexpected error in Hermes backend")
        for _evt in _close_open_blocks():
            yield _evt
        yield agui_core.RunErrorEvent(
            type=agui_core.EventType.RUN_ERROR,
            message=f"Unexpected error: {type(exc).__name__}: {exc}",
        )
