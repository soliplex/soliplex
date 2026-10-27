import re
from unittest import mock

import fastapi
import pytest

from soliplex import authz
from soliplex import installation
from soliplex import loggers
from soliplex import models
from soliplex.views import authz as authz_views

PREFERRED_USERNAME = "bharney"
USER_SUB = "user-sub"
ADMIN_EMAIL = "admin@example.com"
ADMIN_EMAIL_JSON_PATH = f'$[?$.email == "{ADMIN_EMAIL}"]'
ADMIN_OTHER_JSON_PATH = '$[?$.group == "test.admin.group"]'
THE_USER_CLAIMS = {"email": ADMIN_EMAIL}

ROOM_ID = "test_room"
ROOM_POLICY = models.RoomPolicy(
    room_id=ROOM_ID,
    default_allow_deny=authz.AllowDeny.ALLOW,
)

NEW_ROOM_POLICY = models.RoomPolicy(
    room_id=ROOM_ID,
    default_allow_deny=authz.AllowDeny.DENY,
    acl_entries=[
        models.ACLEntry(
            allow_deny=authz.AllowDeny.ALLOW,
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

    the_logger.bind.assert_called_once_with(loggers.AUTHZ_LOGGER_NAME)


@pytest.mark.anyio
@pytest.mark.parametrize("w_admin_access", [False, True])
@pytest.mark.parametrize("w_policy", [None, ROOM_POLICY])
async def test_get_room_authz(w_policy, w_admin_access):
    the_installation = mock.create_autospec(installation.Installation)
    the_admin_users = mock.create_autospec(authz.AdminUserPolicy)
    the_room_authz = mock.create_autospec(authz.RoomAuthorizationPolicy)
    the_admin_users.check_admin_access.return_value = w_admin_access
    the_room_authz.get_room_policy.return_value = w_policy
    the_authz_logger = mock.create_autospec(loggers.LogWrapper)

    if not w_admin_access:
        with pytest.raises(fastapi.HTTPException) as exc:
            await authz_views.get_room_authz(
                room_id=ROOM_ID,
                the_installation=the_installation,
                the_admin_users=the_admin_users,
                the_room_authz=the_room_authz,
                the_user_claims=THE_USER_CLAIMS,
                the_authz_logger=the_authz_logger,
            )

        assert exc.value.status_code == 403
        assert exc.value.detail == loggers.AUTHZ_ADMIN_ACCESS_REQUIRED

        the_room_authz.get_room_policy.assert_not_awaited()

    else:
        found = await authz_views.get_room_authz(
            room_id=ROOM_ID,
            the_installation=the_installation,
            the_admin_users=the_admin_users,
            the_room_authz=the_room_authz,
            the_user_claims=THE_USER_CLAIMS,
            the_authz_logger=the_authz_logger,
        )

        assert found == w_policy

        the_room_authz.get_room_policy.assert_awaited_once_with(
            room_id=ROOM_ID,
        )

    the_authz_logger.debug.assert_called_once_with(
        loggers.AUTHZ_GET_ROOM_POLICY,
    )

    the_admin_users.check_admin_access.assert_awaited_once_with(
        THE_USER_CLAIMS,
        resource=loggers.AUDIT_RESOURCE_ROOM_POLICY,
        action=loggers.AUDIT_ACTION_READ,
    )


@pytest.mark.anyio
@pytest.mark.parametrize("w_admin_access", [False, True])
@pytest.mark.parametrize("w_existing", [False, True])
async def test_post_room_authz(w_existing, w_admin_access):
    the_installation = mock.create_autospec(installation.Installation)
    the_admin_users = mock.create_autospec(authz.AdminUserPolicy)
    the_room_authz = mock.create_autospec(authz.RoomAuthorizationPolicy)
    the_admin_users.check_admin_access.return_value = w_admin_access

    if w_existing:
        the_room_authz.get_room_policy.return_value = ROOM_POLICY

    the_authz_logger = mock.create_autospec(loggers.LogWrapper)

    if not w_admin_access:
        with pytest.raises(fastapi.HTTPException) as exc:
            await authz_views.post_room_authz(
                room_id=ROOM_ID,
                room_policy=NEW_ROOM_POLICY,
                the_installation=the_installation,
                the_admin_users=the_admin_users,
                the_room_authz=the_room_authz,
                the_user_claims=THE_USER_CLAIMS,
                the_authz_logger=the_authz_logger,
            )

        assert exc.value.status_code == 403
        assert exc.value.detail == loggers.AUTHZ_ADMIN_ACCESS_REQUIRED

        the_room_authz.update_room_policy.assert_not_awaited()

    else:
        found = await authz_views.post_room_authz(
            room_id=ROOM_ID,
            room_policy=NEW_ROOM_POLICY,
            the_installation=the_installation,
            the_admin_users=the_admin_users,
            the_room_authz=the_room_authz,
            the_user_claims=THE_USER_CLAIMS,
            the_authz_logger=the_authz_logger,
        )

        assert isinstance(found, fastapi.Response)
        assert found.status_code == 204

        the_room_authz.update_room_policy.assert_awaited_once_with(
            room_id=ROOM_ID,
            room_policy=NEW_ROOM_POLICY,
        )

    the_authz_logger.debug.assert_called_once_with(
        loggers.AUTHZ_POST_ROOM_POLICY,
    )

    the_admin_users.check_admin_access.assert_awaited_once_with(
        THE_USER_CLAIMS,
        resource=loggers.AUDIT_RESOURCE_ROOM_POLICY,
        action=loggers.AUDIT_ACTION_UPDATE,
    )


@pytest.mark.anyio
@pytest.mark.parametrize("w_admin_access", [False, True])
@pytest.mark.parametrize("w_existing", [False, True])
async def test_delete_room_authz(w_existing, w_admin_access):
    the_installation = mock.create_autospec(installation.Installation)
    the_admin_users = mock.create_autospec(authz.AdminUserPolicy)
    the_room_authz = mock.create_autospec(authz.RoomAuthorizationPolicy)
    the_admin_users.check_admin_access.return_value = w_admin_access

    if w_existing:
        the_room_authz.get_room_policy.return_value = ROOM_POLICY

    the_authz_logger = mock.create_autospec(loggers.LogWrapper)

    if not w_admin_access:
        with pytest.raises(fastapi.HTTPException) as exc:
            await authz_views.delete_room_authz(
                room_id=ROOM_ID,
                the_installation=the_installation,
                the_admin_users=the_admin_users,
                the_room_authz=the_room_authz,
                the_user_claims=THE_USER_CLAIMS,
                the_authz_logger=the_authz_logger,
            )

        assert exc.value.status_code == 403
        assert exc.value.detail == loggers.AUTHZ_ADMIN_ACCESS_REQUIRED

        the_room_authz.delete_room_policy.assert_not_awaited()

    else:
        found = await authz_views.delete_room_authz(
            room_id=ROOM_ID,
            the_installation=the_installation,
            the_admin_users=the_admin_users,
            the_room_authz=the_room_authz,
            the_user_claims=THE_USER_CLAIMS,
            the_authz_logger=the_authz_logger,
        )

        assert isinstance(found, fastapi.Response)
        assert found.status_code == 204

        the_room_authz.delete_room_policy.assert_awaited_once_with(
            room_id=ROOM_ID,
        )

    the_authz_logger.debug.assert_called_once_with(
        loggers.AUTHZ_DELETE_ROOM_POLICY,
    )

    the_admin_users.check_admin_access.assert_awaited_once_with(
        THE_USER_CLAIMS,
        resource=loggers.AUDIT_RESOURCE_ROOM_POLICY,
        action=loggers.AUDIT_ACTION_DELETE,
    )


@pytest.mark.anyio
@pytest.mark.parametrize("w_admin_access", [False, True])
@pytest.mark.parametrize(
    "w_admin_user_discrims",
    [
        [],
        [ADMIN_EMAIL_JSON_PATH],
        [ADMIN_OTHER_JSON_PATH],
        [ADMIN_EMAIL_JSON_PATH, ADMIN_OTHER_JSON_PATH],
    ],
)
@pytest.mark.parametrize("w_room_policy", [None, ROOM_POLICY])
async def test_get_installation_authz(
    w_room_policy,
    w_admin_user_discrims,
    w_admin_access,
):
    the_installation = mock.create_autospec(installation.Installation)
    the_installation.get_room_configs.return_value = {ROOM_ID: object()}
    the_admin_users = mock.create_autospec(authz.AdminUserPolicy)
    the_room_authz = mock.create_autospec(authz.RoomAuthorizationPolicy)
    the_admin_users.check_admin_access.return_value = w_admin_access
    the_room_authz.get_room_policy.return_value = w_room_policy
    the_admin_users.list_admin_user_discriminators.return_value = (
        w_admin_user_discrims
    )
    the_authz_logger = mock.create_autospec(loggers.LogWrapper)

    if not w_admin_access:
        with pytest.raises(fastapi.HTTPException) as exc:
            await authz_views.get_installation_authz(
                the_installation=the_installation,
                the_admin_users=the_admin_users,
                the_room_authz=the_room_authz,
                the_user_claims=THE_USER_CLAIMS,
                the_authz_logger=the_authz_logger,
            )

        assert exc.value.status_code == 403
        assert exc.value.detail == loggers.AUTHZ_ADMIN_ACCESS_REQUIRED

        the_room_authz.get_room_policy.assert_not_awaited()
        the_admin_users.list_admin_user_discriminators.assert_not_awaited()

    else:
        expected = models.InstallationAuthorization(
            admin_user_discriminators=w_admin_user_discrims,
            room_policies={
                ROOM_ID: w_room_policy,
            },
        )

        found = await authz_views.get_installation_authz(
            the_installation=the_installation,
            the_admin_users=the_admin_users,
            the_room_authz=the_room_authz,
            the_user_claims=THE_USER_CLAIMS,
            the_authz_logger=the_authz_logger,
        )

        assert found == expected

        the_room_authz.get_room_policy.assert_awaited_once_with(
            room_id=ROOM_ID,
        )
        the_admin_users.list_admin_user_discriminators.assert_awaited_once_with()
        the_installation.get_room_configs.assert_awaited_once_with(
            user=THE_USER_CLAIMS,
            the_room_authz=the_room_authz,
            the_logger=the_authz_logger,
        )

    the_authz_logger.debug.assert_called_once_with(
        loggers.AUTHZ_GET_INSTALLATION_AUTHZ,
    )

    the_admin_users.check_admin_access.assert_awaited_once_with(
        THE_USER_CLAIMS,
        resource=loggers.AUDIT_RESOURCE_INSTALLATION_AUTHZ,
        action=loggers.AUDIT_ACTION_READ,
    )


@pytest.mark.anyio
@pytest.mark.parametrize("w_admin_access", [False, True])
async def test_get_user_authz(
    w_admin_access,
):
    the_admin_users = mock.create_autospec(authz.AdminUserPolicy)
    the_admin_users.is_admin.return_value = w_admin_access
    the_authz_logger = mock.create_autospec(loggers.LogWrapper)

    expected = models.UserAuthorization(is_admin_user=w_admin_access)

    found = await authz_views.get_user_authz(
        the_admin_users=the_admin_users,
        the_user_claims=THE_USER_CLAIMS,
        the_authz_logger=the_authz_logger,
    )

    assert found == expected

    the_admin_users.is_admin.assert_awaited_once_with(THE_USER_CLAIMS)

    the_authz_logger.debug.assert_called_once_with(
        loggers.AUTHZ_GET_USER_AUTHZ,
    )


@pytest.mark.parametrize(
    "resource, expected",
    [
        ("ingester_control", True),
        ("soliplex:room:test-room", True),
        ("v1.2", True),
        ("", False),
        ("has space", False),
        ("has/slash", False),
        ("caf\u00e9", False),
    ],
)
def test_authz_check_resource_pattern(resource, expected):

    found = re.fullmatch(authz_views.AUTHZ_CHECK_RESOURCE_PATTERN, resource)

    assert (found is not None) is expected


PUN_CLAIM_NON_WIRESAFE = {"preferred_username": "Andr\u00e9"}
PUN_CLAIM_WIRESAFE = {"preferred_username": PREFERRED_USERNAME}
EMAIL_CLAIM_NON_WIRESAFE = {"email": f"{ADMIN_EMAIL}\n"}
EMAIL_CLAIM_WIRESAFE = {"email": ADMIN_EMAIL}
SUB_CLAIM_NON_WIRESAFE = {"sub": f"{USER_SUB}\t"}
SUB_CLAIM_WIRESAFE = {"sub": USER_SUB}
# A quirky IdP's non-string JSON claims fail the wire gate, like any
# other non-safe value, and fall through.
PUN_CLAIM_NON_STRING = {"preferred_username": 12345}
EMAIL_CLAIM_NON_STRING = {"email": {"local": "phreddy"}}


@pytest.mark.parametrize(
    "claims, expected",
    [
        # No claims
        ({}, None),
        # Non-wiresafe claims miss
        (SUB_CLAIM_NON_WIRESAFE, None),
        (EMAIL_CLAIM_NON_WIRESAFE, None),
        (PUN_CLAIM_NON_WIRESAFE, None),
        # Non-string claims miss, and fall through like any non-safe value.
        (PUN_CLAIM_NON_STRING, None),
        (PUN_CLAIM_NON_STRING | EMAIL_CLAIM_WIRESAFE, ADMIN_EMAIL),
        (EMAIL_CLAIM_NON_STRING, None),
        (EMAIL_CLAIM_NON_STRING | SUB_CLAIM_WIRESAFE, USER_SUB),
        # Wiresafe claims hit
        (SUB_CLAIM_WIRESAFE, USER_SUB),
        (EMAIL_CLAIM_WIRESAFE, ADMIN_EMAIL),
        (PUN_CLAIM_WIRESAFE, PREFERRED_USERNAME),
        # Precedence
        (SUB_CLAIM_WIRESAFE | EMAIL_CLAIM_WIRESAFE, ADMIN_EMAIL),
        (SUB_CLAIM_WIRESAFE | PUN_CLAIM_WIRESAFE, PREFERRED_USERNAME),
        (EMAIL_CLAIM_WIRESAFE | PUN_CLAIM_WIRESAFE, PREFERRED_USERNAME),
        (
            PUN_CLAIM_WIRESAFE | EMAIL_CLAIM_WIRESAFE | SUB_CLAIM_WIRESAFE,
            PREFERRED_USERNAME,
        ),
        # Claims with precedence but non-wiresafe values do not short circuit
        (
            PUN_CLAIM_NON_WIRESAFE
            | EMAIL_CLAIM_NON_WIRESAFE
            | SUB_CLAIM_WIRESAFE,
            USER_SUB,
        ),
        (
            PUN_CLAIM_NON_WIRESAFE | EMAIL_CLAIM_WIRESAFE | SUB_CLAIM_WIRESAFE,
            ADMIN_EMAIL,
        ),
        (
            PUN_CLAIM_NON_WIRESAFE
            | EMAIL_CLAIM_NON_WIRESAFE
            | SUB_CLAIM_NON_WIRESAFE,
            None,
        ),
    ],
)
def test__soliplex_user_for_header(claims, expected):

    found = authz_views._soliplex_user_for_header(claims)

    assert found == expected


AUTHZ_CHECK_RESOURCE = "ingester_control"


@pytest.mark.anyio
async def test_get_authz_check_denied():
    the_admin_users = mock.create_autospec(authz.AdminUserPolicy)
    the_admin_users.check_admin_access.return_value = False

    with pytest.raises(fastapi.HTTPException) as exc:
        await authz_views.get_authz_check(
            resource=AUTHZ_CHECK_RESOURCE,
            the_admin_users=the_admin_users,
            the_user_claims=THE_USER_CLAIMS,
        )

    assert exc.value.status_code == 403
    assert exc.value.detail == loggers.AUTHZ_ADMIN_ACCESS_REQUIRED
    the_admin_users.check_admin_access.assert_awaited_once_with(
        THE_USER_CLAIMS,
        resource=AUTHZ_CHECK_RESOURCE,
        action=loggers.AUDIT_ACTION_ACCESS,
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "claims, exp_user",
    [
        (THE_USER_CLAIMS, ADMIN_EMAIL),
        ({"name": "Anonymous"}, None),
    ],
)
async def test_get_authz_check_allowed(claims, exp_user):
    the_admin_users = mock.create_autospec(authz.AdminUserPolicy)
    the_admin_users.check_admin_access.return_value = True

    found = await authz_views.get_authz_check(
        resource=AUTHZ_CHECK_RESOURCE,
        the_admin_users=the_admin_users,
        the_user_claims=claims,
    )

    assert found.status_code == 204
    assert found.headers.get(authz_views.AUTHZ_CHECK_USER_HEADER) == exp_user
    the_admin_users.check_admin_access.assert_awaited_once_with(
        claims,
        resource=AUTHZ_CHECK_RESOURCE,
        action=loggers.AUDIT_ACTION_ACCESS,
    )
