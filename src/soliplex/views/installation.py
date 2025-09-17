
import fastapi
from fastapi import security

from soliplex import auth
from soliplex import installation
from soliplex import models
from soliplex import util

router = fastapi.APIRouter()


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
