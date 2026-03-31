from __future__ import annotations

import asyncio
import functools

import fastapi
import logfire
import pydantic
import pydantic_ai
from ag_ui import core as agui_core
from fastapi import responses
from pydantic_ai.ui import ag_ui as ai_ag_ui
from sqlalchemy import exc as sqla_exc
from sqlalchemy.ext import asyncio as sqla_asyncio

from soliplex import agui as agui_package
from soliplex import authn
from soliplex import authz as authz_package
from soliplex import installation
from soliplex import loggers
from soliplex import models
from soliplex import util
from soliplex import views
from soliplex.agui import persistence as agui_persistence
from soliplex.config import agui as config_agui
from soliplex.config import rooms as config_rooms
from soliplex.views import streaming as streaming_views

router = fastapi.APIRouter(tags=["rooms"])

depend_the_installation = installation.depend_the_installation
depend_the_threads = agui_package.depend_the_threads
depend_the_authz = authz_package.depend_the_authz_policy
depend_the_user_claims = views.depend_the_user_claims
depend_the_logger = views.depend_the_logger


async def _check_user_in_room(
    *,
    room_id: str,
    the_installation: installation.Installation,
    the_authz_policy: authz_package.AuthorizationPolicy,
    the_user_claims: authn.UserClaims,
    the_logger: loggers.LogWrapper,
) -> config_rooms.RoomConfig:
    """Check that the user has access to the given room.

    If so, return the room configuration.

    If not, raise a 404.
    """
    try:
        room_config = await the_installation.get_room_config(
            room_id=room_id,
            user=the_user_claims,
            the_authz_policy=the_authz_policy,
            the_logger=the_logger,
        )
    except KeyError:
        # logged in 'get_room_config'
        raise fastapi.HTTPException(
            status_code=404,
            detail=f"No such room: {room_id}",
        ) from None

    return room_config


async def _check_user_room_agent(
    *,
    room_id: str,
    the_installation: installation.Installation,
    the_authz_policy: authz_package.AuthorizationPolicy,
    the_user_claims: authn.UserClaims,
    the_logger: loggers.LogWrapper,
) -> tuple[models.UserProfile, pydantic_ai.Agent]:
    """Check that the user has access to the given room.

    If so, return the user profile and the room's agent

    If not, raise a 404.
    """
    try:
        agent = await the_installation.get_agent_for_room(
            room_id=room_id,
            user=the_user_claims,
            the_authz_policy=the_authz_policy,
            the_logger=the_logger,
        )
    except KeyError:
        raise fastapi.HTTPException(
            status_code=404,
            detail=f"No such room: {room_id}",
        ) from None

    user_profile = models.UserProfile.from_user_claims(the_user_claims)
    return user_profile, agent


@util.logfire_span("GET /v1/rooms/{room_id}/agui")
@router.get("/v1/rooms/{room_id}/agui")
async def get_room_agui(
    request: fastapi.Request,
    room_id: str,
    the_installation: installation.Installation = depend_the_installation,
    the_threads: agui_package.ThreadStorage = depend_the_threads,
    the_authz_policy: authz_package.AuthorizationPolicy = depend_the_authz,
    the_user_claims: authn.UserClaims = depend_the_user_claims,
    the_logger: loggers.LogWrapper = depend_the_logger,
) -> models.AGUI_Threads:
    """Return user's extant AGUI threads within the given room"""
    the_logger.debug(loggers.AGUI_GET_ROOM)

    user_name = the_user_claims.get("preferred_username", "<unknown>")
    _room_config = await _check_user_in_room(
        room_id=room_id,
        the_installation=the_installation,
        the_authz_policy=the_authz_policy,
        the_user_claims=the_user_claims,
        the_logger=the_logger,
    )
    model_threads = []
    for a_thread in await the_threads.list_user_threads(
        user_name=user_name,
        room_id=room_id,
    ):
        thread_meta = await a_thread.awaitable_attrs.thread_metadata

        model_threads.append(
            models.AGUI_Thread.from_thread(
                a_thread,
                a_thread_meta=models.AGUI_ThreadMetadata.from_thread_meta(
                    thread_meta,
                ),
                a_thread_runs=None,
            )
        )

    return models.AGUI_Threads(threads=model_threads)


async def _get_run_input(
    run: agui_persistence.Run,
) -> agui_core.RunAgentInput | None:
    rai = await run.awaitable_attrs.run_agent_input
    return rai.to_agui_model() if rai is not None else None


@util.logfire_span("GET /v1/rooms/{room_id}/agui/{thread_id}")
@router.get("/v1/rooms/{room_id}/agui/{thread_id}")
async def get_room_agui_thread_id(
    request: fastapi.Request,
    room_id: str,
    thread_id: pydantic.UUID4,
    the_installation: installation.Installation = depend_the_installation,
    the_threads: agui_package.ThreadStorage = depend_the_threads,
    the_authz_policy: authz_package.AuthorizationPolicy = depend_the_authz,
    the_user_claims: authn.UserClaims = depend_the_user_claims,
    the_logger: loggers.LogWrapper = depend_the_logger,
) -> models.AGUI_Thread:
    """Return metadata about a specific thread and its runs"""
    thread_id = str(thread_id)
    the_logger.debug(loggers.AGUI_GET_ROOM_THREAD)

    user_name = the_user_claims.get("preferred_username", "<unknown>")
    _room_config = await _check_user_in_room(
        room_id=room_id,
        the_installation=the_installation,
        the_authz_policy=the_authz_policy,
        the_user_claims=the_user_claims,
        the_logger=the_logger,
    )
    try:
        thread = await the_threads.get_thread(
            user_name=user_name,
            room_id=room_id,
            thread_id=thread_id,
        )

    except agui_package.AGUI_Exception as exc:
        raise fastapi.HTTPException(
            status_code=exc.status_code,
            detail=exc.args,
        ) from None

    thread_meta = await thread.awaitable_attrs.thread_metadata

    a_thread_runs = {}

    for a_run in await thread.list_runs():
        await a_run.awaitable_attrs.thread
        a_thread_runs[a_run.run_id] = models.AGUI_Run.from_run(
            a_run=a_run,
            a_run_input=await _get_run_input(a_run),
            a_run_meta=await a_run.awaitable_attrs.run_metadata,
            a_run_events=None,
            a_run_usage=None,
        )

    return models.AGUI_Thread.from_thread(
        a_thread=thread,
        a_thread_meta=models.AGUI_ThreadMetadata.from_thread_meta(
            thread_meta,
        ),
        a_thread_runs=a_thread_runs,
    )


@util.logfire_span("GET /v1/rooms/{room_id}/agui/{thread_id}/{run_id}")
@router.get("/v1/rooms/{room_id}/agui/{thread_id}/{run_id}")
async def get_room_agui_thread_id_run_id(
    request: fastapi.Request,
    room_id: str,
    thread_id: pydantic.UUID4,
    run_id: pydantic.UUID4,
    the_installation: installation.Installation = depend_the_installation,
    the_threads: agui_package.ThreadStorage = depend_the_threads,
    the_authz_policy: authz_package.AuthorizationPolicy = depend_the_authz,
    the_user_claims: authn.UserClaims = depend_the_user_claims,
    the_logger: loggers.LogWrapper = depend_the_logger,
) -> models.AGUI_Run:
    """Return metadata about a specific run"""
    thread_id = str(thread_id)
    run_id = str(run_id)
    the_logger.debug(loggers.AGUI_GET_ROOM_THREAD_RUN)

    user_name = the_user_claims.get("preferred_username", "<unknown>")
    _room_config = await _check_user_in_room(
        room_id=room_id,
        the_installation=the_installation,
        the_authz_policy=the_authz_policy,
        the_user_claims=the_user_claims,
        the_logger=the_logger,
    )
    try:
        run = await the_threads.get_run(
            user_name=user_name,
            room_id=room_id,
            thread_id=thread_id,
            run_id=run_id,
        )

    except agui_package.AGUI_Exception as exc:
        raise fastapi.HTTPException(
            status_code=exc.status_code,
            detail=exc.args,
        ) from None

    await run.awaitable_attrs.thread
    usage = await run.awaitable_attrs.run_usage

    return models.AGUI_Run.from_run(
        a_run=run,
        a_run_input=await _get_run_input(run),
        a_run_meta=await run.awaitable_attrs.run_metadata,
        a_run_events=await run.list_events(),
        a_run_usage=usage.as_tuple() if usage else None,
    )


@util.logfire_span("POST /v1/rooms/{room_id}/agui")
@router.post("/v1/rooms/{room_id}/agui")
async def post_room_agui(
    request: fastapi.Request,
    room_id: str,
    new_thread_request: models.AGUI_NewThreadRequest,
    the_installation: installation.Installation = depend_the_installation,
    the_threads: agui_package.ThreadStorage = depend_the_threads,
    the_authz_policy: authz_package.AuthorizationPolicy = depend_the_authz,
    the_user_claims: authn.UserClaims = depend_the_user_claims,
    the_logger: loggers.LogWrapper = depend_the_logger,
) -> models.AGUI_Thread:
    """Create a new AGUI thread within the given room

    Add the initial AGUI run to the thread.

    Body of request, if passed, must validate to 'models.AGUI_ThreadMetadata'.
    """
    the_logger.debug(loggers.AGUI_POST_ROOM)

    user_name = the_user_claims.get("preferred_username", "<unknown>")
    email = the_user_claims.get("email", "<unknown>")
    room_config = await _check_user_in_room(
        room_id=room_id,
        the_installation=the_installation,
        the_authz_policy=the_authz_policy,
        the_user_claims=the_user_claims,
        the_logger=the_logger,
    )

    if new_thread_request.metadata is not None:
        t_metadata = new_thread_request.metadata.model_dump()
    else:
        t_metadata = None

    thread = await the_threads.new_thread(
        room_id=room_id,
        user_name=user_name,
        email=email,
        thread_metadata=t_metadata,
        initial_run=True,
    )

    run_map = {}

    (run,) = await thread.list_runs()
    await run.awaitable_attrs.thread
    run_meta = await run.awaitable_attrs.run_metadata

    # Synthesize a RunAgentInput with a default AG-UI state based on
    # the room's 'agui_feature_names'.
    # See: https://github.com/soliplex/soliplex/issues/586
    agui_state = {}

    for feature_name in room_config.agui_feature_names:
        feature_klass = config_agui.AGUI_FEATURES_BY_NAME[
            feature_name
        ].model_klass
        agui_state[feature_name] = feature_klass().model_dump(mode="python")

    run_input = agui_core.RunAgentInput(
        thread_id=thread.thread_id,
        run_id=run.run_id,
        state=agui_state,
        messages=(),
        tools=(),
        context=(),
        forwarded_props=None,
    )

    run_map[run.run_id] = models.AGUI_Run.from_run(
        a_run=run,
        a_run_input=run_input,
        a_run_meta=run_meta,
        a_run_events=[],
        a_run_usage=None,
    )

    return models.AGUI_Thread(
        room_id=room_id,
        thread_id=thread.thread_id,
        runs=run_map,
        created=thread.created,
        metadata=models.AGUI_ThreadMetadata.from_thread_meta(
            await thread.awaitable_attrs.thread_metadata,
        ),
    )


@util.logfire_span("POST /v1/rooms/{room_id}/agui/{thread_id}")
@router.post("/v1/rooms/{room_id}/agui/{thread_id}")
async def post_room_agui_thread_id(
    request: fastapi.Request,
    room_id: str,
    thread_id: pydantic.UUID4,
    new_run_request: models.AGUI_NewRunRequest,
    the_installation: installation.Installation = depend_the_installation,
    the_threads: agui_package.ThreadStorage = depend_the_threads,
    the_authz_policy: authz_package.AuthorizationPolicy = depend_the_authz,
    the_user_claims: authn.UserClaims = depend_the_user_claims,
    the_logger: loggers.LogWrapper = depend_the_logger,
) -> models.AGUI_Run:
    """Create a new AGUI run for a thread within the given room

    Body of request, if passed, must validate to 'models.AGUI_RunMetadata'.
    """
    thread_id = str(thread_id)
    the_logger.debug(loggers.AGUI_POST_ROOM_THREAD)

    user_name = the_user_claims.get("preferred_username", "<unknown>")
    _room_config = await _check_user_in_room(
        room_id=room_id,
        the_installation=the_installation,
        the_authz_policy=the_authz_policy,
        the_user_claims=the_user_claims,
        the_logger=the_logger,
    )

    parent_run_id = new_run_request.parent_run_id

    if new_run_request.metadata is not None:
        r_metadata = new_run_request.metadata.model_dump()
    else:
        r_metadata = None

    try:
        run = await the_threads.new_run(
            user_name=user_name,
            room_id=room_id,
            thread_id=thread_id,
            parent_run_id=parent_run_id,
            run_metadata=r_metadata,
        )

    except agui_package.AGUI_Exception as exc:
        raise fastapi.HTTPException(
            status_code=exc.status_code,
            detail=exc.args,
        ) from None

    # Wait for these for a new run because the are set only at commit time
    run_id = await run.awaitable_attrs.run_id
    created = await run.awaitable_attrs.created

    rai = await run.awaitable_attrs.run_agent_input

    return models.AGUI_Run(
        room_id=room_id,
        thread_id=thread_id,
        parent_run_id=parent_run_id,
        run_id=run_id,
        created=created,
        run_input=rai.to_agui_model() if rai is not None else None,
        events=[event.to_agui_model() for event in await run.list_events()],
        metadata=models.AGUI_RunMetadata.from_run_meta(
            a_run_meta=await run.awaitable_attrs.run_metadata,
        ),
    )


@util.logfire_span("POST /v1/rooms/{room_id}/agui/{thread_id}/meta")
@router.post("/v1/rooms/{room_id}/agui/{thread_id}/meta")
async def post_room_agui_thread_id_meta(
    request: fastapi.Request,
    room_id: str,
    thread_id: pydantic.UUID4,
    new_metadata: models.AGUI_ThreadMetadata,
    the_installation: installation.Installation = depend_the_installation,
    the_threads: agui_package.ThreadStorage = depend_the_threads,
    the_authz_policy: authz_package.AuthorizationPolicy = depend_the_authz,
    the_user_claims: authn.UserClaims = depend_the_user_claims,
    the_logger: loggers.LogWrapper = depend_the_logger,
) -> fastapi.Response:
    """Update metadata for a thread within the given room

    Body of request, if passed, must validate to 'models.AGUI_ThreadMetadata'.

    If an empty dict is passed, erase any existing metadata.

    Returns an HTTP 205 (Reset Content) on success.
    """
    thread_id = str(thread_id)
    the_logger.debug(loggers.AGUI_POST_ROOM_THREAD_META)

    user_name = the_user_claims.get("preferred_username", "<unknown>")
    _room_config = await _check_user_in_room(
        room_id=room_id,
        the_installation=the_installation,
        the_authz_policy=the_authz_policy,
        the_user_claims=the_user_claims,
        the_logger=the_logger,
    )

    new_md_dict = {
        key: value
        for key, value in new_metadata.model_dump().items()
        if value is not None
    }

    try:
        await the_threads.update_thread_metadata(
            user_name=user_name,
            room_id=room_id,
            thread_id=thread_id,
            thread_metadata=new_md_dict or None,
        )

    except agui_package.AGUI_Exception as exc:
        raise fastapi.HTTPException(
            status_code=exc.status_code,
            detail=exc.args,
        ) from None

    return fastapi.Response(status_code=205)


@util.logfire_span("DELETE /v1/rooms/{room_id}/agui/{thread_id}")
@router.delete("/v1/rooms/{room_id}/agui/{thread_id}")
async def delete_room_agui_thread_id(
    request: fastapi.Request,
    room_id: str,
    thread_id: pydantic.UUID4,
    the_installation: installation.Installation = depend_the_installation,
    the_threads: agui_package.ThreadStorage = depend_the_threads,
    the_authz_policy: authz_package.AuthorizationPolicy = depend_the_authz,
    the_user_claims: authn.UserClaims = depend_the_user_claims,
    the_logger: loggers.LogWrapper = depend_the_logger,
) -> fastapi.Response:
    """Delete an AGUI thread within the given room"""
    thread_id = str(thread_id)
    the_logger.debug(loggers.AGUI_DELETE_ROOM_THREAD)

    user_name = the_user_claims.get("preferred_username", "<unknown>")
    _room_config = await _check_user_in_room(
        room_id=room_id,
        the_installation=the_installation,
        the_authz_policy=the_authz_policy,
        the_user_claims=the_user_claims,
        the_logger=the_logger,
    )
    try:
        await the_threads.delete_thread(
            user_name=user_name,
            room_id=room_id,
            thread_id=thread_id,
        )

    except agui_package.AGUI_Exception as exc:
        raise fastapi.HTTPException(
            status_code=exc.status_code,
            detail=exc.args,
        ) from None

    return fastapi.Response(
        status_code=204,
    )


async def capture_usage_after_stream(
    result,
    *,
    sqla_engine,
    user_name: str,
    room_id: str,
    thread_id: str,
    run_id: str,
):
    """Save the run usage to the database.

    This function needs to build its own session, because the one bound
    to the request lifetime in the `the_threads` dependency might have
    been closed (e.g., with an early connection reset).
    """
    usage = getattr(result, "usage", None)

    if usage is not None:
        async with sqla_asyncio.AsyncSession(bind=sqla_engine) as session:
            the_threads = agui_persistence.ThreadStorage(session)

            usage = usage()
            await the_threads.save_run_usage(
                user_name=user_name,
                room_id=room_id,
                thread_id=thread_id,
                run_id=run_id,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                requests=usage.requests,
                tool_calls=usage.tool_calls,
            )


async def save_thread_run_events(
    sqla_engine,
    event_list,
    user_name: str,
    room_id: str,
    thread_id: str,
    run_id: str,
):
    """Save the run events to the database.

    This function needs to build its own session, because the one bound
    to the request lifetime in the `the_threads` dependency might have
    been closed (e.g., with an early connection reset).
    """
    async with sqla_asyncio.AsyncSession(bind=sqla_engine) as session:
        the_threads = agui_persistence.ThreadStorage(session)

        await the_threads.save_run_events(
            events=event_list,
            user_name=user_name,
            room_id=room_id,
            thread_id=thread_id,
            run_id=run_id,
        )


async def drive_llm_stream(
    llm_stream,
    sqla_engine,
    event_queue: asyncio.Queue,
    user_name: str,
    room_id: str,
    thread_id: str,
    run_id: str,
):
    """Primary consumer of LLM event stream

    Always runs to completion.
    """
    with logfire.span(
        "AG-UI event stream: {room_id}/{thread_id}/{run_id}",
        room_id=room_id,
        thread_id=thread_id,
        run_id=run_id,
    ):
        event_list = []
        error_message = None
        status = None
        try:
            async for event in llm_stream:
                event_list.append(event)
                await event_queue.put(event)
        finally:
            await event_queue.put(None)  # sentinel

            try:
                await save_thread_run_events(
                    event_list=event_list,
                    sqla_engine=sqla_engine,
                    user_name=user_name,
                    room_id=room_id,
                    thread_id=thread_id,
                    run_id=run_id,
                )
            except sqla_exc.SQLAlchemyError as sa_exc:
                logfire.error(
                    "Error saving run events: {error_message}",
                    error_message=str(sa_exc),
                )
                raise

            if event_list:
                last = event_list[-1]

                if last.type == agui_core.EventType.RUN_FINISHED:
                    status = "FINISHED"

                elif last.type == agui_core.EventType.RUN_ERROR:
                    status = "ERROR"
                    error_message = last.message

                else:
                    status = "UNKNOWN"
            else:
                status = "EMPTY"

            if error_message:
                logfire.error(
                    "Stream error: {error_message}",
                    error_message=error_message,
                )
            else:
                logfire.info("Stream status: {status}", status=status)


async def stream_llm_events(event_queue: asyncio.Queue):
    """Read/yield events from queue

    Stop if client disconnects.
    """
    while True:
        event = await event_queue.get()
        if event is None:
            break
        yield event


@util.logfire_span("POST /v1/rooms/{room_id}/agui/{thread_id}/{run_id}")
@router.post("/v1/rooms/{room_id}/agui/{thread_id}/{run_id}")
async def post_room_agui_thread_id_run_id(
    request: fastapi.Request,
    room_id: str,
    thread_id: pydantic.UUID4,
    run_id: pydantic.UUID4,
    the_installation: installation.Installation = depend_the_installation,
    the_threads: agui_package.ThreadStorage = depend_the_threads,
    the_authz_policy: authz_package.AuthorizationPolicy = depend_the_authz,
    the_user_claims: authn.UserClaims = depend_the_user_claims,
    the_logger: loggers.LogWrapper = depend_the_logger,
) -> responses.StreamingResponse:
    """Execute an AGUI run

    Stream AGUI events in the response.
    """
    thread_id = str(thread_id)
    run_id = str(run_id)
    the_logger.debug(loggers.AGUI_POST_ROOM_THREAD_RUN)

    user_name = the_user_claims.get("preferred_username", "<unknown>")
    user, agent = await _check_user_room_agent(
        room_id=room_id,
        the_installation=the_installation,
        the_authz_policy=the_authz_policy,
        the_user_claims=the_user_claims,
        the_logger=the_logger,
    )

    agui_adapter = await ai_ag_ui.AGUIAdapter.from_request(
        request=request,
        agent=agent,
    )

    try:
        await the_threads.add_run_input(
            user_name=user_name,
            room_id=room_id,
            thread_id=thread_id,
            run_id=run_id,
            run_input=agui_adapter.run_input,
        )

    except agui_package.AGUI_Exception as exc:
        raise fastapi.HTTPException(
            status_code=exc.status_code,
            detail=exc.args,
        ) from None

    agent_deps = await the_installation.get_agent_deps_for_room(
        room_id=room_id,
        user=user,
        run_agent_input=agui_adapter.run_input,
        the_threads=the_threads,
        the_logger=the_logger,
    )

    agent_stream = agui_adapter.run_stream(
        deps=agent_deps,
        on_complete=functools.partial(
            capture_usage_after_stream,
            sqla_engine=request.state.threads_engine,
            user_name=user_name,
            room_id=room_id,
            thread_id=thread_id,
            run_id=run_id,
        ),
    )

    compacted_stream = agui_package.compact_event_stream(agent_stream)

    # We use an unbounded queue here, so that the 'drive_llm_stream'
    # task completes even when the SSE stream gets cancelled due to a
    # client disconnect, thereby permitting the client to see the
    # completed run after reconnecting.
    event_queue = asyncio.Queue()

    # Drive the LLM stream in a background task, in order to save
    # the thread persistence and usage at the end.
    bg_tasks = request.app.state.agui_background_tasks
    task = asyncio.create_task(
        # No 'await' here:  'create_task' *wants* a coroutine
        drive_llm_stream(
            llm_stream=compacted_stream,
            sqla_engine=request.state.threads_engine,
            event_queue=event_queue,
            user_name=user_name,
            room_id=room_id,
            thread_id=thread_id,
            run_id=run_id,
        )
    )
    bg_tasks.add(task)
    task.add_done_callback(bg_tasks.discard)

    # Stream events to the client from the queue, as pushed from
    # the driver.
    sse_stream = agui_adapter.encode_stream(
        stream_llm_events(event_queue),
    )

    # Wrap the response stream w/ keepalives, cancellation detection
    w_keepalive_stream = streaming_views.stream_sse_with_keepalive(
        sse_stream,
        request=request,
        log_info=logfire.info,
    )

    return responses.StreamingResponse(
        w_keepalive_stream,
        media_type=agui_adapter.accept,
        headers=streaming_views.HEADERS_DO_NOT_BUFFER_SSE,
    )


@util.logfire_span("POST /v1/rooms/{room_id}/agui/{thread_id}/{run_id}/meta")
@router.post("/v1/rooms/{room_id}/agui/{thread_id}/{run_id}/meta")
async def post_room_agui_thread_id_run_id_meta(
    request: fastapi.Request,
    room_id: str,
    thread_id: pydantic.UUID4,
    run_id: pydantic.UUID4,
    new_metadata: models.AGUI_RunMetadata,
    the_installation: installation.Installation = depend_the_installation,
    the_threads: agui_package.ThreadStorage = depend_the_threads,
    the_authz_policy: authz_package.AuthorizationPolicy = depend_the_authz,
    the_user_claims: authn.UserClaims = depend_the_user_claims,
    the_logger: loggers.LogWrapper = depend_the_logger,
) -> fastapi.Response:
    """Update metadata for a thread within the given room

    Body of request, if passed, must validate to 'models.AGUI_ThreadMetadata'.

    If an empty dict is passed, erase any existing metadata.

    Returns an HTTP 205 (Reset Content) on success.
    """
    thread_id = str(thread_id)
    run_id = str(run_id)
    the_logger.debug(loggers.AGUI_POST_ROOM_THREAD_RUN_META)

    user_name = the_user_claims.get("preferred_username", "<unknown>")
    _room_config = await _check_user_in_room(
        room_id=room_id,
        the_installation=the_installation,
        the_authz_policy=the_authz_policy,
        the_user_claims=the_user_claims,
        the_logger=the_logger,
    )

    new_md_dict = {
        key: value
        for key, value in new_metadata.model_dump().items()
        if value is not None
    }

    try:
        await the_threads.update_run_metadata(
            user_name=user_name,
            room_id=room_id,
            thread_id=thread_id,
            run_id=run_id,
            run_metadata=new_md_dict,
        )

    except agui_package.AGUI_Exception as exc:
        raise fastapi.HTTPException(
            status_code=exc.status_code,
            detail=exc.args,
        ) from None

    return fastapi.Response(status_code=205)


@util.logfire_span(
    "GET /v1/rooms/{room_id}/agui/{thread_id}/{run_id}/feedback"
)
@router.get("/v1/rooms/{room_id}/agui/{thread_id}/{run_id}/feedback")
async def get_room_agui_thread_id_run_id_feedback(
    request: fastapi.Request,
    room_id: str,
    thread_id: pydantic.UUID4,
    run_id: pydantic.UUID4,
    the_installation: installation.Installation = depend_the_installation,
    the_threads: agui_package.ThreadStorage = depend_the_threads,
    the_authz_policy: authz_package.AuthorizationPolicy = depend_the_authz,
    the_user_claims: authn.UserClaims = depend_the_user_claims,
    the_logger: loggers.LogWrapper = depend_the_logger,
) -> models.AGUI_RunFeedback | None:
    """Retrieve feedback for a run"""
    thread_id = str(thread_id)
    run_id = str(run_id)
    the_logger.debug(loggers.AGUI_GET_ROOM_THREAD_RUN_FEEDBACK)

    user_name = the_user_claims.get("preferred_username", "<unknown>")
    _room_config = await _check_user_in_room(
        room_id=room_id,
        the_installation=the_installation,
        the_authz_policy=the_authz_policy,
        the_user_claims=the_user_claims,
        the_logger=the_logger,
    )

    try:
        run_feedback = await the_threads.get_run_feedback(
            user_name=user_name,
            room_id=room_id,
            thread_id=thread_id,
            run_id=run_id,
        )

    except agui_package.AGUI_Exception as exc:
        raise fastapi.HTTPException(
            status_code=exc.status_code,
            detail=exc.args,
        ) from None

    return models.AGUI_RunFeedback(
        feedback=run_feedback.feedback,
        reason=run_feedback.reason,
    )


@util.logfire_span(
    "POST /v1/rooms/{room_id}/agui/{thread_id}/{run_id}/feedback"
)
@router.post("/v1/rooms/{room_id}/agui/{thread_id}/{run_id}/feedback")
async def post_room_agui_thread_id_run_id_feedback(
    request: fastapi.Request,
    room_id: str,
    thread_id: pydantic.UUID4,
    run_id: pydantic.UUID4,
    new_feedback: models.AGUI_RunFeedback,
    the_installation: installation.Installation = depend_the_installation,
    the_threads: agui_package.ThreadStorage = depend_the_threads,
    the_authz_policy: authz_package.AuthorizationPolicy = depend_the_authz,
    the_user_claims: authn.UserClaims = depend_the_user_claims,
    the_logger: loggers.LogWrapper = depend_the_logger,
) -> fastapi.Response:
    """Add / update feedback for a run

    Return an HTTP 205 (Reset Content) on success.
    """
    thread_id = str(thread_id)
    run_id = str(run_id)
    the_logger.debug(loggers.AGUI_POST_ROOM_THREAD_RUN_FEEDBACK)

    user_name = the_user_claims.get("preferred_username", "<unknown>")
    _room_config = await _check_user_in_room(
        room_id=room_id,
        the_installation=the_installation,
        the_authz_policy=the_authz_policy,
        the_user_claims=the_user_claims,
        the_logger=the_logger,
    )

    try:
        await the_threads.save_run_feedback(
            user_name=user_name,
            room_id=room_id,
            thread_id=thread_id,
            run_id=run_id,
            feedback=new_feedback.feedback,
            reason=new_feedback.reason,
        )

    except agui_package.AGUI_Exception as exc:
        raise fastapi.HTTPException(
            status_code=exc.status_code,
            detail=exc.args,
        ) from None

    return fastapi.Response(status_code=205)


@util.logfire_span("POST /v1/agui/feedback")
@router.post("/v1/agui/feedback")
async def post_agui_recent_feedback(
    request: fastapi.Request,
    query_terms: models.AGUI_FeedbackQueryTerms,
    the_installation: installation.Installation = depend_the_installation,
    the_threads: agui_package.ThreadStorage = depend_the_threads,
    the_authz_policy: authz_package.AuthorizationPolicy = depend_the_authz,
    the_user_claims: authn.UserClaims = depend_the_user_claims,
    the_logger: loggers.LogWrapper = depend_the_logger,
) -> list[models.AGUI_RunFeedback]:
    """Retrieve recent feedback for runs"""
    the_logger.debug(loggers.AGUI_POST_RECENT_FEEDBACK)

    recent_feedback = await the_threads.list_recent_run_feedback(
        **query_terms.as_dict,
    )

    return [
        models.AGUI_RunFeedback(
            feedback=run_feedback.feedback,
            reason=run_feedback.reason,
        )
        for run_feedback in recent_feedback
    ]


@util.logfire_span("POST /v1/agui/feedback/rooms/{room_id}")
@router.post("/v1/agui/feedback/rooms/{room_id}")
async def post_agui_recent_room_feedback(
    request: fastapi.Request,
    room_id: str,
    query_terms: models.AGUI_FeedbackQueryTerms,
    the_installation: installation.Installation = depend_the_installation,
    the_threads: agui_package.ThreadStorage = depend_the_threads,
    the_authz_policy: authz_package.AuthorizationPolicy = depend_the_authz,
    the_user_claims: authn.UserClaims = depend_the_user_claims,
    the_logger: loggers.LogWrapper = depend_the_logger,
) -> list[models.AGUI_RunFeedback]:
    """Retrieve recent feedback for runs in a room"""
    the_logger.debug(loggers.AGUI_POST_RECENT_ROOM_FEEDBACK)

    recent_feedback = await the_threads.list_recent_run_feedback(
        room_id=room_id,
        **query_terms.as_dict,
    )

    return [
        models.AGUI_RunFeedback(
            feedback=run_feedback.feedback,
            reason=run_feedback.reason,
        )
        for run_feedback in recent_feedback
    ]


@util.logfire_span("POST /v1/agui/feedback/user/{user_name}")
@router.post("/v1/agui/feedback/user/{user_name}")
async def post_agui_recent_user_feedback(
    request: fastapi.Request,
    user_name: str,
    query_terms: models.AGUI_FeedbackQueryTerms,
    the_installation: installation.Installation = depend_the_installation,
    the_threads: agui_package.ThreadStorage = depend_the_threads,
    the_authz_policy: authz_package.AuthorizationPolicy = depend_the_authz,
    the_user_claims: authn.UserClaims = depend_the_user_claims,
    the_logger: loggers.LogWrapper = depend_the_logger,
) -> list[models.AGUI_RunFeedback]:
    """Retrieve recent feedback for runs made by a user"""
    the_logger.debug(loggers.AGUI_POST_RECENT_USER_FEEDBACK)

    recent_feedback = await the_threads.list_recent_run_feedback(
        user_name=user_name,
        **query_terms.as_dict,
    )

    return [
        models.AGUI_RunFeedback(
            feedback=run_feedback.feedback,
            reason=run_feedback.reason,
        )
        for run_feedback in recent_feedback
    ]


@util.logfire_span("POST /v1/agui/feedback/review")
@router.post("/v1/agui/feedback/review")
async def post_agui_review_recent_feedback(
    request: fastapi.Request,
    review: models.AGUI_RunFeedbackReview,
    the_installation: installation.Installation = depend_the_installation,
    the_threads: agui_package.ThreadStorage = depend_the_threads,
    the_authz_policy: authz_package.AuthorizationPolicy = depend_the_authz,
    the_user_claims: authn.UserClaims = depend_the_user_claims,
    the_logger: loggers.LogWrapper = depend_the_logger,
) -> models.AGUI_RunFeedbackHistoryEntry:
    """Retrieve recent feedback for runs"""
    the_logger.debug(loggers.AGUI_POST_REVIEW_RECENT_FEEDBACK)

    review_entry = await the_threads.review_run_feedback(
        user_name=review.user_name,
        room_id=review.room_id,
        thread_id=str(review.thread_id),
        run_id=str(review.run_id),
        note=review.note,
    )

    return models.AGUI_RunFeedbackHistoryEntry(
        status=review_entry.status,
        note=review_entry.note,
    )


@util.logfire_span("POST /v1/agui/feedback/resolve")
@router.post("/v1/agui/feedback/resolve")
async def post_agui_resolve_recent_feedback(
    request: fastapi.Request,
    resolution: models.AGUI_RunFeedbackReview,
    the_installation: installation.Installation = depend_the_installation,
    the_threads: agui_package.ThreadStorage = depend_the_threads,
    the_authz_policy: authz_package.AuthorizationPolicy = depend_the_authz,
    the_user_claims: authn.UserClaims = depend_the_user_claims,
    the_logger: loggers.LogWrapper = depend_the_logger,
) -> models.AGUI_RunFeedbackHistoryEntry:
    """Retrieve recent feedback for runs"""
    the_logger.debug(loggers.AGUI_POST_RESOLVE_RECENT_FEEDBACK)

    resolution_entry = await the_threads.resolve_run_feedback(
        user_name=resolution.user_name,
        room_id=resolution.room_id,
        thread_id=str(resolution.thread_id),
        run_id=str(resolution.run_id),
        note=resolution.note,
    )

    return models.AGUI_RunFeedbackHistoryEntry(
        status=resolution_entry.status,
        note=resolution_entry.note,
    )
