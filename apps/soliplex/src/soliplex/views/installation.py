import fastapi
from fastapi import security

from soliplex import auth
from soliplex import installation
from soliplex import models
from soliplex import util

router = fastapi.APIRouter(tags=["installation"])

depend_the_installation = installation.depend_the_installation


@util.logfire_span("GET /v1/installation")
@router.get("/v1/installation")
async def get_installation(
    request: fastapi.Request,
    the_installation: installation.Installation = depend_the_installation,
    token: security.HTTPAuthorizationCredentials = auth.oauth2_predicate,
) -> models.Installation:
    """Return the installation's top-level configuration"""
    auth.authenticate(the_installation, token)
    return models.Installation.from_config(the_installation._config)
