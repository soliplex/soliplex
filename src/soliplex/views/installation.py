import fastapi
from fastapi import Depends
from fastapi import security

from soliplex import auth
from soliplex import installation
from soliplex import models
from soliplex import util

router = fastapi.APIRouter()

depend_the_installation = installation.depend_the_installation


@util.logfire_span("GET /v1/installation")
@router.get("/v1/installation")
async def get_installation(
    request: fastapi.Request,
    the_installation: installation.Installation = depend_the_installation,
    user=Depends(auth.get_current_user),
) -> models.Installation:
    return models.Installation.from_config(the_installation._config)
