import fastapi
from fastapi import responses
from fastapi import security
from pydantic_ai.ui import ag_ui as ai_ag_ui

from soliplex import auth
from soliplex import installation
from soliplex import models
from soliplex import util
from soliplex.agui import parser as agui_parser
from soliplex.agui import thread as agui_thread

router = fastapi.APIRouter(tags=["rooms"])

depend_the_installation = installation.depend_the_installation
depend_the_threads = agui_thread.depend_the_threads


@util.logfire_span("POST /v1/rooms/{room_id}/agui")
@router.post("/v1/rooms/{room_id}/agui")
async def post_room_agui(
    request: fastapi.Request,
    room_id: str,
    new_thread_request: models.AGUI_NewThreadRequest,
    the_installation: installation.Installation = depend_the_installation,
    the_threads: agui_thread.Threads = depend_the_threads,
    token: security.HTTPAuthorizationCredentials = auth.oauth2_predicate,
) -> models.AGUI_Thread:
    """Create a new AGUI thread within the given room

    Add the initial AGUI run to the thread.

    Body of request, if passed, must validate to 'models.AGUI_ThreadMetadata'.
    """
    user = auth.authenticate(the_installation, token)
    user_name = user.get("preferred_username", "<unknown>")

    try:
        the_installation.get_room_config(room_id, user)
    except KeyError:
        raise fastapi.HTTPException(
            status_code=404,
            detail=f"No such room: {room_id}",
        ) from None

    if new_thread_request.metadata is not None:
        t_metadata = agui_thread.ThreadMetadata(
            **new_thread_request.metadata.model_dump()
        )
    else:
        t_metadata = None

    thread = await the_threads.new_thread(
        room_id=room_id,
        user_name=user_name,
        metadata=t_metadata,
    )

    run = await thread.new_run()

    return models.AGUI_Thread(
        room_id=room_id,
        thread_id=thread.thread_id,
        runs={
            run.run_id: models.AGUI_Run(
                room_id=room_id,
                thread_id=thread.thread_id,
                run_id=run.run_id,
                created=run.created,
                parent_run_id=None,
                run_input=run.run_input,
                events=run.events,
                metadata=None,
            ),
        },
        created=thread.created,
        metadata=new_thread_request.metadata,
    )


@util.logfire_span("POST /v1/rooms/{room_id}/agui/{thread_id}")
@router.post("/v1/rooms/{room_id}/agui/{thread_id}")
async def post_room_agui_thread_id(
    request: fastapi.Request,
    room_id: str,
    thread_id: str,
    new_run_request: models.AGUI_NewRunRequest,
    the_installation: installation.Installation = depend_the_installation,
    the_threads: agui_thread.Threads = depend_the_threads,
    token: security.HTTPAuthorizationCredentials = auth.oauth2_predicate,
) -> models.AGUI_Run:
    """Create a new AGUI run for a thread within the given room

    Body of request, if passed, must validate to 'models.AGUI_RunMetadata'.
    """
    user = auth.authenticate(the_installation, token)
    user_name = user.get("preferred_username", "<unknown>")

    try:
        the_installation.get_room_config(room_id, user)
    except KeyError:
        raise fastapi.HTTPException(
            status_code=404,
            detail=f"No such room: {room_id}",
        ) from None

    try:
        thread = await the_threads.get_thread(
            user_name=user_name,
            thread_id=thread_id,
        )
    except agui_thread.UnknownThread:
        raise fastapi.HTTPException(
            status_code=404,
            detail=f"No such thread: {thread_id}",
        ) from None

    parent_run_id = new_run_request.parent_run_id

    if new_run_request.metadata is not None:
        r_metadata = agui_thread.RunMetadata(
            **new_run_request.metadata.model_dump()
        )
    else:
        r_metadata = None

    try:
        run = await thread.new_run(
            parent_run_id=parent_run_id,
            metadata=r_metadata,
        )
    except agui_thread.MissingParentRunId:
        raise fastapi.HTTPException(
            status_code=400,
            detail=f"No such parent run: {parent_run_id}",
        ) from None

    return models.AGUI_Run(
        room_id=room_id,
        thread_id=thread_id,
        run_id=run.run_id,
        created=run.created,
        parent_run_id=parent_run_id,
        run_input=run.run_input,
        events=run.events,
        metadata=new_run_request.metadata,
    )


@util.logfire_span("POST /v1/rooms/{room_id}/agui/{thread_id}/{run_id}")
@router.post("/v1/rooms/{room_id}/agui/{thread_id}/{run_id}")
async def post_room_agui_thread_id_run_id(
    request: fastapi.Request,
    room_id: str,
    thread_id: str,
    run_id: str,
    the_installation: installation.Installation = depend_the_installation,
    the_threads: agui_thread.Threads = depend_the_threads,
    token: security.HTTPAuthorizationCredentials = auth.oauth2_predicate,
) -> responses.StreamingResponse:
    """Execute an AGUI run"""

    user = auth.authenticate(the_installation, token)

    user_profile = models.UserProfile(
        given_name=user.get("given_name", "<unknown>"),
        family_name=user.get("family_name", "<unknown>"),
        email=user.get("email", "<unknown>"),
        preferred_username=user.get("preferred_username", "<unknown>"),
    )
    user_name = user_profile.preferred_username

    try:
        agent = the_installation.get_agent_for_room(room_id, user)
    except KeyError:
        raise fastapi.HTTPException(
            status_code=404,
            detail=f"No such room: {room_id}",
        ) from None

    agui_adapter = await ai_ag_ui.AGUIAdapter.from_request(
        request=request,
        agent=agent,
    )

    try:
        thread = await the_threads.get_thread(
            user_name=user_name,
            thread_id=thread_id,
        )
    except agui_thread.UnknownThread:
        raise fastapi.HTTPException(
            status_code=404,
            detail=f"No such thread: {thread_id}",
        ) from None

    try:
        run = await thread.get_run(run_id)
    except agui_thread.UnknownRunId:
        raise fastapi.HTTPException(
            status_code=404,
            detail=f"No such run: {run_id}",
        ) from None

    run_input = agui_adapter.run_input

    try:
        run.check_run_input(run_input)
    except agui_thread.RunInputMismatch:
        raise fastapi.HTTPException(
            status_code=400,
            detail="Mismatched 'run_input'",
        ) from None

    agent_deps = models.AgentDependencies(
        the_installation=the_installation,
        user=user_profile,
    )

    agent_stream = agui_adapter.run_stream(deps=agent_deps)

    esp = agui_parser.EventStreamParser(run_input, run=run)
    esp_stream = esp.parse_stream(agent_stream)
    sse_stream = agui_adapter.encode_stream(esp_stream)

    return responses.StreamingResponse(
        sse_stream,
        media_type=agui_adapter.accept,
    )
