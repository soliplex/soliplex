import datetime
from unittest import mock

import pydantic
import pytest
import sqlalchemy
from sqlalchemy import orm as sqla_orm
from sqlalchemy.ext import asyncio as sqla_asyncio

from soliplex import authz
from soliplex import models
from soliplex import util
from soliplex.authz import schema as authz_schema
from soliplex.config import installation as config_installation

NOW = datetime.datetime.now(datetime.UTC)

EMAIL = "phreddy@example.com"
JSON_PATH = authz.token_field_json_path("email", EMAIL)

ROOM_ID = "test-room"

ACL_ENTRY_DEFAULTS = {
    "everyone": False,
    "authenticated": False,
    "preferred_username": None,
    "email": None,
    "json_path": None,
    "allow_deny": authz.AllowDeny.DENY,
}

ROOM_POLICY_DEFAULTS = {
    "room_id": ROOM_ID,
    "default_allow_deny": authz.AllowDeny.DENY,
    "acl_entries": [],
}


@mock.patch("datetime.UTC")
@mock.patch("datetime.datetime")
def test__timestamp(dt, utc):
    found = authz_schema._timestamp()

    assert found is dt.now.return_value

    dt.now.assert_called_once_with(utc)


def test_adminuser_ctor(the_session):
    admin_user = authz_schema.AdminUser(json_path=JSON_PATH)

    the_session.add(admin_user)
    the_session.commit()


def test_adminuser_ctor_invalid_json_path():
    with pytest.raises(authz.InvalidJSONPath):
        authz_schema.AdminUser(json_path="$[?(bogus")


@pytest.mark.parametrize(
    "w_json_path, w_token, exp",
    [
        # Email-shaped query matches the matching email claim.
        (JSON_PATH, {"email": EMAIL}, True),
        (JSON_PATH, {"email": "other@example.com"}, False),
        # A missing / empty token never matches.
        (JSON_PATH, None, False),
        # An arbitrary (non-email) query matches on its own field.
        ('$[?$.role == "admin"]', {"role": "admin"}, True),
        ('$[?$.role == "admin"]', {"role": "user"}, False),
    ],
)
def test_adminuser_check_token(w_json_path, w_token, exp):
    admin_user = authz_schema.AdminUser(json_path=w_json_path)

    assert admin_user.check_token(w_token) is exp


def test_roompolicy_ctor(the_session):
    policy = authz_schema.RoomPolicy(
        room_id=ROOM_ID,
    )

    the_session.add(policy)
    the_session.commit()

    assert policy.default_allow_deny == authz.AllowDeny.DENY


@pytest.mark.parametrize(
    "model_kwargs",
    [
        {},
        {"default_allow_deny": authz.AllowDeny.ALLOW},
        {
            "acl_entries_kwargs": [
                {
                    "allow_deny": authz.AllowDeny.ALLOW,
                    "authenticated": True,
                },
            ],
        },
        {
            "acl_entries_kwargs": [
                {
                    "allow_deny": authz.AllowDeny.ALLOW,
                    "email": "phreddy@example.com",
                },
                {
                    "allow_deny": authz.AllowDeny.DENY,
                    "everyone": True,
                },
            ],
        },
        {
            "acl_entries_kwargs": [
                {
                    "allow_deny": authz.AllowDeny.ALLOW,
                    "json_path": "$[?match($.foo, 'b.*z')]",
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


def test_roompolicy_as_unchecked_model(the_session):
    policy = authz_schema.RoomPolicy(
        room_id=ROOM_ID,
        default_allow_deny=authz.AllowDeny.ALLOW,
    )
    authz_schema.ACLEntry(
        room_policy=policy,
        allow_deny=authz.AllowDeny.DENY,
        everyone=True,
    )
    authz_schema.ACLEntry(
        room_policy=policy,
        allow_deny=authz.AllowDeny.ALLOW,
        json_path=JSON_PATH,
    )
    the_session.add(policy)
    the_session.commit()

    unchecked = policy.as_unchecked_model

    assert unchecked.room_id == ROOM_ID
    assert unchecked.default_allow_deny == authz.AllowDeny.ALLOW
    assert len(unchecked.acl_entries) == 2
    assert (
        models.ACLEntryUnchecked(
            allow_deny=authz.AllowDeny.DENY, everyone=True
        )
        in unchecked.acl_entries
    )
    assert (
        models.ACLEntryUnchecked(allow_deny=authz.AllowDeny.ALLOW, email=EMAIL)
        in unchecked.acl_entries
    )


@pytest.mark.parametrize("token", [None, {}, {"foo": "bar"}])
@pytest.mark.parametrize(
    "default_allow_deny",
    [
        authz.AllowDeny.ALLOW,
        authz.AllowDeny.DENY,
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
        authz.AllowDeny.ALLOW,
        authz.AllowDeny.DENY,
    ],
)
def test_roompolicy_check_token_w_acl_miss(default_allow_deny, token):
    policy = authz_schema.RoomPolicy(
        room_id=ROOM_ID,
        default_allow_deny=default_allow_deny,
    )
    _entry = authz_schema.ACLEntry(
        room_policy=policy,
        allow_deny=authz.AllowDeny.ALLOW,
    )

    found = policy.check_token(token)

    assert found == default_allow_deny


@pytest.mark.parametrize("token", [None, {}, {"foo": "bar"}])
@pytest.mark.parametrize(
    "default_allow_deny",
    [
        authz.AllowDeny.ALLOW,
        authz.AllowDeny.DENY,
    ],
)
def test_roompolicy_check_token_w_acl_hit(default_allow_deny, token):
    policy = authz_schema.RoomPolicy(
        room_id=ROOM_ID,
        default_allow_deny=default_allow_deny,
    )
    _entry = authz_schema.ACLEntry(
        room_policy=policy,
        allow_deny=authz.AllowDeny.ALLOW,
        everyone=True,
    )

    found = policy.check_token(token)

    assert found == authz.AllowDeny.ALLOW


@pytest.fixture
def the_room_policy():
    return authz_schema.RoomPolicy(
        room_id=ROOM_ID,
        default_allow_deny=authz.AllowDeny.DENY,
    )


def test_aclentry_rejects_invalid_jsonpath(the_room_policy):
    with pytest.raises(authz.InvalidJSONPath):
        authz_schema.ACLEntry(
            room_policy=the_room_policy,
            allow_deny=authz.AllowDeny.ALLOW,
            json_path="not a path",
        )


@pytest.mark.parametrize(
    "model_kwargs",
    [
        {"everyone": True, "allow_deny": authz.AllowDeny.DENY},
        {"authenticated": True, "allow_deny": authz.AllowDeny.ALLOW},
        {
            "preferred_username": "phreddy",
            "allow_deny": authz.AllowDeny.ALLOW,
        },
        {
            "email": "phreddy@example.com",
            "allow_deny": authz.AllowDeny.ALLOW,
        },
        {
            "json_path": "$[?match($.foo, 'b.*z')]",
            "allow_deny": authz.AllowDeny.ALLOW,
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


STALE_JSON_PATH = "$[?stale_filter_func($.email)]"


def _seed_stale_aclentry(the_session, the_room_policy):
    """Plant an ACL entry whose stored 'json_path' no longer compiles.

    The ORM's 'json_path' validator rejects a non-compiling query on
    insert, so seed a valid placeholder query, then rewrite it to the
    non-compiling value with a raw UPDATE (which skips '@validates') and
    refresh the instance from the row.
    """
    entry = authz_schema.ACLEntry(
        room_policy=the_room_policy,
        allow_deny=authz.AllowDeny.ALLOW,
        json_path=JSON_PATH,
    )
    the_session.add(the_room_policy)
    the_session.add(entry)
    the_session.commit()
    the_session.execute(
        sqlalchemy.text(
            "UPDATE room_acl_entries SET json_path = :stale "
            "WHERE json_path = :placeholder"
        ),
        {"stale": STALE_JSON_PATH, "placeholder": JSON_PATH},
    )
    the_session.commit()
    the_session.refresh(entry)
    return entry


def test_aclentry_as_model_rejects_stale_json_path(
    the_session, the_room_policy
):
    entry = _seed_stale_aclentry(the_session, the_room_policy)

    with pytest.raises(pydantic.ValidationError):
        _ = entry.as_model


@pytest.mark.parametrize(
    "model_kwargs",
    [
        {"everyone": True, "allow_deny": authz.AllowDeny.DENY},
        {"authenticated": True, "allow_deny": authz.AllowDeny.ALLOW},
        {
            "preferred_username": "phreddy",
            "allow_deny": authz.AllowDeny.ALLOW,
        },
        {
            "email": "phreddy@example.com",
            "allow_deny": authz.AllowDeny.ALLOW,
        },
        {
            "json_path": "$[?match($.foo, 'b.*z')]",
            "allow_deny": authz.AllowDeny.ALLOW,
        },
    ],
)
def test_aclentry_as_unchecked_model(
    the_session, the_room_policy, model_kwargs
):
    found = authz_schema.ACLEntry.from_model(
        models.ACLEntry(**(ACL_ENTRY_DEFAULTS | model_kwargs))
    )
    found.room_policy = the_room_policy
    the_session.add(the_room_policy)
    the_session.add(found)
    the_session.commit()

    unchecked = found.as_unchecked_model

    assert unchecked == models.ACLEntryUnchecked(
        **(ACL_ENTRY_DEFAULTS | model_kwargs)
    )


def test_aclentry_as_unchecked_model_tolerates_stale_json_path(
    the_session, the_room_policy
):
    entry = _seed_stale_aclentry(the_session, the_room_policy)

    unchecked = entry.as_unchecked_model

    assert unchecked.json_path == STALE_JSON_PATH


@pytest.mark.parametrize(
    "kwargs",
    [
        {},  # zero discriminators
        {"everyone": True, "json_path": "$.foo"},  # two discriminators
    ],
)
def test_aclentry_flush_requires_exactly_one_discriminator(
    the_session, the_room_policy, kwargs
):
    entry = authz_schema.ACLEntry(
        room_policy=the_room_policy,
        allow_deny=authz.AllowDeny.ALLOW,
        **kwargs,
    )
    the_session.add(the_room_policy)
    the_session.add(entry)

    with pytest.raises(authz.ExactlyOneDiscriminator):
        the_session.commit()


@pytest.mark.parametrize("token", [None, {}, {"foo": "bar"}])
@pytest.mark.parametrize(
    "allow_deny",
    [
        authz.AllowDeny.ALLOW,
        authz.AllowDeny.DENY,
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
        authz.AllowDeny.ALLOW,
        authz.AllowDeny.DENY,
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
        authz.AllowDeny.ALLOW,
        authz.AllowDeny.DENY,
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
        ({"foo": "bar"}, False),
        ({"foo": "baz"}, True),
        ({"foo": "baloonz"}, True),
    ],
)
@pytest.mark.parametrize(
    "allow_deny",
    [
        authz.AllowDeny.ALLOW,
        authz.AllowDeny.DENY,
    ],
)
def test_aclentry_check_token_w_jsonpath(
    the_room_policy,
    allow_deny,
    token,
    matched,
):
    entry = authz_schema.ACLEntry(
        room_policy=the_room_policy,
        allow_deny=allow_deny,
        json_path="$[?match($.foo, 'b.*z')]",
    )

    found = entry.check_token(token)

    if matched:
        assert found is allow_deny
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
        authz.AllowDeny.ALLOW,
        authz.AllowDeny.DENY,
    ],
)
def test_aclentry_check_token_w_preferred_username(
    the_room_policy,
    allow_deny,
    token,
    matched,
):
    entry = authz_schema.ACLEntry.from_model(
        models.ACLEntry(allow_deny=allow_deny, preferred_username="hit")
    )
    entry.room_policy = the_room_policy

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
        authz.AllowDeny.ALLOW,
        authz.AllowDeny.DENY,
    ],
)
def test_aclentry_check_token_w_email(
    the_room_policy,
    allow_deny,
    token,
    matched,
):
    entry = authz_schema.ACLEntry.from_model(
        models.ACLEntry(allow_deny=allow_deny, email="hit@example.com")
    )
    entry.room_policy = the_room_policy

    found = entry.check_token(token)

    if matched:
        assert found == allow_deny
    else:
        assert found is None


@pytest.mark.parametrize("init_schema", [None, False, True])
@mock.patch("sqlalchemy.event.listens_for")
@mock.patch("sqlalchemy.create_engine")
@mock.patch("soliplex.authz.schema.metadata.create_all")
def test_get_engine(
    ca,
    ce,
    lf,
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

    # A 'connect' listener is registered to enable SQLite foreign keys.
    lf.assert_called_once_with(ce.return_value, "connect")

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
