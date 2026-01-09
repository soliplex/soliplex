import contextlib
from unittest import mock

import fastapi
import pytest

from soliplex import authz as authz_package
from soliplex import installation
from soliplex import models
from soliplex.views import authz as authz_views

ROOM_ID = "test_room"

ROOM_POLICY = models.RoomPolicy(
    room_id=ROOM_ID,
    default_allow_deny=authz_package.AllowDeny.ALLOW,
)


def raises_httpexc(*, match, code) -> pytest.raises:
    def _check(exc):
        return exc.status_code == code

    return pytest.raises(fastapi.HTTPException, match=match, check=_check)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "w_policy, expectation",
    [
        (None, contextlib.nullcontext(None)),
        (
            ROOM_POLICY,
            contextlib.nullcontext(ROOM_POLICY),
        ),
        (
            KeyError(ROOM_ID),
            raises_httpexc(code=404, match="No such room"),
        ),
    ],
)
async def test_get_room_authz(w_policy, expectation):
    request = fastapi.Request(scope={"type": "http"})
    the_installation = mock.create_autospec(installation.Installation)
    the_room_authz = mock.create_autospec(authz_package.RoomAuthorization)

    if isinstance(w_policy, Exception):
        the_room_authz.get_room_policy.side_effect = w_policy
    else:
        the_room_authz.get_room_policy.return_value = w_policy

    token = object()

    with expectation as expected:
        found = await authz_views.get_room_authz(
            request=request,
            room_id=ROOM_ID,
            the_installation=the_installation,
            the_room_authz=the_room_authz,
            token=token,
        )

    if not isinstance(expected, pytest.ExceptionInfo):
        assert found == expected
