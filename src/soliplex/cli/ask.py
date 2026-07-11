from __future__ import annotations

import asyncio
import dataclasses
import json
import pathlib
import sys
import typing
import uuid

import typer
from ag_ui import core as agui_core
from pydantic_ai.ui import ag_ui as ai_ag_ui
from sqlalchemy.ext import asyncio as sqla_asyncio

from soliplex import agents
from soliplex import installation
from soliplex import loggers
from soliplex import models
from soliplex import util
from soliplex.agui import persistence as agui_persistence
from soliplex.agui import schema as agui_schema
from soliplex.cli import cli_util
from soliplex.cli import types

app = typer.Typer()


@dataclasses.dataclass
class _AskResult:
    thread_id: str
    ok: bool
    response: str | None = None
    usage: typing.Any = None
    error: str | None = None


def _fail(json_output: bool, message: str) -> typing.NoReturn:
    """Report a failure on stderr and exit non-zero.

    Keeps the success channel (stdout) clean for scripting: diagnostics go
    to stderr, either as a human line or a ``{"error": ...}`` object under
    ``--json``.
    """
    if json_output:
        print(json.dumps({"error": message}), file=sys.stderr)
    else:
        typer.echo(f"Error: {message}", err=True)
    raise typer.Exit(1)


def _check_room_id(the_installation, room_id, json_output):
    room_configs = the_installation._config.room_configs
    if room_id in room_configs:
        return

    configured = ", ".join(sorted(room_configs)) or "(none)"
    _fail(
        json_output,
        f"No room configured with id '{room_id}'. "
        f"Configured rooms: {configured}",
    )


def _usage_as_dict(usage) -> dict:
    if usage is None:
        return {}
    return {
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
    }


async def _create_thread_run(engine, *, user_name, email, room_id):
    """Create a persisted thread with its initial run; return their ids."""
    async with sqla_asyncio.AsyncSession(bind=engine) as session:
        async with session.begin():
            thread = await agui_persistence.ThreadStorage(session).new_thread(
                user_name=user_name,
                email=email,
                room_id=room_id,
                initial_run=True,
            )
            (run,) = await thread.list_runs()
            return thread.thread_id, run.run_id


async def _add_run_input(
    engine, *, user_name, room_id, thread_id, run_id, run_input
):
    async with sqla_asyncio.AsyncSession(bind=engine) as session:
        async with session.begin():
            await agui_persistence.ThreadStorage(session).add_run_input(
                user_name=user_name,
                room_id=room_id,
                thread_id=thread_id,
                run_id=run_id,
                run_input=run_input,
            )


async def _run_ask(the_installation, room_id, prompt, claims) -> _AskResult:
    """Run one room-agent turn over the AG-UI stream, auditing + persisting.

    Skips per-room ACL enforcement (a trusted CLI operator), but records the
    access and any RAG retrievals through the same audit log the web/MCP
    paths use, and persists the thread/run/events so a future turn can build
    on them.
    """
    user = models.UserProfile.from_user_claims(claims)
    user_name = claims["actor"]

    agent = await the_installation.get_agent_for_room(
        room_id=room_id,
        user=user,
    )
    room_config = await the_installation.get_room_config(
        room_id=room_id,
        user=user,
    )

    engine = installation._create_async_engine(
        the_installation.thread_persistence_dburi_async,
        json_serializer=util.serialize_sqla_json,
        pool_pre_ping=True,
    )
    try:
        async with engine.begin() as connection:
            await connection.run_sync(agui_schema.Base.metadata.create_all)

        thread_id, run_id = await _create_thread_run(
            engine,
            user_name=user_name,
            email="<unknown>",
            room_id=room_id,
        )

        audit = loggers.RoomAccessAuditLog(
            claims=claims,
            room_id=room_id,
            thread_id=thread_id,
            run_id=run_id,
        )
        # Record the access *before* the run begins, so an aborted or
        # crashed run still leaves a trace that the agent was invoked.
        audit.room_access_allowed(room_id)

        run_input = agui_core.RunAgentInput(
            thread_id=thread_id,
            run_id=run_id,
            state={},
            messages=[
                agui_core.UserMessage(
                    id=uuid.uuid4().hex,
                    role="user",
                    content=prompt,
                ),
            ],
            tools=(),
            context=(),
            forwarded_props=None,
        )
        await _add_run_input(
            engine,
            user_name=user_name,
            room_id=room_id,
            thread_id=thread_id,
            run_id=run_id,
            run_input=run_input,
        )

        deps = await the_installation.get_agent_deps_for_room(
            room_id=room_id,
            user=user,
            run_agent_input=run_input,
        )
        adapter = ai_ag_ui.AGUIAdapter(
            agent=agent,
            run_input=run_input,
            accept=None,
        )

        captured: dict = {}

        async def _on_complete(result):
            captured["usage"] = getattr(result, "usage", None)
            await agui_persistence.capture_usage_after_stream(
                result,
                sqla_engine=engine,
                user_name=user_name,
                room_id=room_id,
                thread_id=thread_id,
                run_id=run_id,
            )

        text_parts: list[str] = []
        last_event = None
        try:
            async for event in agui_persistence.drive_agui_turn(
                adapter=adapter,
                skill_toolset=agents.find_skill_toolset(agent),
                engine=engine,
                user_name=user_name,
                room_id=room_id,
                thread_id=thread_id,
                run_id=run_id,
                claims=claims,
                rag_db_paths=room_config.rag_db_paths,
                run_stream_kwargs=dict(
                    deps=deps,
                    conversation_id=thread_id,
                    on_complete=_on_complete,
                ),
            ):
                if event.type == agui_core.EventType.TEXT_MESSAGE_CONTENT:
                    text_parts.append(event.delta)
                last_event = event

            await agui_persistence.finish_run(
                engine,
                user_name=user_name,
                room_id=room_id,
                thread_id=thread_id,
                run_id=run_id,
            )
        except Exception as exc:
            audit.run_failed(str(exc))
            raise
    finally:
        await engine.dispose()

    if last_event is not None and (
        last_event.type == agui_core.EventType.RUN_FINISHED
    ):
        audit.run_finished()
        return _AskResult(
            thread_id=thread_id,
            ok=True,
            response="".join(text_parts),
            usage=captured.get("usage"),
        )

    if last_event is not None and (
        last_event.type == agui_core.EventType.RUN_ERROR
    ):
        reason = last_event.message
    else:
        reason = "the run produced no result"
    audit.run_failed(reason)
    return _AskResult(thread_id=thread_id, ok=False, error=reason)


@app.command("ask")
def ask(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
    room_id: str,
    prompt: str,
    json_output: bool = typer.Option(
        False,
        "--json",
        help=(
            "Emit a JSON object (room_id, thread_id, prompt, response, "
            "usage) instead of the plain-text response."
        ),
    ),
    cli_log_config: pathlib.Path | None = cli_util.CLI_LOG_CONFIG_OPTION,
):
    """Send a single prompt to a room's agent and print the response.

    Runs the room's agent in-process, skipping per-room ACL enforcement (a
    trusted operator), but records the access -- and any RAG retrievals --
    through the audit log (enable it with ``--cli-log-config``), and
    persists the thread/run so a follow-up turn can build on it. Exits 0 on
    success (response on stdout) and non-zero on failure (diagnostic on
    stderr), so the call can be scripted.
    """
    cli_util._configure_cli_logging(cli_log_config)

    the_installation = cli_util.get_installation(installation_path)

    _check_room_id(the_installation, room_id, json_output)

    claims = cli_util._audit_claims()

    try:
        the_installation.resolve_secrets()
        the_installation.resolve_environment()
        result = asyncio.run(
            _run_ask(the_installation, room_id, prompt, claims)
        )
    except Exception as exc:
        _fail(json_output, str(exc))

    if not result.ok:
        _fail(json_output, result.error)

    if json_output:
        print(
            json.dumps(
                {
                    "room_id": room_id,
                    "thread_id": result.thread_id,
                    "prompt": prompt,
                    "response": result.response,
                    "usage": _usage_as_dict(result.usage),
                }
            )
        )
    else:
        print(result.response)
