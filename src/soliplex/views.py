import datetime
import json

import fastapi
from fastapi import responses
from fastapi import security
from pydantic_ai import messages as ai_messages

from soliplex import auth
from soliplex import convos
from soliplex import installation
from soliplex import models
from soliplex import util

router = fastapi.APIRouter()

#   'process_control' canary
@util.logfire_span("GET /ok")
@router.get("/ok", response_class=responses.PlainTextResponse)
async def health_check():
    return "OK"


# testing and validation
@util.logfire_span("GET /check-headers")
@router.get("/check-headers")
async def check_headers(request: fastapi.Request):  # pragma: NO COVER
    return_to="https://google.com"
    redirect_uri = request.url_for("health_check")
    redirect_uri = redirect_uri.replace_query_params(return_to=return_to)
    #redirect_uri = redirect_uri.replace(netloc=redirect_uri.netloc + '/api')
    return {
        "X-Forwarded-For": request.headers.get("x-forwarded-for"),
        "X-Forwarded-Proto": request.headers.get("x-forwarded-proto"),
        "X-Forwarded-Host": request.headers.get("x-forwarded-host"),
        "X-Forwarded-Port": request.headers.get("x-forwarded-port"),
        "X-Real-IP": request.headers.get("x-real-ip"),
        "Host": request.headers.get("host"),
        "redirect_uri": redirect_uri,
        "headers": request.headers,
    }


@util.logfire_span("GET /v1/installation")
@router.get("/v1/installation", response_model=models.Installation)
async def get_installation(
    request: fastapi.Request,
    the_installation: installation.Installation =
        installation.depend_the_installation,
    token: security.HTTPAuthorizationCredentials = auth.oauth2_predicate,
):
    auth.authenticate(the_installation, token)
    return models.Installation.from_config(the_installation._config)

#==============================================================================
#   API endpoints for convos
#==============================================================================


@util.logfire_span("POST /v1/convos/new")
@router.post("/v1/convos/new")
async def post_convos_new(
    request: fastapi.Request,
    convo_msg: models.NewConvoClientMessage,
    the_installation: installation.Installation =
        installation.depend_the_installation,
    the_convos: convos.Conversations = convos.depend_the_convos,
    token: security.HTTPAuthorizationCredentials =
        auth.oauth2_predicate,
):
    """Create a new convo, including room ID and URI with UUID"""
    user = auth.authenticate(the_installation, token)
    user_profile = models.UserProfile(
        given_name=user.get("given_name", "<unknown>"),
        family_name=user.get("family_name", "<unknown>"),
        email=user.get("email", "<unknown>"),
        preferred_username=user.get("preferred_username", "<unknown>"),
    )
    user_name = user_profile.preferred_username

    try:
        agent = the_installation.get_agent_for_room(
            convo_msg.room_id, user=user,
        )
    except KeyError:
        raise fastapi.HTTPException(
            status_code=404, detail=f"No such room: {convo_msg.room_id}",
        ) from None


    agent_deps = models.AgentDependencies(
        user=user_profile,
    )

    async with agent.run_stream(
        convo_msg.text, message_history=[], deps=agent_deps,
    ) as result:
        await result.get_output()
        new_messages = result.new_messages()

    context_messages = convos._filter_context_messages(new_messages)

    convo = await the_convos.new_conversation(
        user_name,
        convo_msg.room_id,
        convo_msg.text,
        new_messages=context_messages,
    )

    return convo


@util.logfire_span("POST /v1/convos/new/{room_id}")
@router.post("/v1/convos/new/{room_id}")
async def post_convos_new_room(
    request: fastapi.Request,
    room_id: str,
    convo_msg: models.UserPromptClientMessage,
    the_installation: installation.Installation =
        installation.depend_the_installation,
    the_convos: convos.Conversations = convos.depend_the_convos,
    token: security.HTTPAuthorizationCredentials =
        auth.oauth2_predicate,
    response_model=convos.Conversation,
):
    """Create a new convo, including room ID and URI with UUID"""
    user = auth.authenticate(the_installation, token)
    user_profile = models.UserProfile(
        given_name=user.get("given_name", "<unknown>"),
        family_name=user.get("family_name", "<unknown>"),
        email=user.get("email", "<unknown>"),
        preferred_username=user.get("preferred_username", "<unknown>"),
    )
    user_name = user_profile.preferred_username

    try:
        agent = the_installation.get_agent_for_room(
            room_id, user=user,
        )
    except KeyError:
        raise fastapi.HTTPException(
            status_code=404, detail=f"No such room: {room_id}",
        ) from None

    agent_deps = models.AgentDependencies(
        user=user_profile,
    )

    async with agent.run_stream(
        convo_msg.text, message_history=[], deps=agent_deps,
    ) as result:
        await result.get_output()
        new_messages = result.new_messages()

    context_messages = convos._filter_context_messages(new_messages)

    convo = await the_convos.new_conversation(
        user_name,
        room_id,
        convo_msg.text,
        new_messages=context_messages,
    )

    return convo


@util.logfire_span("GET /v1/convos")
@router.get("/v1/convos")
async def get_convos(
    request: fastapi.Request,
    the_installation: installation.Installation =
        installation.depend_the_installation,
    the_convos: convos.Conversations = convos.depend_the_convos,
    token: security.HTTPAuthorizationCredentials =
        auth.oauth2_predicate,
):
    """Return a list of conversations, including room ID and URI with UUID"""
    user = auth.authenticate(the_installation, token)
    user_name = user.get("preferred_username", "<unknown>")
    convos = await the_convos.user_conversations(user_name)
    return convos


@util.logfire_span("GET /v1/convos/{convo_uuid}")
@router.get("/v1/convos/{convo_uuid}")
async def get_convo(
    request: fastapi.Request,
    convo_uuid: str,
    the_installation: installation.Installation =
        installation.depend_the_installation,
    the_convos: convos.Conversations = convos.depend_the_convos,
    token: security.HTTPAuthorizationCredentials =
        auth.oauth2_predicate,
):
    """Return the conversation, by id

    Include the message history for the conversation, along with room ID, etc.
    """
    user = auth.authenticate(the_installation, token)
    user_name = user.get("preferred_username", "<unknown>")
    convo = await the_convos.get_conversation_info(user_name, convo_uuid)
    return convo


@util.logfire_span("POST /v1/convos/{convo_uuid}")
@router.post("/v1/convos/{convo_uuid}")
async def post_convo(
    request: fastapi.Request,
    convo_uuid: str,
    convo_msg: models.UserPromptClientMessage,
    the_installation: installation.Installation =
        installation.depend_the_installation,
    the_convos: convos.Conversations = convos.depend_the_convos,
    token: security.HTTPAuthorizationCredentials =
        auth.oauth2_predicate,
):
    """Send another query to an existing convo.

    Return the final response message.
    """
    user = auth.authenticate(the_installation, token)

    user_profile = models.UserProfile(
        given_name=user.get("given_name", "<unknown>"),
        family_name=user.get("family_name", "<unknown>"),
        email=user.get("email", "<unknown>"),
        preferred_username=user.get("preferred_username", "<unknown>"),
    )
    user_name = user_profile.preferred_username

    convo = await the_convos.get_conversation(user_name, convo_uuid)

    try:
        agent = the_installation.get_agent_for_room(
            convo.room_id, user=user,
        )
    except KeyError:
        raise fastapi.HTTPException(
            status_code=404, detail=f"No such room: {convo.room_id}",
        ) from None

    agent_deps = models.AgentDependencies(
        user=user_profile,
    )

    async def stream_messages(text: str, convo: convos.Conversation):
        """Streams new line delimited JSON `Message`s to the client."""
        # stream the user prompt so that can be displayed straight away
        timestamp = datetime.datetime.now(tz=datetime.UTC).isoformat()

        yield (
            json.dumps(
                {
                    "role": "user",
                    "timestamp": timestamp,
                    "content": text,
                }
            ).encode("utf-8")
            + b"\n"
        )

        async with agent.run_stream(
            text, message_history=convo.message_history, deps=agent_deps,
        ) as result:
            #output = await result.get_output()
            async for text in result.stream(debounce_by=0.01):
                # text here is a `str` and the frontend wants
                # JSON encoded ModelResponse, so we create one
                text_part = ai_messages.TextPart(text)
                mr = ai_messages.ModelResponse(
                    parts=[text_part], timestamp=result.timestamp()
                )
                yield json.dumps(
                    convos._to_convo_message(mr),
                ).encode("utf-8") + b"\n"

            new_messages = result.new_messages()

        context_messages = convos._filter_context_messages(new_messages)

        await the_convos.append_to_conversation(
            user_name, convo_uuid, context_messages,
        )

    return responses.StreamingResponse(
        stream_messages(convo_msg.text, convo), media_type="text/plain",
    )


@util.logfire_span("DELETE /v1/convos/{convo_uuid}")
@router.delete("/v1/convos/{convo_uuid}", status_code=204)
async def delete_convo(
    request: fastapi.Request,
    convo_uuid: str,
    the_installation: installation.Installation =
        installation.depend_the_installation,
    the_convos: convos.Conversations = convos.depend_the_convos,
    token: security.HTTPAuthorizationCredentials =
        auth.oauth2_predicate,
):
    """Delete an existing convo.
    """
    user = auth.authenticate(the_installation, token)
    user_name = user.get("preferred_username", "<unknown>")

    await the_convos.delete_conversation(user_name, convo_uuid)
