import datetime
from unittest import mock

import pytest
from sqlalchemy import orm as sqla_orm
from sqlalchemy.ext import asyncio as sqla_asyncio

from soliplex import authz as authz_package
from soliplex import models
from soliplex import util
from soliplex.authz import schema as authz_schema
from soliplex.config import installation as config_installation

NOW = datetime.datetime.now(datetime.UTC)

EMAIL = "phreddy@example.com"

ROOM_ID = "test-room"

ACL_ENTRY_DEFAULTS = {
    "everyone": False,
    "authenticated": False,
    "preferred_username": None,
    "email": None,
    "allow_deny": authz_package.AllowDeny.DENY,
}

ROOM_POLICY_DEFAULTS = {
    "room_id": ROOM_ID,
    "default_allow_deny": authz_package.AllowDeny.DENY,
    "acl_entries": [],
}


@mock.patch("datetime.timezone")
@mock.patch("datetime.datetime")
def test__timestamp(dt, tz):
    found = authz_schema._timestamp()

    assert found is dt.now.return_value

    dt.now.assert_called_once_with(tz.utc)


def test_adminuser_ctor(the_session):
    admin_user = authz_schema.AdminUser(email=EMAIL)

    the_session.add(admin_user)
    the_session.commit()


def test_roompolicy_ctor(the_session):
    policy = authz_schema.RoomPolicy(
        room_id=ROOM_ID,
    )

    the_session.add(policy)
    the_session.commit()

    assert policy.default_allow_deny == authz_package.AllowDeny.DENY


@pytest.mark.parametrize(
    "model_kwargs",
    [
        {},
        {"default_allow_deny": authz_package.AllowDeny.ALLOW},
        {
            "acl_entries_kwargs": [
                {
                    "allow_deny": authz_package.AllowDeny.ALLOW,
                    "authenticated": True,
                },
            ],
        },
        {
            "acl_entries_kwargs": [
                {
                    "allow_deny": authz_package.AllowDeny.ALLOW,
                    "email": "phreddy@example.com",
                },
                {
                    "allow_deny": authz_package.AllowDeny.DENY,
                    "everyone": True,
                },
            ],
        },
    ],
)
def test_roompolicy_from_model(model_kwargs):
    model_kwargs = model_kwargs.copy()
    acl_entries_kwargs = model_kwargs.pop("acl_entries_kwargs", ())
    acl_entries = [
        models.ACLEntry(**(ACL_ENTRY_DEFAULTS | acl_entry_kwargs))
        for acl_entry_kwargs in acl_entries_kwargs
    ]
    if acl_entries:
        model_kwargs["acl_entries"] = acl_entries

    model = models.RoomPolicy(**(ROOM_POLICY_DEFAULTS | model_kwargs))
    found = authz_schema.RoomPolicy.from_model(model)

    assert found.default_allow_deny == model.default_allow_deny

    for f_entry, e_entry in zip(
        found.acl_entries,
        model.acl_entries,
        strict=True,
    ):
        assert f_entry.as_model == e_entry


@pytest.mark.parametrize("token", [None, {}, {"foo": "bar"}])
@pytest.mark.parametrize(
    "default_allow_deny",
    [
        authz_package.AllowDeny.ALLOW,
        authz_package.AllowDeny.DENY,
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
        authz_package.AllowDeny.ALLOW,
        authz_package.AllowDeny.DENY,
    ],
)
def test_roompolicy_check_token_w_acl_miss(default_allow_deny, token):
    policy = authz_schema.RoomPolicy(
        room_id=ROOM_ID,
        default_allow_deny=default_allow_deny,
    )
    _entry = authz_schema.ACLEntry(
        room_policy=policy,
        allow_deny=authz_package.AllowDeny.ALLOW,
    )

    found = policy.check_token(token)

    assert found == default_allow_deny


@pytest.mark.parametrize("token", [None, {}, {"foo": "bar"}])
@pytest.mark.parametrize(
    "default_allow_deny",
    [
        authz_package.AllowDeny.ALLOW,
        authz_package.AllowDeny.DENY,
    ],
)
def test_roompolicy_check_token_w_acl_hit(default_allow_deny, token):
    policy = authz_schema.RoomPolicy(
        room_id=ROOM_ID,
        default_allow_deny=default_allow_deny,
    )
    _entry = authz_schema.ACLEntry(
        room_policy=policy,
        allow_deny=authz_package.AllowDeny.ALLOW,
        everyone=True,
    )

    found = policy.check_token(token)

    assert found == authz_package.AllowDeny.ALLOW


@pytest.fixture
def the_room_policy():
    return authz_schema.RoomPolicy(
        room_id=ROOM_ID,
        default_allow_deny=authz_package.AllowDeny.DENY,
    )


@pytest.mark.parametrize(
    "model_kwargs",
    [
        {},
        {"allow_deny": authz_package.AllowDeny.ALLOW},
        {"everyone": True, "allow_deny": authz_package.AllowDeny.DENY},
        {"authenticated": True, "allow_deny": authz_package.AllowDeny.ALLOW},
        {
            "preferred_username": "phreddy",
            "allow_deny": authz_package.AllowDeny.ALLOW,
        },
        {
            "email": "phreddy@example.com",
            "allow_deny": authz_package.AllowDeny.ALLOW,
        },
    ],
)
def test_aclentry_from_model(the_session, the_room_policy, model_kwargs):
    model = models.ACLEntry(**(ACL_ENTRY_DEFAULTS | model_kwargs))
    found = authz_schema.ACLEntry.from_model(model)
    found.room_policy = the_room_policy

    the_session.add(the_room_policy)
    the_session.add(found)
    the_session.commit()

    assert found.as_model == model


@pytest.mark.parametrize("token", [None, {}, {"foo": "bar"}])
@pytest.mark.parametrize(
    "allow_deny",
    [
        authz_package.AllowDeny.ALLOW,
        authz_package.AllowDeny.DENY,
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
        authz_package.AllowDeny.ALLOW,
        authz_package.AllowDeny.DENY,
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
        authz_package.AllowDeny.ALLOW,
        authz_package.AllowDeny.DENY,
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
        authz_package.AllowDeny.ALLOW,
        authz_package.AllowDeny.DENY,
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
        authz_package.AllowDeny.ALLOW,
        authz_package.AllowDeny.DENY,
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


@pytest.mark.parametrize("init_schema", [None, False, True])
@mock.patch("sqlalchemy.create_engine")
@mock.patch("soliplex.authz.schema.metadata.create_all")
def test_get_engine(
    ca,
    ce,
    init_schema,
):
    kwargs = {}

    if init_schema is not None:
        kwargs["init_schema"] = init_schema

    found = authz_schema.get_engine(**kwargs)

    assert found is ce.return_value

    ce.assert_called_once_with(
        config_installation.SYNC_MEMORY_ENGINE_URL,
        json_serializer=util.serialize_sqla_json,
    )

    if init_schema:
        connection = ce.return_value.connect.return_value
        ca.assert_called_once_with(connection.__enter__.return_value)
    else:
        ca.assert_not_called()


@pytest.mark.parametrize("init_schema", [None, False, True])
@mock.patch("soliplex.authz.schema.get_engine")
def test_get_session(
    ge,
    init_schema,
):
    kwargs = {}

    if init_schema is not None:
        kwargs["init_schema"] = init_schema
        exp_kwargs = kwargs
    else:
        exp_kwargs = {"init_schema": False}

    with authz_schema.get_session(**kwargs) as session:
        assert isinstance(session, sqla_orm.Session)
        assert session.bind is ge.return_value

        ge.assert_called_once_with(
            engine_url=config_installation.SYNC_MEMORY_ENGINE_URL,
            **exp_kwargs,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("init_schema", [None, False, True])
@mock.patch("sqlalchemy.ext.asyncio.create_async_engine")
@mock.patch("soliplex.authz.schema.metadata.create_all")
async def test_get_async_engine(ca, cae, init_schema):
    kwargs = {}

    if init_schema:
        kwargs["init_schema"] = True

    found = await authz_schema.get_async_engine(**kwargs)

    assert found is cae.return_value

    cae.assert_called_once_with(
        config_installation.ASYNC_MEMORY_ENGINE_URL,
        json_serializer=util.serialize_sqla_json,
    )

    if init_schema:
        found.begin.assert_called_once_with()
        connection = found.begin.return_value.__aenter__.return_value
        connection.run_sync.assert_called_once_with(ca)
    else:
        found.begin.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("init_schema", [None, False, True])
@mock.patch("soliplex.authz.schema.get_async_engine")
async def test_get_async_session(gae, init_schema):
    kwargs = {}

    if init_schema is not None:
        kwargs["init_schema"] = init_schema
        exp_kwargs = kwargs
    else:
        exp_kwargs = {"init_schema": False}

    session_maker = await authz_schema.get_async_session(**kwargs)

    async with session_maker as session:
        assert isinstance(session, sqla_asyncio.AsyncSession)
        assert session.bind is gae.return_value

        gae.assert_called_once_with(
            engine_url=config_installation.ASYNC_MEMORY_ENGINE_URL,
            **exp_kwargs,
        )
