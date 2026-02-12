from unittest import mock

import fastapi
import pytest

from soliplex import authz as authz_package
from soliplex import installation
from soliplex import loggers
from soliplex import models
from soliplex.views import authz as authz_views

ADMIN_EMAIL = "admin@example.com"
THE_USER_CLAIMS = {"email": ADMIN_EMAIL}

ROOM_ID = "test_room"
ROOM_POLICY = models.RoomPolicy(
    room_id=ROOM_ID,
    default_allow_deny=authz_package.AllowDeny.ALLOW,
)

NEW_ROOM_POLICY = models.RoomPolicy(
    room_id=ROOM_ID,
    default_allow_deny=authz_package.AllowDeny.DENY,
    acl_entries=[
        models.ACLEntry(
            allow_deny=authz_package.AllowDeny.ALLOW,
            email="phreddy@example.com",
        ),
    ],
)


def test_get_the_authz_logger():
    the_logger = mock.create_autospec(loggers.LogWrapper)

    found = authz_views.get_the_authz_logger(
        the_logger=the_logger,
    )

    assert found is the_logger.bind.return_value

    the_logger.bind.assert_called_once_with(name=loggers.AUTHZ_LOGGER_NAME)


@pytest.mark.anyio
@pytest.mark.parametrize("w_admin_access", [False, True])
@pytest.mark.parametrize("w_policy", [None, ROOM_POLICY])
async def test_get_room_authz(w_policy, w_admin_access):
    request = fastapi.Request(scope={"type": "http"})
    the_installation = mock.create_autospec(installation.Installation)
    the_authz_policy = mock.create_autospec(authz_package.AuthorizationPolicy)
    the_authz_policy.check_admin_access.return_value = w_admin_access
    the_authz_policy.get_room_policy.return_value = w_policy
    the_authz_logger = mock.create_autospec(loggers.LogWrapper)

    if not w_admin_access:
        with pytest.raises(fastapi.HTTPException) as exc:
            await authz_views.get_room_authz(
                request=request,
                room_id=ROOM_ID,
                the_installation=the_installation,
                the_authz_policy=the_authz_policy,
                the_user_claims=THE_USER_CLAIMS,
                the_authz_logger=the_authz_logger,
            )

        assert exc.value.status_code == 403
        assert exc.value.detail == loggers.AUTHZ_ADMIN_ACCESS_REQUIRED

        the_authz_logger.error.assert_called_once_with(
            loggers.AUTHZ_ADMIN_ACCESS_REQUIRED
        )

        the_authz_policy.get_room_policy.assert_not_awaited()

    else:
        found = await authz_views.get_room_authz(
            request=request,
            room_id=ROOM_ID,
            the_installation=the_installation,
            the_authz_policy=the_authz_policy,
            the_user_claims=THE_USER_CLAIMS,
            the_authz_logger=the_authz_logger,
        )

        assert found == w_policy

        the_authz_policy.get_room_policy.assert_awaited_once_with(
            room_id=ROOM_ID,
            user_token=THE_USER_CLAIMS,
        )

    the_authz_logger.debug.assert_called_once_with(
        loggers.AUTHZ_GET_ROOM_POLICY,
    )

    the_authz_policy.check_admin_access.assert_awaited_once_with(
        THE_USER_CLAIMS,
    )


@pytest.mark.anyio
@pytest.mark.parametrize("w_admin_access", [False, True])
@pytest.mark.parametrize("w_existing", [False, True])
async def test_post_room_authz(w_existing, w_admin_access):
    request = fastapi.Request(scope={"type": "http"})
    the_installation = mock.create_autospec(installation.Installation)
    the_authz_policy = mock.create_autospec(authz_package.AuthorizationPolicy)
    the_authz_policy.check_admin_access.return_value = w_admin_access

    if w_existing:
        the_authz_policy.get_room_policy.return_value = ROOM_POLICY

    the_authz_logger = mock.create_autospec(loggers.LogWrapper)

    if not w_admin_access:
        with pytest.raises(fastapi.HTTPException) as exc:
            await authz_views.post_room_authz(
                request=request,
                room_id=ROOM_ID,
                room_policy=NEW_ROOM_POLICY,
                the_installation=the_installation,
                the_authz_policy=the_authz_policy,
                the_user_claims=THE_USER_CLAIMS,
                the_authz_logger=the_authz_logger,
            )

        assert exc.value.status_code == 403
        assert exc.value.detail == loggers.AUTHZ_ADMIN_ACCESS_REQUIRED

        the_authz_logger.error.assert_called_once_with(
            loggers.AUTHZ_ADMIN_ACCESS_REQUIRED,
        )

        the_authz_policy.update_room_policy.assert_not_awaited()

    else:
        found = await authz_views.post_room_authz(
            request=request,
            room_id=ROOM_ID,
            room_policy=NEW_ROOM_POLICY,
            the_installation=the_installation,
            the_authz_policy=the_authz_policy,
            the_user_claims=THE_USER_CLAIMS,
            the_authz_logger=the_authz_logger,
        )

        assert isinstance(found, fastapi.Response)
        assert found.status_code == 204

        the_authz_policy.update_room_policy.assert_awaited_once_with(
            room_id=ROOM_ID,
            room_policy=NEW_ROOM_POLICY,
            user_token=THE_USER_CLAIMS,
        )

    the_authz_logger.debug.assert_called_once_with(
        loggers.AUTHZ_POST_ROOM_POLICY,
    )

    the_authz_policy.check_admin_access.assert_awaited_once_with(
        THE_USER_CLAIMS,
    )


@pytest.mark.anyio
@pytest.mark.parametrize("w_admin_access", [False, True])
@pytest.mark.parametrize("w_existing", [False, True])
async def test_delete_room_authz(w_existing, w_admin_access):
    request = fastapi.Request(scope={"type": "http"})
    the_installation = mock.create_autospec(installation.Installation)
    the_authz_policy = mock.create_autospec(authz_package.AuthorizationPolicy)
    the_authz_policy.check_admin_access.return_value = w_admin_access

    if w_existing:
        the_authz_policy.get_room_policy.return_value = ROOM_POLICY

    the_authz_logger = mock.create_autospec(loggers.LogWrapper)

    if not w_admin_access:
        with pytest.raises(fastapi.HTTPException) as exc:
            await authz_views.delete_room_authz(
                request=request,
                room_id=ROOM_ID,
                the_installation=the_installation,
                the_authz_policy=the_authz_policy,
                the_user_claims=THE_USER_CLAIMS,
                the_authz_logger=the_authz_logger,
            )

        assert exc.value.status_code == 403
        assert exc.value.detail == loggers.AUTHZ_ADMIN_ACCESS_REQUIRED

        the_authz_logger.error.assert_called_once_with(
            loggers.AUTHZ_ADMIN_ACCESS_REQUIRED,
        )

        the_authz_policy.delete_room_policy.assert_not_awaited()

    else:
        found = await authz_views.delete_room_authz(
            request=request,
            room_id=ROOM_ID,
            the_installation=the_installation,
            the_authz_policy=the_authz_policy,
            the_user_claims=THE_USER_CLAIMS,
            the_authz_logger=the_authz_logger,
        )

        assert isinstance(found, fastapi.Response)
        assert found.status_code == 204

        the_authz_policy.delete_room_policy.assert_awaited_once_with(
            room_id=ROOM_ID,
            user_token=THE_USER_CLAIMS,
        )

    the_authz_logger.debug.assert_called_once_with(
        loggers.AUTHZ_DELETE_ROOM_POLICY,
    )

    the_authz_policy.check_admin_access.assert_awaited_once_with(
        THE_USER_CLAIMS,
    )


@pytest.mark.anyio
@pytest.mark.parametrize("w_admin_access", [False, True])
@pytest.mark.parametrize("w_admin_user", [None, ADMIN_EMAIL])
@pytest.mark.parametrize("w_room_policy", [None, ROOM_POLICY])
async def test_get_installation_authz(
    w_room_policy,
    w_admin_user,
    w_admin_access,
):
    request = fastapi.Request(scope={"type": "http"})
    the_installation = mock.create_autospec(installation.Installation)
    the_installation.get_room_configs.return_value = {ROOM_ID: object()}
    the_authz_policy = mock.create_autospec(authz_package.AuthorizationPolicy)
    the_authz_policy.check_admin_access.return_value = w_admin_access
    the_authz_logger = mock.create_autospec(loggers.LogWrapper)

    if w_admin_user is not None:
        exp_admin_emails = [ADMIN_EMAIL]
    else:
        exp_admin_emails = []

    the_authz_policy.list_admin_users.return_value = exp_admin_emails

    the_authz_policy.get_room_policy.return_value = w_room_policy

    if not w_admin_access:
        with pytest.raises(fastapi.HTTPException) as exc:
            await authz_views.get_installation_authz(
                request=request,
                the_installation=the_installation,
                the_authz_policy=the_authz_policy,
                the_user_claims=THE_USER_CLAIMS,
                the_authz_logger=the_authz_logger,
            )

        assert exc.value.status_code == 403
        assert exc.value.detail == loggers.AUTHZ_ADMIN_ACCESS_REQUIRED

        the_authz_logger.error.assert_called_once_with(
            loggers.AUTHZ_ADMIN_ACCESS_REQUIRED,
        )

        the_authz_policy.get_room_policy.assert_not_awaited()
        the_authz_policy.list_admin_users.assert_not_awaited()

    else:
        expected = models.InstallationAuthorization(
            admin_user_emails=exp_admin_emails,
            room_policies={
                ROOM_ID: w_room_policy,
            },
        )

        found = await authz_views.get_installation_authz(
            request=request,
            the_installation=the_installation,
            the_authz_policy=the_authz_policy,
            the_user_claims=THE_USER_CLAIMS,
            the_authz_logger=the_authz_logger,
        )

        assert found == expected

        the_authz_policy.get_room_policy.assert_awaited_once_with(
            room_id=ROOM_ID,
            user_token=THE_USER_CLAIMS,
        )
        the_authz_policy.list_admin_users.assert_awaited_once_with()
        the_installation.get_room_configs.assert_awaited_once_with(
            user=THE_USER_CLAIMS,
            the_authz_policy=the_authz_policy,
            the_logger=the_authz_logger,
        )

    the_authz_logger.debug.assert_called_once_with(
        loggers.AUTHZ_GET_INSTALLATION_AUTHZ,
    )

    the_authz_policy.check_admin_access.assert_awaited_once_with(
        THE_USER_CLAIMS,
    )
