import fastapi
import pydantic_ai
from fastapi import responses

from soliplex import agents
from soliplex import authn
from soliplex import completions
from soliplex import installation
from soliplex import models
from soliplex import util
from soliplex import views

# -----------------------------------------------------------------------------
#   Completions endpoints
# -----------------------------------------------------------------------------

router = fastapi.APIRouter(tags=["completions"])

depend_the_installation = installation.depend_the_installation
depend_the_user_claims = views.depend_the_user_claims


@util.logfire_span("GET /v1/chat/completions")
@router.get("/v1/chat/completions", summary="Get available completions")
async def get_chat_completions(
    request: fastapi.Request,
    the_installation: installation.Installation = depend_the_installation,
    the_user_claims: authn.UserClaims = depend_the_user_claims,
) -> models.ConfiguredCompletions:
    """Return the completions available to the user"""
    completion_configs = await the_installation.get_completion_configs(
        user=the_user_claims,
    )

    return {
        key: models.Completion.from_config(completion_config)
        for (key, completion_config) in sorted(completion_configs.items())
    }


@util.logfire_span("GET /v1/chat/completions/{completion_id}")
@router.get(
    "/v1/chat/completions/{completion_id}",
    summary="Get a completion",
)
async def get_chat_completion(
    request: fastapi.Request,
    completion_id: str,
    the_installation: installation.Installation = depend_the_installation,
    the_user_claims: authn.UserClaims = depend_the_user_claims,
) -> models.Completion:
    """Return an individual completion"""
    try:
        completion_config = await the_installation.get_completion_config(
            completion_id=completion_id,
            user=the_user_claims,
        )
    except KeyError:
        raise fastapi.HTTPException(
            status_code=404, detail=f"No such completion: {completion_id}"
        ) from None

    return models.Completion.from_config(completion_config)


async def openai_chat_completion(
    agent: pydantic_ai.Agent,
    agent_deps: agents.AgentDependencies,
    chat_request: models.ChatCompletionRequest,
) -> responses.StreamingResponse:
    openai_payload = chat_request.model_dump(exclude_unset=True)
    user_question = openai_payload["messages"][-1]["content"]
    # TODO: figure out how to convert message history to PydanticAI's
    #       format.
    # message_history = munge(openai_payload["messages"][:-1])
    message_history = []

    try:
        return responses.StreamingResponse(
            completions.stream_chat_responses(
                agent,
                agent_deps,
                user_question,
                message_history,
            ),
            media_type="text/event-stream",
            headers=views.HEADERS_DO_NOT_BUFFER_SSE,
        )
    except Exception:
        raise fastapi.HTTPException(
            status_code=500, detail="Error streaming chat responses"
        ) from None


@util.logfire_span("POST /v1/chat/completions/{completion_id}")
@router.post(
    "/v1/chat/completions/{completion_id}",
    summary="Post to a completion",
)
async def post_chat_completion(
    request: fastapi.Request,
    completion_id: str,
    chat_request: models.ChatCompletionRequest,
    the_installation: installation.Installation = depend_the_installation,
    the_user_claims: authn.UserClaims = depend_the_user_claims,
) -> responses.StreamingResponse:
    try:
        agent = await the_installation.get_agent_for_completion(
            completion_id=completion_id,
            user=the_user_claims,
        )
    except KeyError:
        raise fastapi.HTTPException(
            status_code=404, detail=f"No such completion: {completion_id}"
        ) from None

    user_profile = models.UserProfile.from_user_claims(the_user_claims)

    agent_deps = await the_installation.get_agent_deps_for_completion(
        completion_id=completion_id,
        user=user_profile,
    )

    return await openai_chat_completion(
        agent,
        agent_deps,
        chat_request,
    )
