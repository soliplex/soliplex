from __future__ import annotations

import functools

import fastapi
import pydantic_ai
from ag_ui import core as agui_core
from fastapi import responses
from fastapi import security
from pydantic_ai.ui import ag_ui as ai_ag_ui

from soliplex import agui as agui_package
from soliplex import auth
from soliplex import installation
from soliplex import models
from soliplex import util
from soliplex.agui import mpx as agui_mpx
from soliplex.agui import parser as agui_parser
from soliplex.agui import persistence as agui_persistence

router = fastapi.APIRouter(tags=["rooms"])

depend_the_installation = installation.depend_the_installation
depend_the_threads = agui_package.depend_the_threads


async def _check_user_in_room(
    *,
    room_id: str,
    the_installation: installation.Installation = depend_the_installation,
    token: security.HTTPAuthorizationCredentials = auth.oauth2_predicate,
) -> str:
    """Check that the token's user has access to the given room.

    If so, return the user's preferred username.

    If not, raise a 404.
    """
    user = auth.authenticate(the_installation, token)

    try:
        the_installation.get_room_config(room_id, user)
    except KeyError:
        raise fastapi.HTTPException(
            status_code=404,
            detail=f"No such room: {room_id}",
        ) from None

    return user.get("preferred_username", "<unknown>")


async def _check_user_room_agent(
    *,
    room_id: str,
    the_installation: installation.Installation = depend_the_installation,
    token: security.HTTPAuthorizationCredentials = auth.oauth2_predicate,
) -> tuple[str, models.UserProfile, pydantic_ai.Agent]:
    """Check that the token's user has access to the given room.

    If so, return the user name, user profile and the room's agent

    If not, raise a 404.
    """
    user = auth.authenticate(the_installation, token)
    user_name = user.get("preferred_username", "<unknown>")
    user_profile = models.UserProfile(
        given_name=user.get("given_name", "<unknown>"),
        family_name=user.get("family_name", "<unknown>"),
        email=user.get("email", "<unknown>"),
        preferred_username=user.get("preferred_username", "<unknown>"),
    )
    try:
        agent = the_installation.get_agent_for_room(room_id, user)
    except KeyError:
        raise fastapi.HTTPException(
            status_code=404,
            detail=f"No such room: {room_id}",
        ) from None

    return user_name, user_profile, agent


@util.logfire_span("GET /v1/rooms/{room_id}/agui")
@router.get("/v1/rooms/{room_id}/agui")
async def get_room_agui(
    request: fastapi.Request,
    room_id: str,
    the_installation: installation.Installation = depend_the_installation,
    the_threads: agui_package.ThreadStorage = depend_the_threads,
    token: security.HTTPAuthorizationCredentials = auth.oauth2_predicate,
) -> models.AGUI_Threads:
    """Return user's extant AGUI threads within the given room"""
    user_name = await _check_user_in_room(
        room_id=room_id,
        the_installation=the_installation,
        token=token,
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
    thread_id: str,
    the_installation: installation.Installation = depend_the_installation,
    the_threads: agui_package.ThreadStorage = depend_the_threads,
    token: security.HTTPAuthorizationCredentials = auth.oauth2_predicate,
) -> models.AGUI_Thread:
    """Return metadata about a specific thread and its runs"""
    user_name = await _check_user_in_room(
        room_id=room_id,
        the_installation=the_installation,
        token=token,
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
    thread_id: str,
    run_id: str,
    the_installation: installation.Installation = depend_the_installation,
    the_threads: agui_package.ThreadStorage = depend_the_threads,
    token: security.HTTPAuthorizationCredentials = auth.oauth2_predicate,
) -> models.AGUI_Run:
    """Return metadata about a specific run"""
    user_name = await _check_user_in_room(
        room_id=room_id,
        the_installation=the_installation,
        token=token,
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

    return models.AGUI_Run.from_run(
        a_run=run,
        a_run_input=await _get_run_input(run),
        a_run_meta=await run.awaitable_attrs.run_metadata,
        a_run_events=await run.list_events(),
    )


@util.logfire_span("POST /v1/rooms/{room_id}/agui")
@router.post("/v1/rooms/{room_id}/agui")
async def post_room_agui(
    request: fastapi.Request,
    room_id: str,
    new_thread_request: models.AGUI_NewThreadRequest,
    the_installation: installation.Installation = depend_the_installation,
    the_threads: agui_package.ThreadStorage = depend_the_threads,
    token: security.HTTPAuthorizationCredentials = auth.oauth2_predicate,
) -> models.AGUI_Thread:
    """Create a new AGUI thread within the given room

    Add the initial AGUI run to the thread.

    Body of request, if passed, must validate to 'models.AGUI_ThreadMetadata'.
    """
    user_name = await _check_user_in_room(
        room_id=room_id,
        the_installation=the_installation,
        token=token,
    )

    if new_thread_request.metadata is not None:
        t_metadata = new_thread_request.metadata.model_dump()
    else:
        t_metadata = None

    thread = await the_threads.new_thread(
        room_id=room_id,
        user_name=user_name,
        thread_metadata=t_metadata,
        initial_run=True,
    )

    run_map = {}

    for run in await thread.list_runs():
        await run.awaitable_attrs.thread
        run_meta = await run.awaitable_attrs.run_metadata
        run_map[run.run_id] = models.AGUI_Run.from_run(
            a_run=run,
            a_run_input=await _get_run_input(run),
            a_run_meta=run_meta,
            a_run_events=[],
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
    thread_id: str,
    new_run_request: models.AGUI_NewRunRequest,
    the_installation: installation.Installation = depend_the_installation,
    the_threads: agui_package.ThreadStorage = depend_the_threads,
    token: security.HTTPAuthorizationCredentials = auth.oauth2_predicate,
) -> models.AGUI_Run:
    """Create a new AGUI run for a thread within the given room

    Body of request, if passed, must validate to 'models.AGUI_RunMetadata'.
    """
    user_name = await _check_user_in_room(
        room_id=room_id,
        the_installation=the_installation,
        token=token,
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
    thread_id: str,
    new_metadata: models.AGUI_ThreadMetadata,
    the_installation: installation.Installation = depend_the_installation,
    the_threads: agui_package.ThreadStorage = depend_the_threads,
    token: security.HTTPAuthorizationCredentials = auth.oauth2_predicate,
) -> fastapi.Response:
    """Update metadata for a thread within the given room

    Body of request, if passed, must validate to 'models.AGUI_ThreadMetadata'.

    If an empty dict is passed, erase any existing metadata.

    Returns an HTTP 205 (Reset Content) on success.
    """
    user_name = await _check_user_in_room(
        room_id=room_id,
        the_installation=the_installation,
        token=token,
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
            thread_metadata=new_md_dict,
        )

    except agui_package.AGUI_Exception as exc:
        raise fastapi.HTTPException(
            status_code=exc.status_code,
            detail=exc.args,
        ) from None

    return fastapi.Response(status_code=205)


async def tee_events(
    event_stream: agui_package.AGUI_EventStream,
    event_list: agui_package.AGUI_Events,
    on_done,
):
    async for event in event_stream:
        event_list.append(event)
        yield event

    await on_done(events=event_list)


@util.logfire_span("POST /v1/rooms/{room_id}/agui/{thread_id}/{run_id}")
@router.post("/v1/rooms/{room_id}/agui/{thread_id}/{run_id}")
async def post_room_agui_thread_id_run_id(
    request: fastapi.Request,
    room_id: str,
    thread_id: str,
    run_id: str,
    the_installation: installation.Installation = depend_the_installation,
    the_threads: agui_package.ThreadStorage = depend_the_threads,
    token: security.HTTPAuthorizationCredentials = auth.oauth2_predicate,
) -> responses.StreamingResponse:
    """Execute an AGUI run

    Stream AGUI events in the response.
    """
    user_name, user, agent = await _check_user_room_agent(
        room_id=room_id,
        the_installation=the_installation,
        token=token,
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

    agent_deps = the_installation.get_agent_deps_for_room(
        room_id,
        user=user,
        run_agent_input=agui_adapter.run_input,
    )

    emitter = agent_deps.agui_emitter

    events = []

    async def finish_stream(_result):
        await emitter.close()

    mpx = agui_mpx.multiplex_streams(
        agui_adapter.run_stream(deps=agent_deps, on_complete=finish_stream),
        agui_parser.agui_events_from_dicts(emitter),
    )

    save_events = functools.partial(
        the_threads.save_run_events,
        user_name=user_name,
        room_id=room_id,
        thread_id=thread_id,
        run_id=run_id,
    )

    db_stream = tee_events(
        mpx,
        events,
        on_done=save_events,
    )

    sse_stream = agui_adapter.encode_stream(db_stream)

    return responses.StreamingResponse(
        sse_stream,
        media_type=agui_adapter.accept,
    )


@util.logfire_span("POST /v1/rooms/{room_id}/agui/{thread_id}/{run_id}/meta")
@router.post("/v1/rooms/{room_id}/agui/{thread_id}/{run_id}/meta")
async def post_room_agui_thread_id_run_id_meta(
    request: fastapi.Request,
    room_id: str,
    thread_id: str,
    run_id: str,
    new_metadata: models.AGUI_RunMetadata,
    the_installation: installation.Installation = depend_the_installation,
    the_threads: agui_package.ThreadStorage = depend_the_threads,
    token: security.HTTPAuthorizationCredentials = auth.oauth2_predicate,
) -> fastapi.Response:
    """Update metadata for a thread within the given room

    Body of request, if passed, must validate to 'models.AGUI_ThreadMetadata'.

    If an empty dict is passed, erase any existing metadata.

    Returns an HTTP 205 (Reset Content) on success.
    """
    user_name = await _check_user_in_room(
        room_id=room_id,
        the_installation=the_installation,
        token=token,
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


@util.logfire_span("DELETE /v1/rooms/{room_id}/agui/{thread_id}")
@router.delete("/v1/rooms/{room_id}/agui/{thread_id}")
async def delete_room_agui_thread_id(
    request: fastapi.Request,
    room_id: str,
    thread_id: str,
    the_installation: installation.Installation = depend_the_installation,
    the_threads: agui_package.ThreadStorage = depend_the_threads,
    token: security.HTTPAuthorizationCredentials = auth.oauth2_predicate,
) -> models.AGUI_Run:
    """Delete an AGUI thread within the given room"""
    user_name = await _check_user_in_room(
        room_id=room_id,
        the_installation=the_installation,
        token=token,
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
        content=f"Deleted thread: {thread_id}",
    )
