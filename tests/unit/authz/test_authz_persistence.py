import datetime
from unittest import mock

import pytest
from sqlalchemy import sql as sqla_sql
from sqlalchemy.ext import asyncio as sqla_asyncio

from soliplex import authz
from soliplex import loggers
from soliplex import models
from soliplex.authz import persistence as authz_persistence
from soliplex.authz import schema as authz_schema

EMAIL = "phreddy@example.com"
JSON_PATH = authz.token_field_json_path("email", EMAIL)
ROLE_JSON_PATH = '$[?$.role == "admin"]'
INVALID_JSON_PATH = "$[?@.role"  # unbalanced -- does not compile
USER_TOKEN = {
    "email": EMAIL,
}
ROOM_ID = "test-room"
CLAIMS = {"source": "test", "actor": EMAIL}


@pytest.fixture
def faux_sqlaa_session():
    return mock.create_autospec(
        sqla_asyncio.AsyncSession,
    )


def _admin_user_policy(session):
    """An 'AdminUserPolicy' whose '_audit' is a mock, for emit assertions."""
    policy = authz_persistence.AdminUserPolicy(session, CLAIMS)
    policy._audit = mock.create_autospec(loggers.AdminUsersAuditLog)
    return policy


def _room_authz_policy(session):
    """A 'RoomAuthorizationPolicy' whose audit logs are mocks."""
    policy = authz_persistence.RoomAuthorizationPolicy(session, CLAIMS)
    policy._audit = mock.create_autospec(loggers.RoomAuthzAuditLog)
    policy._access_audit = mock.create_autospec(loggers.RoomAccessAuditLog)
    return policy


@pytest.mark.anyio
async def test_admin_user_session(faux_sqlaa_session):
    aup = authz_persistence.AdminUserPolicy(faux_sqlaa_session, CLAIMS)

    async with aup.session as session:
        entered = session

    # The session property is a passthrough: it yields the caller-owned
    # session unchanged and never opens its own transaction. The session
    # owner owns the commit boundary.
    assert entered is faux_sqlaa_session
    faux_sqlaa_session.begin.assert_not_called()


def test_admin_user_policy_builds_audit_log():
    policy = authz_persistence.AdminUserPolicy(object(), CLAIMS)

    assert isinstance(policy._audit, loggers.AdminUsersAuditLog)
    assert policy._audit.extra["claims"] == CLAIMS


@pytest.mark.asyncio
async def test_list_admin_user_discriminators(the_async_session):
    aup = _admin_user_policy(the_async_session)
    the_async_session.add(authz_schema.AdminUser(json_path=JSON_PATH))
    the_async_session.add(authz_schema.AdminUser(json_path=ROLE_JSON_PATH))

    found = await aup.list_admin_user_discriminators()

    assert found == [JSON_PATH, ROLE_JSON_PATH]
    aup._audit.admin_users_listed.assert_called_once_with()


@pytest.mark.asyncio
async def test_add_admin_user_discriminator(the_async_session):
    aup = _admin_user_policy(the_async_session)

    await aup.add_admin_user_discriminator(ROLE_JSON_PATH)

    aup._audit.admin_user_added.assert_called_once_with(ROLE_JSON_PATH)
    found = await aup.list_admin_user_discriminators()
    assert found == [ROLE_JSON_PATH]


@pytest.mark.asyncio
async def test_add_admin_user_discriminator_already_exists(the_async_session):
    aup = _admin_user_policy(the_async_session)
    the_async_session.add(authz_schema.AdminUser(json_path=ROLE_JSON_PATH))

    with pytest.raises(authz.AdminUserExists):
        await aup.add_admin_user_discriminator(ROLE_JSON_PATH)

    ((args, kwargs),) = aup._audit.admin_user_add_failed.call_args_list
    (arg,) = args
    assert arg == ROLE_JSON_PATH
    assert list(kwargs) == ["reason"]
    msg = kwargs["reason"]
    assert msg.startswith("Admin user already exists with json_path")


@pytest.mark.asyncio
async def test_remove_admin_user_discriminator(the_async_session):
    aup = _admin_user_policy(the_async_session)
    the_async_session.add(authz_schema.AdminUser(json_path=ROLE_JSON_PATH))

    await aup.remove_admin_user_discriminator(ROLE_JSON_PATH)

    aup._audit.admin_user_removed.assert_called_once_with(ROLE_JSON_PATH)
    found = await aup.list_admin_user_discriminators()
    assert found == []


@pytest.mark.asyncio
async def test_remove_admin_user_discriminator_absent(the_async_session):
    aup = _admin_user_policy(the_async_session)

    with pytest.raises(authz.NoSuchAdminUser):
        await aup.remove_admin_user_discriminator(ROLE_JSON_PATH)

    ((args, kwargs),) = aup._audit.admin_user_remove_failed.call_args_list
    (arg,) = args
    assert arg == ROLE_JSON_PATH
    assert list(kwargs) == ["reason"]
    msg = kwargs["reason"]
    assert msg.startswith("No admin user exists with json_path")


@pytest.mark.asyncio
async def test_remove_admin_user_discriminator_invalid_json_path(
    the_async_session,
):
    aup = _admin_user_policy(the_async_session)
    # Seed via a core INSERT so the stored value bypasses the ORM
    # '@validates' hook -- mimicking an entry whose 'json_path' no
    # longer compiles (e.g. a removed meta-config filter function).
    await the_async_session.execute(
        sqla_sql.insert(authz_schema.AdminUser.__table__).values(
            json_path=INVALID_JSON_PATH,
            created=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        )
    )

    await aup.remove_admin_user_discriminator(INVALID_JSON_PATH)

    aup._audit.admin_user_removed.assert_called_once_with(INVALID_JSON_PATH)
    found = await aup.list_admin_user_discriminators()
    assert found == []


@pytest.mark.asyncio
async def test_clear_admin_user_discriminators(the_async_session):
    aup = _admin_user_policy(the_async_session)
    the_async_session.add(authz_schema.AdminUser(json_path=JSON_PATH))
    the_async_session.add(authz_schema.AdminUser(json_path=ROLE_JSON_PATH))

    await aup.clear_admin_user_discriminators()

    aup._audit.admin_users_cleared.assert_called_once_with()
    found = await aup.list_admin_user_discriminators()
    assert found == []


@pytest.mark.asyncio
async def test_clear_admin_user_discriminators_empty(the_async_session):
    aup = _admin_user_policy(the_async_session)

    await aup.clear_admin_user_discriminators()

    aup._audit.admin_users_cleared.assert_called_once_with()
    found = await aup.list_admin_user_discriminators()
    assert found == []


@pytest.mark.asyncio
async def test_admin_user_crud(the_async_session):
    # The deprecated 'email'-keyed aliases delegate to the
    # '*_discriminator' methods, storing the canonical email JSONPath.
    aup = _admin_user_policy(the_async_session)

    found = await aup.list_admin_users()

    aup._audit.admin_users_listed.assert_called_once_with()
    aup._audit.admin_users_listed.reset_mock()

    assert found == []

    await aup.add_admin_user(email=EMAIL)
    user = await authz_persistence._find_admin_user_by_json_path(
        json_path=JSON_PATH,
        session=the_async_session,
    )
    assert user is not None

    aup._audit.admin_user_added.assert_called_once_with(JSON_PATH)
    aup._audit.admin_user_added.reset_mock()

    found = await aup.list_admin_users()
    assert found == [JSON_PATH]

    aup._audit.admin_users_listed.assert_called_once_with()
    aup._audit.admin_users_listed.reset_mock()

    with pytest.raises(authz.AdminUserExists):
        await aup.add_admin_user(email=EMAIL)

    no_dupe = await authz_persistence._find_admin_user_by_json_path(
        json_path=JSON_PATH,
        session=the_async_session,
    )
    assert no_dupe is user

    ((args, kwargs),) = aup._audit.admin_user_add_failed.call_args_list
    (arg,) = args
    assert arg == JSON_PATH
    assert list(kwargs) == ["reason"]
    msg = kwargs["reason"]
    assert msg.startswith("Admin user already exists with json_path")
    aup._audit.admin_user_add_failed.reset_mock()

    found = await aup.list_admin_users()
    assert found == [JSON_PATH]

    aup._audit.admin_users_listed.assert_called_once_with()
    aup._audit.admin_users_listed.reset_mock()

    await aup.remove_admin_user(email=EMAIL)
    gone = await authz_persistence._find_admin_user_by_json_path(
        json_path=JSON_PATH,
        session=the_async_session,
    )
    assert gone is None

    aup._audit.admin_user_removed.assert_called_once_with(JSON_PATH)
    aup._audit.admin_user_removed.reset_mock()

    found = await aup.list_admin_users()
    assert found == []

    aup._audit.admin_users_listed.assert_called_once_with()
    aup._audit.admin_users_listed.reset_mock()

    with pytest.raises(authz.NoSuchAdminUser):
        await aup.remove_admin_user(email=EMAIL)

    ((args, kwargs),) = aup._audit.admin_user_remove_failed.call_args_list
    (arg,) = args
    assert arg == JSON_PATH
    assert list(kwargs) == ["reason"]
    msg = kwargs["reason"]
    assert msg.startswith("No admin user exists with json_path")
    aup._audit.admin_user_remove_failed.reset_mock()


# A representative gated operation; 'check_admin_access' forwards these to
# the audit record verbatim, so the exact values are arbitrary here.
ADMIN_RESOURCE = loggers.AUDIT_RESOURCE_ROOM_POLICY
ADMIN_ACTION = loggers.AUDIT_ACTION_READ


@pytest.mark.asyncio
async def test_admin_user_check_admin_access(the_async_session):
    aup = _admin_user_policy(the_async_session)

    assert not await aup.check_admin_access(
        USER_TOKEN, resource=ADMIN_RESOURCE, action=ADMIN_ACTION
    )

    aup._audit.admin_access_denied.assert_called_once_with(
        resource=ADMIN_RESOURCE, action=ADMIN_ACTION
    )
    aup._audit.admin_access_denied.reset_mock()

    await aup.add_admin_user(email=EMAIL)

    aup._audit.admin_user_added.assert_called_once_with(JSON_PATH)
    aup._audit.admin_user_added.reset_mock()

    assert await aup.check_admin_access(
        USER_TOKEN, resource=ADMIN_RESOURCE, action=ADMIN_ACTION
    )

    aup._audit.admin_access_allowed.assert_called_once_with(
        resource=ADMIN_RESOURCE, action=ADMIN_ACTION
    )
    aup._audit.admin_access_allowed.reset_mock()

    await aup.remove_admin_user(email=EMAIL)

    aup._audit.admin_user_removed.assert_called_once_with(JSON_PATH)
    aup._audit.admin_user_removed.reset_mock()

    assert not await aup.check_admin_access(
        USER_TOKEN, resource=ADMIN_RESOURCE, action=ADMIN_ACTION
    )

    aup._audit.admin_access_denied.assert_called_once_with(
        resource=ADMIN_RESOURCE, action=ADMIN_ACTION
    )
    aup._audit.admin_access_denied.reset_mock()


@pytest.mark.asyncio
async def test_admin_user_check_admin_access_json_path(
    the_async_session,
):
    aup = _admin_user_policy(the_async_session)

    # An admin keyed by a non-email JSONPath query (e.g. a role claim),
    # as produced by 'admin-users add --json-path'.
    the_async_session.add(
        authz_schema.AdminUser(json_path='$[?$.role == "admin"]'),
    )

    assert await aup.check_admin_access(
        {"role": "admin"}, resource=ADMIN_RESOURCE, action=ADMIN_ACTION
    )

    aup._audit.admin_access_allowed.assert_called_once_with(
        resource=ADMIN_RESOURCE, action=ADMIN_ACTION
    )
    aup._audit.admin_access_allowed.reset_mock()

    assert not await aup.check_admin_access(
        {"role": "user"}, resource=ADMIN_RESOURCE, action=ADMIN_ACTION
    )

    aup._audit.admin_access_denied.assert_called_once_with(
        resource=ADMIN_RESOURCE, action=ADMIN_ACTION
    )
    aup._audit.admin_access_denied.reset_mock()

    # A role-keyed admin is not matched by an unrelated email token.
    assert not await aup.check_admin_access(
        USER_TOKEN, resource=ADMIN_RESOURCE, action=ADMIN_ACTION
    )

    aup._audit.admin_access_denied.assert_called_once_with(
        resource=ADMIN_RESOURCE, action=ADMIN_ACTION
    )
    aup._audit.admin_access_denied.reset_mock()

    # A non-email admin surfaces as its raw JSONPath query, not an email.
    listed = await aup.list_admin_users()
    assert listed == ['$[?$.role == "admin"]']

    aup._audit.admin_users_listed.assert_called_once_with()
    aup._audit.admin_users_listed.reset_mock()


def test_room_authz_policy_builds_audit_log():
    policy = authz_persistence.RoomAuthorizationPolicy(object(), CLAIMS)

    assert isinstance(policy._audit, loggers.RoomAuthzAuditLog)
    assert policy._audit.extra["claims"] == CLAIMS
    assert isinstance(policy._access_audit, loggers.RoomAccessAuditLog)
    assert policy._access_audit.extra["claims"] == CLAIMS


@pytest.mark.asyncio
async def test_room_authz_check_room_access_public(the_async_session):
    rap = _room_authz_policy(the_async_session)

    granted = await rap.check_room_access(ROOM_ID, None)

    assert granted
    rap._access_audit.room_access_allowed.assert_called_once_with(ROOM_ID)
    rap._access_audit.room_access_denied.assert_not_called()
    # The room-policy CRUD audit log is not touched by an access check.
    assert rap._audit.method_calls == []


@pytest.mark.asyncio
async def test_room_authz_check_room_access_denied(the_async_session):
    rap = _room_authz_policy(the_async_session)
    # Policy w/ deny as default, no ACL entries.
    the_async_session.add(authz_schema.RoomPolicy(room_id=ROOM_ID))

    granted = await rap.check_room_access(ROOM_ID, None)

    assert not granted
    rap._access_audit.room_access_denied.assert_called_once_with(ROOM_ID)
    rap._access_audit.room_access_allowed.assert_not_called()
    assert rap._audit.method_calls == []


@pytest.mark.asyncio
async def test_room_authz_check_room_access_allowed(the_async_session):
    rap = _room_authz_policy(the_async_session)
    denier = authz_schema.RoomPolicy(room_id=ROOM_ID)
    the_async_session.add(denier)
    the_async_session.add(
        authz_schema.ACLEntry(
            room_policy=denier,
            allow_deny=authz.AllowDeny.ALLOW,
            everyone=True,
        )
    )

    granted = await rap.check_room_access(ROOM_ID, None)

    assert granted
    rap._access_audit.room_access_allowed.assert_called_once_with(ROOM_ID)
    rap._access_audit.room_access_denied.assert_not_called()
    assert rap._audit.method_calls == []


@pytest.mark.asyncio
async def test_room_authz_filter_room_ids(the_async_session):
    rap = _room_authz_policy(the_async_session)

    room_ids = [ROOM_ID]

    # No policy -> public room
    assert await rap.filter_room_ids(room_ids, None) == room_ids

    # Policy w/ deny as default, no ACL entries
    denier = authz_schema.RoomPolicy(room_id=ROOM_ID)
    the_async_session.add(denier)

    assert await rap.filter_room_ids(room_ids, None) == []

    allower = authz_schema.ACLEntry(
        room_policy=denier,
        allow_deny=authz.AllowDeny.ALLOW,
        everyone=True,
    )
    the_async_session.add(allower)

    assert await rap.filter_room_ids(room_ids, None) == room_ids

    # The hot end-user access path is deliberately not audited.
    assert rap._audit.method_calls == []


@pytest.mark.asyncio
async def test_room_authz_policy_crud(the_async_session):
    rap = _room_authz_policy(the_async_session)

    # No policy -> public room
    policy = await rap.get_room_policy(ROOM_ID)
    assert policy is None

    rap._audit.room_policy_read.assert_called_once_with(ROOM_ID)
    rap._audit.room_policy_read.reset_mock()

    acl_entry_model = models.ACLEntry(
        allow_deny=authz.AllowDeny.ALLOW,
        everyone=True,
    )
    policy_model = models.RoomPolicy(
        room_id=ROOM_ID,
        acl_entries=[acl_entry_model],
    )
    await rap.update_room_policy(ROOM_ID, policy_model)

    rap._audit.room_policy_updated.assert_called_once_with(ROOM_ID)
    rap._audit.room_policy_updated.reset_mock()

    after = await rap.get_room_policy(ROOM_ID)
    assert after == policy_model

    rap._audit.room_policy_read.assert_called_once_with(ROOM_ID)
    rap._audit.room_policy_read.reset_mock()

    new_acl_entry_model = models.ACLEntry(
        allow_deny=authz.AllowDeny.ALLOW,
        preferred_username="phreddy",
    )
    new_policy_model = policy_model.model_copy(
        update={"acl_entries": [new_acl_entry_model]},
    )
    await rap.update_room_policy(ROOM_ID, new_policy_model)

    rap._audit.room_policy_updated.assert_called_once_with(ROOM_ID)
    rap._audit.room_policy_updated.reset_mock()

    policy = await rap.get_room_policy(ROOM_ID)
    assert policy == new_policy_model

    rap._audit.room_policy_read.assert_called_once_with(ROOM_ID)
    rap._audit.room_policy_read.reset_mock()

    await rap.delete_room_policy(ROOM_ID)

    rap._audit.room_policy_deleted.assert_called_once_with(ROOM_ID)
    rap._audit.room_policy_deleted.reset_mock()

    gone = await rap.get_room_policy(ROOM_ID)
    assert gone is None

    rap._audit.room_policy_read.assert_called_once_with(ROOM_ID)
    rap._audit.room_policy_read.reset_mock()

    await rap.delete_room_policy(ROOM_ID)

    rap._audit.room_policy_deleted.assert_called_once_with(ROOM_ID)
    rap._audit.room_policy_deleted.reset_mock()


ALLOW = authz.AllowDeny.ALLOW
DENY = authz.AllowDeny.DENY
STALE_JSON_PATH = "$[?stale_filter_func($.email)]"


def _orm_entry(
    allow_deny, *, everyone=False, authenticated=False, json_path=None
):
    return authz_schema.ACLEntry(
        allow_deny=allow_deny,
        everyone=everyone,
        authenticated=authenticated,
        json_path=json_path,
    )


async def _seed_policy(session, *, default=DENY, entries=()):
    policy = authz_schema.RoomPolicy(
        room_id=ROOM_ID, default_allow_deny=default
    )
    session.add(policy)
    for entry in entries:
        entry.room_policy = policy
        session.add(entry)
    return policy


async def _seed_stale_entry(session, *, allow_deny=ALLOW):
    await _seed_policy(
        session,
        default=DENY,
        entries=[_orm_entry(allow_deny, json_path=JSON_PATH)],
    )
    # Flush so the entry is a persistent row (not just pending state)
    # before the raw UPDATE corrupts its 'json_path' out from under the
    # ORM '@validates' hook. This is ORM setup for the stale-value
    # scenario, not a transaction-boundary commit: the enclosing
    # session still owns the (single) commit.
    await session.flush()
    await session.execute(
        sqla_sql.text(
            "UPDATE room_acl_entries SET json_path = :stale "
            "WHERE json_path = :placeholder"
        ),
        {"stale": STALE_JSON_PATH, "placeholder": JSON_PATH},
    )
    session.expire_all()


@pytest.mark.asyncio
async def test_get_room_policy_unchecked_absent(the_async_session):
    rap = _room_authz_policy(the_async_session)

    found = await rap.get_room_policy_unchecked(ROOM_ID)

    assert found is None
    rap._audit.room_policy_read.assert_called_once_with(ROOM_ID)


@pytest.mark.asyncio
async def test_get_room_policy_unchecked_tolerates_stale_json_path(
    the_async_session,
):
    rap = _room_authz_policy(the_async_session)
    await _seed_stale_entry(the_async_session)

    found = await rap.get_room_policy_unchecked(ROOM_ID)

    assert isinstance(found, models.RoomPolicyUnchecked)
    assert [entry.json_path for entry in found.acl_entries] == [
        STALE_JSON_PATH
    ]
    rap._audit.room_policy_read.assert_called_once_with(ROOM_ID)


@pytest.mark.asyncio
async def test_list_room_policies_empty(the_async_session):
    rap = _room_authz_policy(the_async_session)

    found = await rap.list_room_policies()

    assert found == []
    rap._audit.room_policies_listed.assert_called_once_with()


@pytest.mark.asyncio
async def test_list_room_policies(the_async_session):
    rap = _room_authz_policy(the_async_session)
    the_async_session.add(
        authz_schema.RoomPolicy(room_id="alpha", default_allow_deny=ALLOW)
    )
    the_async_session.add(
        authz_schema.RoomPolicy(room_id="beta", default_allow_deny=DENY)
    )

    found = await rap.list_room_policies()

    assert all(
        isinstance(policy, models.RoomPolicyUnchecked) for policy in found
    )
    assert {policy.room_id: policy.default_allow_deny for policy in found} == {
        "alpha": ALLOW,
        "beta": DENY,
    }
    rap._audit.room_policies_listed.assert_called_once_with()


@pytest.mark.asyncio
async def test_list_room_policies_tolerates_stale_json_path(
    the_async_session,
):
    rap = _room_authz_policy(the_async_session)
    await _seed_stale_entry(the_async_session)

    found = await rap.list_room_policies()

    assert len(found) == 1
    assert [entry.json_path for entry in found[0].acl_entries] == [
        STALE_JSON_PATH
    ]
    rap._audit.room_policies_listed.assert_called_once_with()


@pytest.mark.asyncio
async def test_update_room_policy_room_id_is_authoritative(the_async_session):
    rap = _room_authz_policy(the_async_session)
    policy_model = models.RoomPolicy(
        room_id="some-other-room",
        acl_entries=[models.ACLEntry(allow_deny=ALLOW, everyone=True)],
    )

    await rap.update_room_policy(ROOM_ID, policy_model)

    rap._audit.room_policy_updated.assert_called_once_with(ROOM_ID)
    stored = await rap.get_room_policy(ROOM_ID)
    assert stored is not None
    assert stored.room_id == ROOM_ID
    assert await rap.get_room_policy("some-other-room") is None


@pytest.mark.asyncio
async def test_delete_room_policy_removes_acl_entries(the_async_session):
    # Regression: the delete must cascade to the ACL entries. The async
    # SQLite engine does not enforce the DB-level 'ON DELETE CASCADE', so
    # an orphaned row would survive and -- via SQLite primary-key reuse --
    # re-attach to the next policy created for the same room.
    rap = _room_authz_policy(the_async_session)
    await _seed_policy(
        the_async_session,
        default=DENY,
        entries=[_orm_entry(ALLOW, everyone=True)],
    )

    await rap.delete_room_policy(ROOM_ID)

    remaining = (
        await the_async_session.scalars(sqla_sql.select(authz_schema.ACLEntry))
    ).all()
    assert remaining == []
    rap._audit.room_policy_deleted.assert_called_once_with(ROOM_ID)


@pytest.mark.asyncio
async def test_clear_room_acl(the_async_session, unit_of_work):
    rap = _room_authz_policy(the_async_session)
    await _seed_policy(
        the_async_session,
        default=DENY,
        entries=[
            _orm_entry(ALLOW, everyone=True),
            _orm_entry(DENY, authenticated=True),
        ],
    )

    async with unit_of_work():
        await rap.clear_room_acl(ROOM_ID)

    rap._audit.acl_cleared.assert_called_once_with(ROOM_ID)
    after = await rap.get_room_policy(ROOM_ID)
    assert after.acl_entries == []
    assert after.default_allow_deny == DENY


@pytest.mark.asyncio
async def test_clear_room_acl_no_policy(the_async_session):
    rap = _room_authz_policy(the_async_session)

    await rap.clear_room_acl(ROOM_ID)

    rap._audit.acl_cleared.assert_called_once_with(ROOM_ID)
    assert await rap.get_room_policy(ROOM_ID) is None


@pytest.mark.asyncio
async def test_add_acl_entry_to_policy(the_async_session):
    rap = _room_authz_policy(the_async_session)
    await _seed_policy(the_async_session, default=DENY, entries=[])
    entry = models.ACLEntry(allow_deny=ALLOW, everyone=True)

    await rap.add_acl_entry(ROOM_ID, entry)

    rap._audit.acl_entry_added.assert_called_once_with(ROOM_ID, entry)
    after = await rap.get_room_policy(ROOM_ID)
    assert [(e.allow_deny, e.everyone) for e in after.acl_entries] == [
        (ALLOW, True)
    ]


@pytest.mark.asyncio
async def test_add_acl_entry_no_policy_raises(the_async_session):
    rap = _room_authz_policy(the_async_session)
    entry = models.ACLEntry(allow_deny=ALLOW, everyone=True)

    with pytest.raises(authz.NoSuchRoomPolicy):
        await rap.add_acl_entry(ROOM_ID, entry)

    ((args, kwargs),) = rap._audit.acl_entry_add_failed.call_args_list
    room_arg, entry_arg = args
    assert room_arg == ROOM_ID
    assert entry_arg == entry
    assert list(kwargs) == ["reason"]
    msg = kwargs["reason"]
    assert msg.startswith("No policy exists for room")


@pytest.mark.parametrize(
    "discriminator_kwargs",
    [
        {"everyone": True},
        {"authenticated": True},
        {"json_path": ROLE_JSON_PATH},
    ],
)
@pytest.mark.asyncio
async def test_add_acl_entry_replaces_same_discriminator(
    the_async_session, discriminator_kwargs, unit_of_work
):
    rap = _room_authz_policy(the_async_session)
    await _seed_policy(
        the_async_session,
        default=DENY,
        entries=[_orm_entry(ALLOW, **discriminator_kwargs)],
    )
    entry = models.ACLEntry(allow_deny=DENY, **discriminator_kwargs)

    async with unit_of_work():
        await rap.add_acl_entry(ROOM_ID, entry)

    rap._audit.acl_entry_added.assert_called_once_with(ROOM_ID, entry)
    after = await rap.get_room_policy(ROOM_ID)
    assert len(after.acl_entries) == 1
    assert after.acl_entries[0].allow_deny == DENY


@pytest.mark.asyncio
async def test_add_acl_entry_keeps_other_discriminator(the_async_session):
    rap = _room_authz_policy(the_async_session)
    await _seed_policy(
        the_async_session,
        default=DENY,
        entries=[_orm_entry(ALLOW, everyone=True)],
    )
    entry = models.ACLEntry(allow_deny=DENY, json_path=ROLE_JSON_PATH)

    await rap.add_acl_entry(ROOM_ID, entry)

    rap._audit.acl_entry_added.assert_called_once_with(ROOM_ID, entry)
    after = await rap.get_room_policy(ROOM_ID)
    assert len(after.acl_entries) == 2


@pytest.mark.parametrize(
    "seed_kwargs, remove_kwargs",
    [
        ({"everyone": True}, {"everyone": True}),
        ({"authenticated": True}, {"authenticated": True}),
        ({"json_path": ROLE_JSON_PATH}, {"json_path": ROLE_JSON_PATH}),
        (
            {
                "json_path": authz.token_field_json_path(
                    "preferred_username", "phreddy"
                )
            },
            {"preferred_username": "phreddy"},
        ),
        ({"json_path": JSON_PATH}, {"email": EMAIL}),
    ],
)
@pytest.mark.asyncio
async def test_remove_acl_entry_matches_discriminator(
    the_async_session, seed_kwargs, remove_kwargs, unit_of_work
):
    rap = _room_authz_policy(the_async_session)
    await _seed_policy(
        the_async_session,
        default=DENY,
        entries=[_orm_entry(ALLOW, **seed_kwargs)],
    )
    entry = models.ACLEntryUnchecked(allow_deny=ALLOW, **remove_kwargs)

    async with unit_of_work():
        await rap.remove_acl_entry(ROOM_ID, entry)

    rap._audit.acl_entry_removed.assert_called_once_with(ROOM_ID, entry)
    after = await rap.get_room_policy(ROOM_ID)
    assert after.acl_entries == []


@pytest.mark.asyncio
async def test_remove_acl_entry_no_match_raises(the_async_session):
    rap = _room_authz_policy(the_async_session)
    await _seed_policy(
        the_async_session,
        default=DENY,
        entries=[
            _orm_entry(ALLOW, everyone=True),
            _orm_entry(DENY, json_path=ROLE_JSON_PATH),
        ],
    )

    entry = models.ACLEntryUnchecked(
        allow_deny=ALLOW, json_path=ROLE_JSON_PATH
    )

    with pytest.raises(authz.NoSuchACLEntry):
        await rap.remove_acl_entry(ROOM_ID, entry)

    ((args, kwargs),) = rap._audit.acl_entry_remove_failed.call_args_list
    room_arg, entry_arg = args
    assert room_arg == ROOM_ID
    assert entry_arg == entry
    assert list(kwargs) == ["reason"]
    msg = kwargs["reason"]
    assert msg.startswith("No matching ACL entry in room")


@pytest.mark.asyncio
async def test_remove_acl_entry_no_policy_raises(the_async_session):
    rap = _room_authz_policy(the_async_session)
    entry = models.ACLEntryUnchecked(allow_deny=ALLOW, everyone=True)

    with pytest.raises(authz.NoSuchRoomPolicy):
        await rap.remove_acl_entry(ROOM_ID, entry)

    ((args, kwargs),) = rap._audit.acl_entry_remove_failed.call_args_list
    room_arg, entry_arg = args
    assert room_arg == ROOM_ID
    assert entry_arg == entry
    assert list(kwargs) == ["reason"]
    msg = kwargs["reason"]
    assert msg.startswith("No policy exists for room")


@pytest.mark.asyncio
async def test_remove_acl_entry_stale_json_path(the_async_session):
    rap = _room_authz_policy(the_async_session)
    await _seed_stale_entry(the_async_session, allow_deny=ALLOW)
    entry = models.ACLEntryUnchecked(
        allow_deny=ALLOW, json_path=STALE_JSON_PATH
    )

    await rap.remove_acl_entry(ROOM_ID, entry)

    rap._audit.acl_entry_removed.assert_called_once_with(ROOM_ID, entry)
    after = await rap.get_room_policy(ROOM_ID)
    assert after.acl_entries == []


@pytest.mark.asyncio
async def test_set_room_default_creates_when_missing(the_async_session):
    rap = _room_authz_policy(the_async_session)

    await rap.set_room_default(ROOM_ID, ALLOW)

    rap._audit.room_default_set.assert_called_once_with(ROOM_ID, ALLOW)
    after = await rap.get_room_policy(ROOM_ID)
    assert after is not None
    assert after.default_allow_deny == ALLOW
    assert after.acl_entries == []


@pytest.mark.asyncio
async def test_set_room_default_updates_existing(the_async_session):
    rap = _room_authz_policy(the_async_session)
    await _seed_policy(
        the_async_session,
        default=DENY,
        entries=[_orm_entry(ALLOW, everyone=True)],
    )

    await rap.set_room_default(ROOM_ID, ALLOW)

    rap._audit.room_default_set.assert_called_once_with(ROOM_ID, ALLOW)
    after = await rap.get_room_policy(ROOM_ID)
    assert after.default_allow_deny == ALLOW
    assert len(after.acl_entries) == 1
