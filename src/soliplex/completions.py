import fastapi
from fastapi import security

from soliplex import auth
from soliplex import installation
from soliplex import models

#------------------------------------------------------------------------------
#   '/api/v1/completions/{completion_id}' endpoint
#------------------------------------------------------------------------------

router = fastapi.APIRouter()


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
    completion_configs = the_installation.get_completion_configs(user)
    try:
        completion_config = completion_configs[completion_id]
    except KeyError:
        raise fastapi.HTTPException(
            status_code=404, detail=f"No such completion: {completion_id}"
        ) from None

    return models.Completion.from_config(completion_config)
