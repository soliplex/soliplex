import json
import pathlib
import subprocess
import traceback

import fastapi

from soliplex import authn
from soliplex import authz
from soliplex import installation
from soliplex import models
from soliplex import util
from soliplex import views

router = fastapi.APIRouter(tags=["installation"])

depend_the_installation = installation.depend_the_installation
depend_the_authz = authz.depend_the_authz_policy
depend_the_user_claims = views.depend_the_user_claims


@util.logfire_span("GET /v1/installation")
@router.get("/v1/installation")
async def get_installation(
    request: fastapi.Request,
    the_installation: installation.Installation = depend_the_installation,
    the_authz_policy: authz.AuthorizationPolicy = depend_the_authz,
    the_user_claims: authn.UserClaims = depend_the_user_claims,
) -> models.Installation:
    """Return the installation's top-level configuration"""
    if not await the_authz_policy.check_admin_access(the_user_claims):
        raise fastapi.HTTPException(
            status_code=403,
            detail="Admin access required",
        ) from None

    return models.Installation.from_config(the_installation._config)


@util.logfire_span("GET /v1/installation/versions")
@router.get("/v1/installation/versions")
async def get_installation_versions(
    request: fastapi.Request,
    the_installation: installation.Installation = depend_the_installation,
    the_authz_policy: authz.AuthorizationPolicy = depend_the_authz,
    the_user_claims: authn.UserClaims = depend_the_user_claims,
) -> models.InstalledPackages:
    """Return the installation's top-level configuration"""
    if not await the_authz_policy.check_admin_access(the_user_claims):
        raise fastapi.HTTPException(
            status_code=403,
            detail="Admin access required",
        ) from None

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
    the_authz_policy: authz.AuthorizationPolicy = depend_the_authz,
    the_user_claims: authn.UserClaims = depend_the_user_claims,
) -> installation.ProviderInfoMap:
    """Return the installation's top-level configuration"""
    if not await the_authz_policy.check_admin_access(the_user_claims):
        raise fastapi.HTTPException(
            status_code=403,
            detail="Admin access required",
        ) from None

    return the_installation.all_provider_info


@util.logfire_span("GET /v1/installation/git_metadata")
@router.get("/v1/installation/git_metadata")
async def get_installation_git_metadata(
    request: fastapi.Request,
    the_installation: installation.Installation = depend_the_installation,
    the_user_claims: authn.UserClaims = depend_the_user_claims,
) -> models.GitMetadata:
    """Return the installation's top-level configuration"""
    git_metadata = util.GitMetadata(pathlib.Path.cwd())

    return models.GitMetadata(
        git_hash=git_metadata.git_hash,
        git_branch=git_metadata.git_branch,
        git_tag=git_metadata.git_tag,
    )
