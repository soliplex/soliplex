"""Soliplex thread-label catalogue views

The catalogue is global to the installation and administrator-curated:
creating, renaming, recoloring and deleting a label all require admin
access. *Attaching* an existing label to a thread does not, and lives
with the other thread handlers in 'views.agui' -- the module split
mirrors the authorization split.
"""

import fastapi

from soliplex import agui
from soliplex import authn
from soliplex import authz
from soliplex import loggers
from soliplex import models
from soliplex import util
from soliplex import views

router = fastapi.APIRouter(tags=["labels"])

depend_the_threads = agui.depend_the_threads
depend_the_admin_users = views.depend_the_admin_user_policy
depend_the_user_claims = views.depend_the_user_claims
depend_the_logger = views.depend_the_logger


def get_the_labels_logger(
    the_logger: loggers.LogWrapper = depend_the_logger,
) -> loggers.LogWrapper:
    return the_logger.bind(loggers.LABELS_LOGGER_NAME)


depend_the_labels_logger = fastapi.Depends(get_the_labels_logger)


async def _check_admin(
    *,
    the_admin_users: authz.AdminUserPolicy,
    the_user_claims: authn.UserClaims,
    action: str,
) -> None:
    """Raise a 403 unless the caller is an administrator."""
    if not await the_admin_users.check_admin_access(
        the_user_claims,
        resource=loggers.AUDIT_RESOURCE_THREAD_LABEL,
        action=action,
    ):
        raise fastapi.HTTPException(
            status_code=403,
            detail=loggers.AUTHZ_ADMIN_ACCESS_REQUIRED,
        ) from None


@util.logfire_span("GET /v1/agui/labels")
@router.get("/v1/agui/labels")
async def get_agui_labels(
    the_threads: agui.ThreadStorage = depend_the_threads,
    the_admin_users: authz.AdminUserPolicy = depend_the_admin_users,
    the_user_claims: authn.UserClaims = depend_the_user_claims,
    the_labels_logger: loggers.LogWrapper = depend_the_labels_logger,
) -> models.AGUI_Labels:
    """Return the installation's label catalogue

    Readable by anyone: a user has to know the catalogue to attach
    anything from it, and the client renders chips from it.

    Usage counts ride along only for administrators. They span every
    user's threads, so a label name beside a volume would tell an
    ordinary user how much work exists that they cannot otherwise see --
    and, since only administrators can delete a label, the count (whose
    whole purpose is to warn before deleting one in use) is of no use to
    anyone else.
    """
    the_labels_logger.debug(loggers.LABELS_GET)

    is_admin = await the_admin_users.check_admin_access(
        the_user_claims,
        resource=loggers.AUDIT_RESOURCE_THREAD_LABEL,
        action=loggers.AUDIT_ACTION_READ,
    )

    labels = await the_threads.list_labels()
    # Omitted outright for non-admins rather than sent as 0 or null, so
    # a client cannot read "not allowed to know" as "unused" and offer a
    # delete that is in fact destructive.
    counts = await the_threads.get_label_usage_counts() if is_admin else {}

    return models.AGUI_Labels(
        labels=[
            models.AGUI_Label.from_label(
                a_label,
                usage_count=counts.get(a_label.id_, 0) if is_admin else None,
            )
            for a_label in labels
        ]
    )


@util.logfire_span("POST /v1/agui/labels")
@router.post("/v1/agui/labels")
async def post_agui_labels(
    new_label: models.AGUI_NewLabelRequest,
    the_threads: agui.ThreadStorage = depend_the_threads,
    the_admin_users: authz.AdminUserPolicy = depend_the_admin_users,
    the_user_claims: authn.UserClaims = depend_the_user_claims,
    the_labels_logger: loggers.LogWrapper = depend_the_labels_logger,
) -> models.AGUI_Label:
    """Add a label to the catalogue (administrators only)"""
    the_labels_logger.debug(loggers.LABELS_POST)

    await _check_admin(
        the_admin_users=the_admin_users,
        the_user_claims=the_user_claims,
        action=loggers.AUDIT_ACTION_CREATE,
    )

    try:
        label = await the_threads.create_label(
            name=new_label.name,
            color=new_label.color,
        )

    except agui.AGUI_Exception as exc:
        raise fastapi.HTTPException(
            status_code=exc.status_code,
            detail=exc.args,
        ) from None

    return models.AGUI_Label.from_label(label)


@util.logfire_span("POST /v1/agui/labels/{label_id}")
@router.post("/v1/agui/labels/{label_id}")
async def post_agui_label_id(
    label_id: int,
    updated_label: models.AGUI_UpdateLabelRequest,
    the_threads: agui.ThreadStorage = depend_the_threads,
    the_admin_users: authz.AdminUserPolicy = depend_the_admin_users,
    the_user_claims: authn.UserClaims = depend_the_user_claims,
    the_labels_logger: loggers.LogWrapper = depend_the_labels_logger,
) -> models.AGUI_Label:
    """Rename and/or recolor a label (administrators only)

    POST rather than PATCH: the repository has no 'patch' or 'put'
    handler anywhere, and this follows the thread-metadata update.
    """
    the_labels_logger.debug(loggers.LABELS_POST_LABEL)

    await _check_admin(
        the_admin_users=the_admin_users,
        the_user_claims=the_user_claims,
        action=loggers.AUDIT_ACTION_UPDATE,
    )

    try:
        label = await the_threads.update_label(
            label_id=label_id,
            name=updated_label.name,
            color=updated_label.color,
        )

    except agui.AGUI_Exception as exc:
        raise fastapi.HTTPException(
            status_code=exc.status_code,
            detail=exc.args,
        ) from None

    return models.AGUI_Label.from_label(label)


@util.logfire_span("DELETE /v1/agui/labels/{label_id}")
@router.delete("/v1/agui/labels/{label_id}")
async def delete_agui_label_id(
    label_id: int,
    the_threads: agui.ThreadStorage = depend_the_threads,
    the_admin_users: authz.AdminUserPolicy = depend_the_admin_users,
    the_user_claims: authn.UserClaims = depend_the_user_claims,
    the_labels_logger: loggers.LogWrapper = depend_the_labels_logger,
) -> fastapi.Response:
    """Remove a label from the catalogue (administrators only)

    Detaches it from every thread carrying it; the threads themselves
    are untouched. Returns an HTTP 205 (Reset Content) on success.
    """
    the_labels_logger.debug(loggers.LABELS_DELETE_LABEL)

    await _check_admin(
        the_admin_users=the_admin_users,
        the_user_claims=the_user_claims,
        action=loggers.AUDIT_ACTION_DELETE,
    )

    try:
        await the_threads.delete_label(label_id=label_id)

    except agui.AGUI_Exception as exc:
        raise fastapi.HTTPException(
            status_code=exc.status_code,
            detail=exc.args,
        ) from None

    return fastapi.Response(status_code=205)
