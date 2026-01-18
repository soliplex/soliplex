import json
import subprocess
import traceback

import fastapi
from fastapi import security

from soliplex import authn
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
    token: security.HTTPAuthorizationCredentials = authn.oauth2_predicate,
) -> models.Installation:
    """Return the installation's top-level configuration"""
    authn.authenticate(the_installation, token)
    return models.Installation.from_config(the_installation._config)


@util.logfire_span("GET /v1/installation/versions")
@router.get("/v1/installation/versions")
async def get_installation_versions(
    request: fastapi.Request,
    the_installation: installation.Installation = depend_the_installation,
    token: security.HTTPAuthorizationCredentials = authn.oauth2_predicate,
) -> models.InstalledPackages:
    """Return the installation's top-level configuration"""
    authn.authenticate(the_installation, token)

    try:
        found = (
            subprocess.check_output(
                ["pip", "list", "--format", "json"],
            )
            .decode("utf-8")
            .strip()
        )
    except Exception:
        error = traceback.format_exc()
        raise fastapi.HTTPException(
            status_code=500,
            detail=error,
        ) from None

    installed = json.loads(found)
    packages = {package.pop("name"): package for package in installed}

    return packages


@util.logfire_span("GET /v1/installation/providers")
@router.get("/v1/installation/providers")
async def get_installation_providers(
    request: fastapi.Request,
    the_installation: installation.Installation = depend_the_installation,
    token: security.HTTPAuthorizationCredentials = authn.oauth2_predicate,
) -> installation.ProviderInfoMap:
    """Return the installation's top-level configuration"""
    authn.authenticate(the_installation, token)
    return the_installation.all_provider_info
