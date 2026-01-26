import datetime
from unittest import mock

import pytest
import pytest_asyncio
import sqlalchemy
from sqlalchemy import orm as sqla_orm
from sqlalchemy.ext import asyncio as sqla_asyncio

from soliplex import authz as authz_package
from soliplex import config
from soliplex import models
from soliplex.authz import schema as authz_schema

NOW = datetime.datetime.now(datetime.UTC)

EMAIL = "phreddy@example.com"
USER_TOKEN = {
    "email": EMAIL,
}

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


@pytest.fixture
def the_engine():
    engine = sqlalchemy.create_engine(config.SYNC_MEMORY_ENGINE_URL)

    yield engine

    engine.dispose()


@pytest.fixture
def the_session(the_engine):
    with the_engine.connect() as connection:
        authz_schema.Base.metadata.create_all(connection)

    assert connection.closed

    with sqla_orm.Session(bind=the_engine) as session:
        yield session


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


@pytest.fixture
def faux_sqlaa_session():
    return mock.create_autospec(
        sqla_asyncio.AsyncSession,
    )


@pytest.mark.anyio
async def test_authorizationpolicy_session(faux_sqlaa_session):
    ap = authz_schema.AuthorizationPolicy(faux_sqlaa_session)
    begin = faux_sqlaa_session.begin

    async with ap.session as session:
        assert session is faux_sqlaa_session

        begin.assert_called_once_with()
        begin.return_value.__aenter__.assert_called_once_with()
        begin.return_value.__aexit__.assert_not_called()

    begin.return_value.__aenter__.assert_called_once_with()


@pytest_asyncio.fixture()
async def the_async_engine():  # pragma: NO COVER
    engine = sqla_asyncio.create_async_engine(
        config.ASYNC_MEMORY_ENGINE_URL,
    )
    async with engine.begin() as connection:
        await connection.run_sync(authz_schema.Base.metadata.create_all)

    yield engine

    await engine.dispose()


@pytest_asyncio.fixture()
async def the_async_session(the_async_engine):  # pragma: NO COVER
    session = sqla_asyncio.AsyncSession(bind=the_async_engine)
    yield session
    await session.close()


@pytest.mark.asyncio
async def test_authorizationpolicy_crud_admin_user(the_async_session):
    ap = authz_schema.AuthorizationPolicy(the_async_session)

    found = await ap.list_admin_users()

    assert found == []

    await ap.add_admin_user(email=EMAIL)
    user = await authz_schema._find_admin_user(
        email=EMAIL,
        session=the_async_session,
    )
    assert user is not None
    await the_async_session.commit()

    found = await ap.list_admin_users()
    assert found == [EMAIL]
    await the_async_session.commit()

    with pytest.raises(authz_schema.AdminUserExists):
        await ap.add_admin_user(email=EMAIL)

    no_dupe = await authz_schema._find_admin_user(
        email=EMAIL,
        session=the_async_session,
    )
    assert no_dupe is user
    await the_async_session.commit()

    found = await ap.list_admin_users()
    assert found == [EMAIL]
    await the_async_session.commit()

    await ap.remove_admin_user(email=EMAIL)
    gone = await authz_schema._find_admin_user(
        email=EMAIL,
        session=the_async_session,
    )
    assert gone is None
    await the_async_session.commit()

    found = await ap.list_admin_users()
    assert found == []
    await the_async_session.commit()

    with pytest.raises(authz_schema.NoSuchAdminUser):
        await ap.remove_admin_user(email=EMAIL)


@pytest.mark.asyncio
async def test_authorizationpolicy_check_admin_access(the_async_session):
    ap = authz_schema.AuthorizationPolicy(the_async_session)

    assert not await ap.check_admin_access(USER_TOKEN)

    await ap.add_admin_user(email=EMAIL)

    assert await ap.check_admin_access(USER_TOKEN)

    await ap.remove_admin_user(email=EMAIL)

    assert not await ap.check_admin_access(USER_TOKEN)


@pytest.mark.asyncio
async def test_authorizationpolicy_check_room_access(the_async_session):
    ap = authz_schema.AuthorizationPolicy(the_async_session)

    # No policy -> public room
    assert await ap.check_room_access(ROOM_ID, None)

    # Policy w/ deny as default, no ACL entries
    denier = authz_schema.RoomPolicy(room_id=ROOM_ID)
    the_async_session.add(denier)
    await the_async_session.commit()

    assert not await ap.check_room_access(ROOM_ID, None)

    allower = authz_schema.ACLEntry(
        room_policy=denier,
        allow_deny=authz_package.AllowDeny.ALLOW,
        everyone=True,
    )
    the_async_session.add(allower)
    await the_async_session.commit()

    assert await ap.check_room_access(ROOM_ID, None)


@pytest.mark.asyncio
async def test_authorizationpolicy_filter_room_ids(the_async_session):
    ap = authz_schema.AuthorizationPolicy(the_async_session)

    room_ids = [ROOM_ID]

    # No policy -> public room
    assert await ap.filter_room_ids(room_ids, None) == room_ids

    # Policy w/ deny as default, no ACL entries
    denier = authz_schema.RoomPolicy(room_id=ROOM_ID)
    the_async_session.add(denier)
    await the_async_session.commit()

    assert await ap.filter_room_ids(room_ids, None) == []

    allower = authz_schema.ACLEntry(
        room_policy=denier,
        allow_deny=authz_package.AllowDeny.ALLOW,
        everyone=True,
    )
    the_async_session.add(allower)
    await the_async_session.commit()

    assert await ap.filter_room_ids(room_ids, None) == room_ids


@pytest.mark.asyncio
async def test_authorizationpolicy_room_policy_crud_not_admin(
    the_async_session,
):
    ap = authz_schema.AuthorizationPolicy(the_async_session)

    with pytest.raises(authz_schema.NotAdminUser):
        await ap.get_room_policy(ROOM_ID, USER_TOKEN)

    acl_entry_model = models.ACLEntry(
        allow_deny=authz_package.AllowDeny.ALLOW,
        everyone=True,
    )
    policy_model = models.RoomPolicy(
        room_id=ROOM_ID,
        acl_entries=[acl_entry_model],
    )

    with pytest.raises(authz_schema.NotAdminUser):
        await ap.update_room_policy(ROOM_ID, policy_model, USER_TOKEN)

    with pytest.raises(authz_schema.NotAdminUser):
        await ap.delete_room_policy(ROOM_ID, USER_TOKEN)


@pytest.mark.asyncio
async def test_authorizationpolicy_room_policy_crud(the_async_session):
    ap = authz_schema.AuthorizationPolicy(the_async_session)

    await ap.add_admin_user(email=EMAIL)
    await the_async_session.commit()

    # No policy -> public room
    policy = await ap.get_room_policy(ROOM_ID, USER_TOKEN)
    assert policy is None

    acl_entry_model = models.ACLEntry(
        allow_deny=authz_package.AllowDeny.ALLOW,
        everyone=True,
    )
    policy_model = models.RoomPolicy(
        room_id=ROOM_ID,
        acl_entries=[acl_entry_model],
    )
    await ap.update_room_policy(ROOM_ID, policy_model, USER_TOKEN)
    await the_async_session.commit()

    after = await ap.get_room_policy(ROOM_ID, USER_TOKEN)
    assert after == policy_model
    await the_async_session.commit()

    new_acl_entry_model = models.ACLEntry(
        allow_deny=authz_package.AllowDeny.ALLOW,
        preferred_username="phreddy",
    )
    new_policy_model = policy_model.model_copy(
        update={"acl_entries": [new_acl_entry_model]},
    )
    await ap.update_room_policy(ROOM_ID, new_policy_model, USER_TOKEN)
    await the_async_session.commit()

    policy = await ap.get_room_policy(ROOM_ID, USER_TOKEN)
    assert policy == new_policy_model
    await the_async_session.commit()

    await ap.delete_room_policy(ROOM_ID, USER_TOKEN)
    await the_async_session.commit()

    gone = await ap.get_room_policy(ROOM_ID, USER_TOKEN)
    assert gone is None
    await the_async_session.commit()

    await ap.delete_room_policy(ROOM_ID, USER_TOKEN)
    await the_async_session.commit()


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
