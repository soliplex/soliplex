import datetime
from unittest import mock

import pytest
from sqlalchemy import orm as sqla_orm
from sqlalchemy.ext import asyncio as sqla_asyncio

from soliplex import config
from soliplex.authz import schema as authz_schema

NOW = datetime.datetime.now(datetime.UTC)
ROOM_ID = "test-room"


@mock.patch("datetime.timezone")
@mock.patch("datetime.datetime")
def test__timestamp(dt, tz):
    found = authz_schema._timestamp()

    assert found is dt.now.return_value

    dt.now.assert_called_once_with(tz.utc)


@pytest.mark.parametrize("token", [None, {}, {"foo": "bar"}])
@pytest.mark.parametrize(
    "default_allow_deny",
    [
        authz_schema.AllowDeny.ALLOW,
        authz_schema.AllowDeny.DENY,
    ],
)
def test_roompolicy_check_token_w_empty(default_allow_deny, token):
    policy = authz_schema.RoomPolicy(
        room_id=ROOM_ID,
        default_allow_deny=default_allow_deny,
    )

    found = policy.check_token(token)

    assert found == default_allow_deny


@pytest.mark.parametrize("token", [None, {}, {"foo": "bar"}])
@pytest.mark.parametrize(
    "default_allow_deny",
    [
        authz_schema.AllowDeny.ALLOW,
        authz_schema.AllowDeny.DENY,
    ],
)
def test_roompolicy_check_token_w_acl_miss(default_allow_deny, token):
    policy = authz_schema.RoomPolicy(
        room_id=ROOM_ID,
        default_allow_deny=default_allow_deny,
    )
    _entry = authz_schema.ACLEntry(
        room_policy=policy,
        allow_deny=authz_schema.AllowDeny.ALLOW,
    )

    found = policy.check_token(token)

    assert found == default_allow_deny


@pytest.mark.parametrize("token", [None, {}, {"foo": "bar"}])
@pytest.mark.parametrize(
    "default_allow_deny",
    [
        authz_schema.AllowDeny.ALLOW,
        authz_schema.AllowDeny.DENY,
    ],
)
def test_roompolicy_check_token_w_acl_hit(default_allow_deny, token):
    policy = authz_schema.RoomPolicy(
        room_id=ROOM_ID,
        default_allow_deny=default_allow_deny,
    )
    _entry = authz_schema.ACLEntry(
        room_policy=policy,
        allow_deny=authz_schema.AllowDeny.ALLOW,
        everyone=True,
    )

    found = policy.check_token(token)

    assert found == authz_schema.AllowDeny.ALLOW


@pytest.fixture
def the_room_policy():
    return authz_schema.RoomPolicy(
        room_id=ROOM_ID,
        default_allow_deny=authz_schema.AllowDeny.DENY,
    )


@pytest.mark.parametrize("token", [None, {}, {"foo": "bar"}])
@pytest.mark.parametrize(
    "allow_deny",
    [
        authz_schema.AllowDeny.ALLOW,
        authz_schema.AllowDeny.DENY,
    ],
)
def test_aclentry_check_token_wo_discrim(the_room_policy, allow_deny, token):
    entry = authz_schema.ACLEntry(
        room_policy=the_room_policy,
        allow_deny=allow_deny,
    )

    found = entry.check_token(token)

    assert found is None


@pytest.mark.parametrize("token", [None, {}, {"foo": "bar"}])
@pytest.mark.parametrize(
    "allow_deny",
    [
        authz_schema.AllowDeny.ALLOW,
        authz_schema.AllowDeny.DENY,
    ],
)
def test_aclentry_check_token_w_everyone(the_room_policy, allow_deny, token):
    entry = authz_schema.ACLEntry(
        room_policy=the_room_policy,
        allow_deny=allow_deny,
        everyone=True,
    )

    found = entry.check_token(token)

    assert found == allow_deny


@pytest.mark.parametrize(
    "token, matched",
    [
        (None, False),
        ({}, True),
        ({"foo": "bar"}, True),
    ],
)
@pytest.mark.parametrize(
    "allow_deny",
    [
        authz_schema.AllowDeny.ALLOW,
        authz_schema.AllowDeny.DENY,
    ],
)
def test_aclentry_check_token_w_authenticated(
    the_room_policy,
    allow_deny,
    token,
    matched,
):
    entry = authz_schema.ACLEntry(
        room_policy=the_room_policy,
        allow_deny=allow_deny,
        authenticated=True,
    )

    found = entry.check_token(token)

    if matched:
        assert found == allow_deny
    else:
        assert found is None


@pytest.mark.parametrize(
    "token, matched",
    [
        (None, False),
        ({}, False),
        ({"preferred_username": "miss"}, False),
        ({"preferred_username": "hit"}, True),
    ],
)
@pytest.mark.parametrize(
    "allow_deny",
    [
        authz_schema.AllowDeny.ALLOW,
        authz_schema.AllowDeny.DENY,
    ],
)
def test_aclentry_check_token_w_preferred_username(
    the_room_policy,
    allow_deny,
    token,
    matched,
):
    entry = authz_schema.ACLEntry(
        room_policy=the_room_policy,
        allow_deny=allow_deny,
        preferred_username="hit",
    )

    found = entry.check_token(token)

    if matched:
        assert found == allow_deny
    else:
        assert found is None


@pytest.mark.parametrize(
    "token, matched",
    [
        (None, False),
        ({}, False),
        ({"email": "miss@example.com"}, False),
        ({"email": "hit@example.com"}, True),
    ],
)
@pytest.mark.parametrize(
    "allow_deny",
    [
        authz_schema.AllowDeny.ALLOW,
        authz_schema.AllowDeny.DENY,
    ],
)
def test_aclentry_check_token_w_email(
    the_room_policy,
    allow_deny,
    token,
    matched,
):
    entry = authz_schema.ACLEntry(
        room_policy=the_room_policy,
        allow_deny=allow_deny,
        email="hit@example.com",
    )

    found = entry.check_token(token)

    if matched:
        assert found == allow_deny
    else:
        assert found is None


@pytest.mark.parametrize("init_schema", [False, True])
@mock.patch("sqlalchemy.create_engine")
@mock.patch("soliplex.authz.schema.metadata.create_all")
def test_get_session(
    ca,
    ce,
    init_schema,
):
    kwargs = {}

    if init_schema:
        kwargs["init_schema"] = True

    with authz_schema.get_session(**kwargs) as session:
        assert isinstance(session, sqla_orm.Session)
        assert session.bind is ce.return_value

        ce.assert_called_once_with(config.SYNC_MEMORY_ENGINE_URL)

        if init_schema:
            connection = ce.return_value.connect.return_value
            ca.assert_called_once_with(connection.__enter__.return_value)
        else:
            ca.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("init_schema", [False, True])
@mock.patch("sqlalchemy.ext.asyncio.create_async_engine")
@mock.patch("soliplex.authz.schema.metadata.create_all")
async def test_get_async_session(
    ca,
    cae,
    init_schema,
):
    engine = cae.return_value

    kwargs = {}

    if init_schema:
        kwargs["init_schema"] = True

    session_maker = await authz_schema.get_async_session(**kwargs)

    async with session_maker as session:
        assert isinstance(session, sqla_asyncio.AsyncSession)
        assert session.bind is engine

        cae.assert_called_once_with(config.ASYNC_MEMORY_ENGINE_URL)

        if init_schema:
            engine.begin.assert_called_once_with()
            connection = engine.begin.return_value.__aenter__.return_value
            connection.run_sync.assert_called_once_with(ca)
        else:
            engine.begin.assert_not_called()
