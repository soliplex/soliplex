import fastapi
from fastapi import Depends
from fastapi import responses
from fastapi import security

from soliplex import auth
from soliplex import completions
from soliplex import installation
from soliplex import models
from soliplex import util

# -----------------------------------------------------------------------------
#   Completions endpoints
# -----------------------------------------------------------------------------

router = fastapi.APIRouter(tags=["completions"])

depend_the_installation = installation.depend_the_installation


@util.logfire_span("GET /v1/chat/completions")
@router.get("/v1/chat/completions", summary="Get available completions")
async def get_chat_completions(
    request: fastapi.Request,
    the_installation: installation.Installation = depend_the_installation,
    user=Depends(auth.get_current_user),
) -> models.ConfiguredCompletions:
    """Return the completions available to the user"""
    completion_configs = the_installation.get_completion_configs(user)

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
    user=Depends(auth.get_current_user),
) -> models.Completion:
    """Return an individual completion"""
    try:
        completion_config = the_installation.get_completion_config(
            completion_id,
            user,
        )
    except KeyError:
        raise fastapi.HTTPException(
            status_code=404, detail=f"No such completion: {completion_id}"
        ) from None

    return models.Completion.from_config(completion_config)


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
    user=Depends(auth.get_current_user),
) -> responses.StreamingResponse:
    user_profile = models.UserProfile(
        given_name=user.get("given_name", "<unknown>"),
        family_name=user.get("family_name", "<unknown>"),
        email=user.get("email", "<unknown>"),
        preferred_username=user.get("preferred_username", "<unknown>"),
    )

    try:
        agent = the_installation.get_agent_for_completion(
            completion_id,
            user,
        )
    except KeyError:
        raise fastapi.HTTPException(
            status_code=404, detail=f"No such completion: {completion_id}"
        ) from None

    agent_deps = models.AgentDependencies(
        the_installation=the_installation,
        user=user_profile,
    )

    return await completions.openai_chat_completion(
        agent,
        agent_deps,
        chat_request,
    )
