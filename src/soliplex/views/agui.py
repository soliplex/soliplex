from __future__ import annotations

import functools

import fastapi
import pydantic_ai
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
from soliplex.agui import util as agui_util

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


async def _check_user_thread(
    *,
    room_id: str,
    thread_id: str,
    user_name: str,
    the_threads: agui_package.ThreadStorage,
) -> agui_package.Thread:
    """Check for an existing thread for the user within the given room"""
    try:
        thread = await the_threads.get_thread(
            user_name=user_name,
            thread_id=thread_id,
        )
    except agui_package.UnknownThread:
        raise fastapi.HTTPException(
            status_code=404,
            detail=f"No such thread: {thread_id}",
        ) from None

    t_room_id = await thread.awaitable_attrs.room_id

    if t_room_id != room_id:
        msg = f"Expected thread.room_id: {room_id}, found {t_room_id}"
        raise fastapi.HTTPException(
            status_code=400,
            detail=msg,
        ) from None

    return thread


async def _check_user_thread_run(
    *,
    room_id: str,
    thread_id: str,
    user_name: str,
    run_id: str,
    the_threads: agui_package.ThreadStorage,
) -> agui_package.Run:
    """Check for an existing thread / run for the user within the given room"""
    try:
        run = await the_threads.get_run(
            thread_id=thread_id,
            user_name=user_name,
            run_id=run_id,
        )
    except agui_package.UnknownRun:
        raise fastapi.HTTPException(
            status_code=404,
            detail=f"No such run: {run_id}",
        ) from None

    thread = await run.awaitable_attrs.thread
    t_room_id = await thread.awaitable_attrs.room_id

    if t_room_id != room_id:
        msg = f"Expected thread.room_id: {room_id}, found {t_room_id}"
        raise fastapi.HTTPException(
            status_code=400,
            detail=msg,
        ) from None

    return run


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
    thread = await _check_user_thread(
        room_id=room_id,
        thread_id=thread_id,
        user_name=user_name,
        the_threads=the_threads,
    )
    thread_meta = await thread.awaitable_attrs.thread_metadata

    a_thread_runs = {}

    for a_run in await thread.list_runs():
        a_thread_runs[a_run.run_id] = models.AGUI_Run.from_run(
            a_run=a_run,
            a_run_input=(
                await a_run.awaitable_attrs.run_agent_input
            ).to_agui_model(),
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
    run = await _check_user_thread_run(
        room_id=room_id,
        thread_id=thread_id,
        user_name=user_name,
        run_id=run_id,
        the_threads=the_threads,
    )
    await run.awaitable_attrs.thread

    return models.AGUI_Run.from_run(
        a_run=run,
        a_run_input=(
            await run.awaitable_attrs.run_agent_input
        ).to_agui_model(),
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
        rai = await run.awaitable_attrs.run_agent_input
        run_meta = await run.awaitable_attrs.run_metadata
        run_map[run.run_id] = models.AGUI_Run.from_run(
            a_run=run,
            a_run_input=rai.to_agui_model(),
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
            thread_id=thread_id,
            parent_run_id=parent_run_id,
            run_metadata=r_metadata,
        )
    except agui_package.MissingParentRun:
        raise fastapi.HTTPException(
            status_code=400,
            detail=f"No such parent run: {parent_run_id}",
        ) from None

    # Wait for these for a new run because the are set only at commit time
    run_id = await run.awaitable_attrs.run_id
    created = await run.awaitable_attrs.created

    return models.AGUI_Run(
        room_id=room_id,
        thread_id=thread_id,
        parent_run_id=parent_run_id,
        run_id=run_id,
        created=created,
        run_input=(await run.awaitable_attrs.run_agent_input).to_agui_model(),
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

    await the_threads.update_thread(
        user_name=user_name,
        thread_id=thread_id,
        thread_metadata=new_md_dict,
    )
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
    run = await _check_user_thread_run(
        room_id=room_id,
        thread_id=thread_id,
        user_name=user_name,
        run_id=run_id,
        the_threads=the_threads,
    )

    agui_adapter = await ai_ag_ui.AGUIAdapter.from_request(
        request=request,
        agent=agent,
    )

    old_run_agent_input = await run.awaitable_attrs.run_agent_input
    new_run_agent_input = agui_adapter.run_input

    try:
        agui_util.check_run_input(old_run_agent_input, new_run_agent_input)
    except agui_package.RunInputMismatch:
        raise fastapi.HTTPException(
            status_code=400,
            detail="Mismatched 'run_input'",
        ) from None

    agent_deps = the_installation.get_agent_deps_for_room(
        room_id,
        user=user,
        run_agent_input=new_run_agent_input,
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

    await the_threads.update_run(
        thread_id=thread_id,
        user_name=user_name,
        run_id=run_id,
        run_metadata=new_md_dict,
    )
    return fastapi.Response(status_code=205)


@util.logfire_span("DELETE /v1/rooms/{room_id}/agui/{thread_id}")
@router.post("/v1/rooms/{room_id}/agui/{thread_id}")
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
    await _check_user_thread(
        room_id=room_id,
        thread_id=thread_id,
        user_name=user_name,
        the_threads=the_threads,
    )

    await the_threads.delete_thread(
        user_name=user_name,
        thread_id=thread_id,
    )
    return fastapi.Response(
        status_code=204,
        content=f"Deleted thread: {thread_id}",
    )
