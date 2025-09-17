import fastapi
from fastapi import security

from soliplex import auth
from soliplex import completions
from soliplex import installation
from soliplex import models
from soliplex import util

#------------------------------------------------------------------------------
#   Completions endpoints
#------------------------------------------------------------------------------

router = fastapi.APIRouter()


@util.logfire_span("GET /v1/chat/completions")
@router.get("/v1/chat/completions")
async def get_chat_completions(
    request: fastapi.Request,
    the_installation: installation.Installation =
        installation.depend_the_installation,
    token: security.HTTPAuthorizationCredentials =
        auth.oauth2_predicate,
) -> models.ConfiguredCompletions:
    user = auth.authenticate(the_installation, token)
    completion_configs = the_installation.get_completion_configs(user)

    return {
        key: models.Completion.from_config(completion_config)
        for (key, completion_config) in sorted(completion_configs.items())
    }


@util.logfire_span("GET /v1/chat/completions/{completion_id}")
@router.get("/v1/chat/completions/{completion_id}")
async def get_chat_completion(
    request: fastapi.Request,
    completion_id: str,
    the_installation: installation.Installation =
        installation.depend_the_installation,
    token: security.HTTPAuthorizationCredentials =
        auth.oauth2_predicate,
) -> models.Completion:
    user = auth.authenticate(the_installation, token)
    try:
        completion_config = the_installation.get_completion_config(
            completion_id, user,
        )
    except KeyError:
        raise fastapi.HTTPException(
            status_code=404, detail=f"No such completion: {completion_id}"
        ) from None

    return models.Completion.from_config(completion_config)


@util.logfire_span("POST /v1/chat/completions/{completion_id}")
@router.post("/v1/chat/completions/{completion_id}")
async def post_chat_completion(
    request: fastapi.Request,
    completion_id: str,
    chat_request: models.ChatCompletionRequest,
    the_installation: installation.Installation =
        installation.depend_the_installation,
    token: security.HTTPAuthorizationCredentials =
        auth.oauth2_predicate,
):
    user = auth.authenticate(the_installation, token)
    user_profile = models.UserProfile(
        given_name=user.get("given_name", "<unknown>"),
        family_name=user.get("family_name", "<unknown>"),
        email=user.get("email", "<unknown>"),
        preferred_username=user.get("preferred_username", "<unknown>"),
    )

    try:
        agent = the_installation.get_agent_for_completion(
            completion_id, user,
        )
    except KeyError:
        raise fastapi.HTTPException(
            status_code=404, detail=f"No such completion: {completion_id}"
        ) from None

    agent_deps = models.AgentDependencies(
        user=user_profile,
    )

    return await completions.openai_chat_completion(
        agent, agent_deps, chat_request,
    )
