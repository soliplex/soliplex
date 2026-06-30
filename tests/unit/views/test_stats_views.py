import contextlib
import datetime
from unittest import mock

import fastapi
import pytest

from soliplex import agui
from soliplex import authz
from soliplex import installation
from soliplex import loggers
from soliplex import models
from soliplex.views import stats as stats_views

ROOM_ID = "test-room"
ROOM_ID_2 = "test-room-2"
USER_NAME = "phreddy"
EMAIL = "phreddy@example.com"

THE_USER_CLAIMS = {"preferred_username": USER_NAME, "email": EMAIL}

T1 = datetime.datetime(2026, 1, 1, 12, 0, tzinfo=datetime.UTC)
T2 = datetime.datetime(2026, 1, 2, 12, 0, tzinfo=datetime.UTC)

no_error = contextlib.nullcontext


def raises_httpexc(*, match, code) -> pytest.raises:
    def _check(exc):
        return exc.status_code == code

    return pytest.raises(fastapi.HTTPException, match=match, check=_check)


@pytest.fixture
def the_threads():
    return mock.create_autospec(agui.ThreadStorage)


@pytest.fixture
def the_logger():
    return mock.create_autospec(loggers.LogWrapper)


def _installation_with_rooms(*room_ids):
    the_installation = mock.create_autospec(installation.Installation)
    the_installation.get_room_configs.return_value = {
        room_id: mock.Mock() for room_id in room_ids
    }
    return the_installation


@pytest.mark.anyio
async def test_get_rooms_stats(the_threads, the_logger):
    the_installation = _installation_with_rooms(ROOM_ID, ROOM_ID_2)
    the_room_authz = mock.create_autospec(authz.RoomAuthorizationPolicy)
    the_threads.get_rooms_last_activity.return_value = {
        ROOM_ID: T1,
        ROOM_ID_2: T2,
    }

    found = await stats_views.get_rooms_stats(
        the_installation=the_installation,
        the_room_authz=the_room_authz,
        the_threads=the_threads,
        the_user_claims=THE_USER_CLAIMS,
        the_logger=the_logger,
    )

    assert found == {
        ROOM_ID: models.RoomStats(room_id=ROOM_ID, last_activity=T1),
        ROOM_ID_2: models.RoomStats(room_id=ROOM_ID_2, last_activity=T2),
    }
    the_threads.get_rooms_last_activity.assert_awaited_once_with(
        user_name=USER_NAME,
    )
    the_installation.get_room_configs.assert_awaited_once_with(
        user=THE_USER_CLAIMS,
        the_room_authz=the_room_authz,
        the_logger=the_logger,
    )


@pytest.mark.anyio
async def test_get_rooms_stats_filters_inaccessible(the_threads, the_logger):
    # The user has activity in both rooms but currently only has access
    # to ROOM_ID; the de-authorized ROOM_ID_2 must drop out.
    the_installation = _installation_with_rooms(ROOM_ID)
    the_room_authz = mock.create_autospec(authz.RoomAuthorizationPolicy)
    the_threads.get_rooms_last_activity.return_value = {
        ROOM_ID: T1,
        ROOM_ID_2: T2,
    }

    found = await stats_views.get_rooms_stats(
        the_installation=the_installation,
        the_room_authz=the_room_authz,
        the_threads=the_threads,
        the_user_claims=THE_USER_CLAIMS,
        the_logger=the_logger,
    )

    assert found == {
        ROOM_ID: models.RoomStats(room_id=ROOM_ID, last_activity=T1),
    }


@pytest.mark.anyio
async def test_get_rooms_stats_no_accessible_rooms(the_threads, the_logger):
    the_installation = _installation_with_rooms()
    the_room_authz = mock.create_autospec(authz.RoomAuthorizationPolicy)
    the_threads.get_rooms_last_activity.return_value = {}

    found = await stats_views.get_rooms_stats(
        the_installation=the_installation,
        the_room_authz=the_room_authz,
        the_threads=the_threads,
        the_user_claims=THE_USER_CLAIMS,
        the_logger=the_logger,
    )

    assert found == {}


@pytest.mark.anyio
async def test_get_rooms_stats_includes_accessible_room_without_activity(
    the_threads, the_logger
):
    # Every accessible room appears; one the user has no runs in carries a
    # null last_activity rather than being omitted.
    the_installation = _installation_with_rooms(ROOM_ID, ROOM_ID_2)
    the_room_authz = mock.create_autospec(authz.RoomAuthorizationPolicy)
    the_threads.get_rooms_last_activity.return_value = {ROOM_ID: T1}

    found = await stats_views.get_rooms_stats(
        the_installation=the_installation,
        the_room_authz=the_room_authz,
        the_threads=the_threads,
        the_user_claims=THE_USER_CLAIMS,
        the_logger=the_logger,
    )

    assert found == {
        ROOM_ID: models.RoomStats(room_id=ROOM_ID, last_activity=T1),
        ROOM_ID_2: models.RoomStats(room_id=ROOM_ID_2, last_activity=None),
    }


@pytest.mark.anyio
@pytest.mark.parametrize("last_activity", [T1, None])
async def test_get_room_stats(the_threads, the_logger, last_activity):
    the_installation = mock.create_autospec(installation.Installation)
    the_room_authz = mock.create_autospec(authz.RoomAuthorizationPolicy)
    the_threads.get_room_last_activity.return_value = last_activity

    found = await stats_views.get_room_stats(
        room_id=ROOM_ID,
        the_installation=the_installation,
        the_room_authz=the_room_authz,
        the_threads=the_threads,
        the_user_claims=THE_USER_CLAIMS,
        the_logger=the_logger,
    )

    assert found == models.RoomStats(
        room_id=ROOM_ID,
        last_activity=last_activity,
    )
    the_installation.get_room_config.assert_awaited_once_with(
        room_id=ROOM_ID,
        user=THE_USER_CLAIMS,
        the_room_authz=the_room_authz,
        the_logger=the_logger,
    )
    the_threads.get_room_last_activity.assert_awaited_once_with(
        user_name=USER_NAME,
        room_id=ROOM_ID,
    )


@pytest.mark.anyio
async def test_get_room_stats_unknown_room(the_threads, the_logger):
    the_installation = mock.create_autospec(installation.Installation)
    the_room_authz = mock.create_autospec(authz.RoomAuthorizationPolicy)
    the_installation.get_room_config.side_effect = KeyError("testing")

    with raises_httpexc(code=404, match="unknown room id"):
        await stats_views.get_room_stats(
            room_id=ROOM_ID,
            the_installation=the_installation,
            the_room_authz=the_room_authz,
            the_threads=the_threads,
            the_user_claims=THE_USER_CLAIMS,
            the_logger=the_logger,
        )

    the_threads.get_room_last_activity.assert_not_called()
    the_logger.exception.assert_called_once_with(
        loggers.ROOM_UNKNOWN_ROOM_ID,
        room_id=ROOM_ID,
    )


@pytest.mark.anyio
async def test_get_room_stats_serializes_aware_datetime(
    the_threads, the_logger
):
    # The whole point of '_as_utc' + 'AwareDatetime': the serialized value
    # must carry a UTC offset so clients don't parse it as local time.
    the_installation = mock.create_autospec(installation.Installation)
    the_room_authz = mock.create_autospec(authz.RoomAuthorizationPolicy)
    the_threads.get_room_last_activity.return_value = T1

    found = await stats_views.get_room_stats(
        room_id=ROOM_ID,
        the_installation=the_installation,
        the_room_authz=the_room_authz,
        the_threads=the_threads,
        the_user_claims=THE_USER_CLAIMS,
        the_logger=the_logger,
    )

    dumped = found.model_dump(mode="json")
    parsed = datetime.datetime.fromisoformat(dumped["last_activity"])
    assert parsed.tzinfo is not None
    assert parsed == T1


@pytest.mark.anyio
async def test_get_rooms_stats_serializes_aware_datetime(
    the_threads, the_logger
):
    the_installation = _installation_with_rooms(ROOM_ID)
    the_room_authz = mock.create_autospec(authz.RoomAuthorizationPolicy)
    the_threads.get_rooms_last_activity.return_value = {ROOM_ID: T1}

    found = await stats_views.get_rooms_stats(
        the_installation=the_installation,
        the_room_authz=the_room_authz,
        the_threads=the_threads,
        the_user_claims=THE_USER_CLAIMS,
        the_logger=the_logger,
    )

    dumped = found[ROOM_ID].model_dump(mode="json")
    parsed = datetime.datetime.fromisoformat(dumped["last_activity"])
    assert parsed.tzinfo is not None
    assert parsed == T1


@pytest.mark.anyio
async def test_get_room_stats_serializes_null_activity(
    the_threads, the_logger
):
    # An accessible room with no runs must serialize last_activity as JSON
    # null -- not omit the key, not error.
    the_installation = mock.create_autospec(installation.Installation)
    the_room_authz = mock.create_autospec(authz.RoomAuthorizationPolicy)
    the_threads.get_room_last_activity.return_value = None

    found = await stats_views.get_room_stats(
        room_id=ROOM_ID,
        the_installation=the_installation,
        the_room_authz=the_room_authz,
        the_threads=the_threads,
        the_user_claims=THE_USER_CLAIMS,
        the_logger=the_logger,
    )

    dumped = found.model_dump(mode="json")
    assert dumped["last_activity"] is None
