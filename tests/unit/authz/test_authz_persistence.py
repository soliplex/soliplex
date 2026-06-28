import datetime
from unittest import mock

import pytest
from sqlalchemy import sql as sqla_sql
from sqlalchemy.ext import asyncio as sqla_asyncio

from soliplex import authz
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


@pytest.fixture
def faux_sqlaa_session():
    return mock.create_autospec(
        sqla_asyncio.AsyncSession,
    )


@pytest.mark.anyio
async def test_admin_user_session(faux_sqlaa_session):
    aup = authz_persistence.AdminUserPolicy(faux_sqlaa_session)
    begin = faux_sqlaa_session.begin

    async with aup.session as session:
        assert session is faux_sqlaa_session

        begin.assert_called_once_with()
        begin.return_value.__aenter__.assert_called_once_with()
        begin.return_value.__aexit__.assert_not_called()

    begin.return_value.__aenter__.assert_called_once_with()


@pytest.mark.asyncio
async def test_list_admin_user_discriminators(the_async_session):
    aup = authz_persistence.AdminUserPolicy(the_async_session)
    the_async_session.add(authz_schema.AdminUser(json_path=JSON_PATH))
    the_async_session.add(authz_schema.AdminUser(json_path=ROLE_JSON_PATH))
    await the_async_session.commit()

    found = await aup.list_admin_user_discriminators()

    assert found == [JSON_PATH, ROLE_JSON_PATH]


@pytest.mark.asyncio
async def test_add_admin_user_discriminator(the_async_session):
    aup = authz_persistence.AdminUserPolicy(the_async_session)

    await aup.add_admin_user_discriminator(ROLE_JSON_PATH)

    found = await aup.list_admin_user_discriminators()
    assert found == [ROLE_JSON_PATH]


@pytest.mark.asyncio
async def test_add_admin_user_discriminator_already_exists(the_async_session):
    aup = authz_persistence.AdminUserPolicy(the_async_session)
    the_async_session.add(authz_schema.AdminUser(json_path=ROLE_JSON_PATH))
    await the_async_session.commit()

    with pytest.raises(authz.AdminUserExists):
        await aup.add_admin_user_discriminator(ROLE_JSON_PATH)


@pytest.mark.asyncio
async def test_remove_admin_user_discriminator(the_async_session):
    aup = authz_persistence.AdminUserPolicy(the_async_session)
    the_async_session.add(authz_schema.AdminUser(json_path=ROLE_JSON_PATH))
    await the_async_session.commit()

    await aup.remove_admin_user_discriminator(ROLE_JSON_PATH)

    found = await aup.list_admin_user_discriminators()
    assert found == []


@pytest.mark.asyncio
async def test_remove_admin_user_discriminator_absent(the_async_session):
    aup = authz_persistence.AdminUserPolicy(the_async_session)

    with pytest.raises(authz.NoSuchAdminUser):
        await aup.remove_admin_user_discriminator(ROLE_JSON_PATH)


@pytest.mark.asyncio
async def test_remove_admin_user_discriminator_invalid_json_path(
    the_async_session,
):
    aup = authz_persistence.AdminUserPolicy(the_async_session)
    # Seed via a core INSERT so the stored value bypasses the ORM
    # '@validates' hook -- mimicking an entry whose 'json_path' no
    # longer compiles (e.g. a removed meta-config filter function).
    await the_async_session.execute(
        sqla_sql.insert(authz_schema.AdminUser.__table__).values(
            json_path=INVALID_JSON_PATH,
            created=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        )
    )
    await the_async_session.commit()

    await aup.remove_admin_user_discriminator(INVALID_JSON_PATH)

    found = await aup.list_admin_user_discriminators()
    assert found == []


@pytest.mark.asyncio
async def test_clear_admin_user_discriminators(the_async_session):
    aup = authz_persistence.AdminUserPolicy(the_async_session)
    the_async_session.add(authz_schema.AdminUser(json_path=JSON_PATH))
    the_async_session.add(authz_schema.AdminUser(json_path=ROLE_JSON_PATH))
    await the_async_session.commit()

    await aup.clear_admin_user_discriminators()

    found = await aup.list_admin_user_discriminators()
    assert found == []


@pytest.mark.asyncio
async def test_clear_admin_user_discriminators_empty(the_async_session):
    aup = authz_persistence.AdminUserPolicy(the_async_session)

    await aup.clear_admin_user_discriminators()

    found = await aup.list_admin_user_discriminators()
    assert found == []


@pytest.mark.asyncio
async def test_admin_user_crud(the_async_session):
    # The deprecated 'email'-keyed aliases delegate to the
    # '*_discriminator' methods, storing the canonical email JSONPath.
    aup = authz_persistence.AdminUserPolicy(the_async_session)

    found = await aup.list_admin_users()

    assert found == []

    await aup.add_admin_user(email=EMAIL)
    user = await authz_persistence._find_admin_user_by_json_path(
        json_path=JSON_PATH,
        session=the_async_session,
    )
    assert user is not None
    await the_async_session.commit()

    found = await aup.list_admin_users()
    assert found == [JSON_PATH]
    await the_async_session.commit()

    with pytest.raises(authz.AdminUserExists):
        await aup.add_admin_user(email=EMAIL)

    no_dupe = await authz_persistence._find_admin_user_by_json_path(
        json_path=JSON_PATH,
        session=the_async_session,
    )
    assert no_dupe is user
    await the_async_session.commit()

    found = await aup.list_admin_users()
    assert found == [JSON_PATH]
    await the_async_session.commit()

    await aup.remove_admin_user(email=EMAIL)
    gone = await authz_persistence._find_admin_user_by_json_path(
        json_path=JSON_PATH,
        session=the_async_session,
    )
    assert gone is None
    await the_async_session.commit()

    found = await aup.list_admin_users()
    assert found == []
    await the_async_session.commit()

    with pytest.raises(authz.NoSuchAdminUser):
        await aup.remove_admin_user(email=EMAIL)


@pytest.mark.asyncio
async def test_admin_user_check_admin_access(the_async_session):
    aup = authz_persistence.AdminUserPolicy(the_async_session)

    assert not await aup.check_admin_access(USER_TOKEN)

    await aup.add_admin_user(email=EMAIL)

    assert await aup.check_admin_access(USER_TOKEN)

    await aup.remove_admin_user(email=EMAIL)

    assert not await aup.check_admin_access(USER_TOKEN)


@pytest.mark.asyncio
async def test_admin_user_check_admin_access_json_path(
    the_async_session,
):
    aup = authz_persistence.AdminUserPolicy(the_async_session)

    # An admin keyed by a non-email JSONPath query (e.g. a role claim),
    # as produced by 'admin-users add --json-path'.
    the_async_session.add(
        authz_schema.AdminUser(json_path='$[?$.role == "admin"]'),
    )
    await the_async_session.commit()

    assert await aup.check_admin_access({"role": "admin"})
    assert not await aup.check_admin_access({"role": "user"})
    # A role-keyed admin is not matched by an unrelated email token.
    assert not await aup.check_admin_access(USER_TOKEN)

    # A non-email admin surfaces as its raw JSONPath query, not an email.
    listed = await aup.list_admin_users()
    assert listed == ['$[?$.role == "admin"]']


@pytest.mark.asyncio
async def test_room_authz_check_room_access(the_async_session):
    rap = authz_persistence.RoomAuthorizationPolicy(the_async_session)

    # No policy -> public room
    assert await rap.check_room_access(ROOM_ID, None)

    # Policy w/ deny as default, no ACL entries
    denier = authz_schema.RoomPolicy(room_id=ROOM_ID)
    the_async_session.add(denier)
    await the_async_session.commit()

    assert not await rap.check_room_access(ROOM_ID, None)

    allower = authz_schema.ACLEntry(
        room_policy=denier,
        allow_deny=authz.AllowDeny.ALLOW,
        everyone=True,
    )
    the_async_session.add(allower)
    await the_async_session.commit()

    assert await rap.check_room_access(ROOM_ID, None)


@pytest.mark.asyncio
async def test_room_authz_filter_room_ids(the_async_session):
    rap = authz_persistence.RoomAuthorizationPolicy(the_async_session)

    room_ids = [ROOM_ID]

    # No policy -> public room
    assert await rap.filter_room_ids(room_ids, None) == room_ids

    # Policy w/ deny as default, no ACL entries
    denier = authz_schema.RoomPolicy(room_id=ROOM_ID)
    the_async_session.add(denier)
    await the_async_session.commit()

    assert await rap.filter_room_ids(room_ids, None) == []

    allower = authz_schema.ACLEntry(
        room_policy=denier,
        allow_deny=authz.AllowDeny.ALLOW,
        everyone=True,
    )
    the_async_session.add(allower)
    await the_async_session.commit()

    assert await rap.filter_room_ids(room_ids, None) == room_ids


@pytest.mark.asyncio
async def test_room_authz_policy_crud(the_async_session):
    rap = authz_persistence.RoomAuthorizationPolicy(the_async_session)

    # No policy -> public room
    policy = await rap.get_room_policy(ROOM_ID)
    assert policy is None

    acl_entry_model = models.ACLEntry(
        allow_deny=authz.AllowDeny.ALLOW,
        everyone=True,
    )
    policy_model = models.RoomPolicy(
        room_id=ROOM_ID,
        acl_entries=[acl_entry_model],
    )
    await rap.update_room_policy(ROOM_ID, policy_model)
    await the_async_session.commit()

    after = await rap.get_room_policy(ROOM_ID)
    assert after == policy_model
    await the_async_session.commit()

    new_acl_entry_model = models.ACLEntry(
        allow_deny=authz.AllowDeny.ALLOW,
        preferred_username="phreddy",
    )
    new_policy_model = policy_model.model_copy(
        update={"acl_entries": [new_acl_entry_model]},
    )
    await rap.update_room_policy(ROOM_ID, new_policy_model)
    await the_async_session.commit()

    policy = await rap.get_room_policy(ROOM_ID)
    assert policy == new_policy_model
    await the_async_session.commit()

    await rap.delete_room_policy(ROOM_ID)
    await the_async_session.commit()

    gone = await rap.get_room_policy(ROOM_ID)
    assert gone is None
    await the_async_session.commit()

    await rap.delete_room_policy(ROOM_ID)
    await the_async_session.commit()


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
    await session.commit()
    return policy


async def _seed_stale_entry(session, *, allow_deny=ALLOW):
    await _seed_policy(
        session,
        default=DENY,
        entries=[_orm_entry(allow_deny, json_path=JSON_PATH)],
    )
    await session.execute(
        sqla_sql.text(
            "UPDATE room_acl_entries SET json_path = :stale "
            "WHERE json_path = :placeholder"
        ),
        {"stale": STALE_JSON_PATH, "placeholder": JSON_PATH},
    )
    await session.commit()
    session.expire_all()


@pytest.mark.asyncio
async def test_get_room_policy_unchecked_absent(the_async_session):
    rap = authz_persistence.RoomAuthorizationPolicy(the_async_session)

    found = await rap.get_room_policy_unchecked(ROOM_ID)

    assert found is None


@pytest.mark.asyncio
async def test_get_room_policy_unchecked_tolerates_stale_json_path(
    the_async_session,
):
    rap = authz_persistence.RoomAuthorizationPolicy(the_async_session)
    await _seed_stale_entry(the_async_session)

    found = await rap.get_room_policy_unchecked(ROOM_ID)

    assert isinstance(found, models.RoomPolicyUnchecked)
    assert [entry.json_path for entry in found.acl_entries] == [
        STALE_JSON_PATH
    ]


@pytest.mark.asyncio
async def test_list_room_policies_empty(the_async_session):
    rap = authz_persistence.RoomAuthorizationPolicy(the_async_session)

    found = await rap.list_room_policies()

    assert found == []


@pytest.mark.asyncio
async def test_list_room_policies(the_async_session):
    rap = authz_persistence.RoomAuthorizationPolicy(the_async_session)
    the_async_session.add(
        authz_schema.RoomPolicy(room_id="alpha", default_allow_deny=ALLOW)
    )
    the_async_session.add(
        authz_schema.RoomPolicy(room_id="beta", default_allow_deny=DENY)
    )
    await the_async_session.commit()

    found = await rap.list_room_policies()

    assert all(
        isinstance(policy, models.RoomPolicyUnchecked) for policy in found
    )
    assert {policy.room_id: policy.default_allow_deny for policy in found} == {
        "alpha": ALLOW,
        "beta": DENY,
    }


@pytest.mark.asyncio
async def test_list_room_policies_tolerates_stale_json_path(
    the_async_session,
):
    rap = authz_persistence.RoomAuthorizationPolicy(the_async_session)
    await _seed_stale_entry(the_async_session)

    found = await rap.list_room_policies()

    assert len(found) == 1
    assert [entry.json_path for entry in found[0].acl_entries] == [
        STALE_JSON_PATH
    ]


@pytest.mark.asyncio
async def test_update_room_policy_room_id_is_authoritative(the_async_session):
    rap = authz_persistence.RoomAuthorizationPolicy(the_async_session)
    policy_model = models.RoomPolicy(
        room_id="some-other-room",
        acl_entries=[models.ACLEntry(allow_deny=ALLOW, everyone=True)],
    )

    await rap.update_room_policy(ROOM_ID, policy_model)
    await the_async_session.commit()

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
    rap = authz_persistence.RoomAuthorizationPolicy(the_async_session)
    await _seed_policy(
        the_async_session,
        default=DENY,
        entries=[_orm_entry(ALLOW, everyone=True)],
    )

    await rap.delete_room_policy(ROOM_ID)
    await the_async_session.commit()

    remaining = (
        await the_async_session.scalars(sqla_sql.select(authz_schema.ACLEntry))
    ).all()
    assert remaining == []


@pytest.mark.asyncio
async def test_clear_room_acl(the_async_session):
    rap = authz_persistence.RoomAuthorizationPolicy(the_async_session)
    await _seed_policy(
        the_async_session,
        default=DENY,
        entries=[
            _orm_entry(ALLOW, everyone=True),
            _orm_entry(DENY, authenticated=True),
        ],
    )

    await rap.clear_room_acl(ROOM_ID)
    await the_async_session.commit()

    after = await rap.get_room_policy(ROOM_ID)
    assert after.acl_entries == []
    assert after.default_allow_deny == DENY


@pytest.mark.asyncio
async def test_clear_room_acl_no_policy(the_async_session):
    rap = authz_persistence.RoomAuthorizationPolicy(the_async_session)

    await rap.clear_room_acl(ROOM_ID)

    assert await rap.get_room_policy(ROOM_ID) is None


@pytest.mark.asyncio
async def test_add_acl_entry_to_policy(the_async_session):
    rap = authz_persistence.RoomAuthorizationPolicy(the_async_session)
    await _seed_policy(the_async_session, default=DENY, entries=[])

    await rap.add_acl_entry(
        ROOM_ID, models.ACLEntry(allow_deny=ALLOW, everyone=True)
    )
    await the_async_session.commit()

    after = await rap.get_room_policy(ROOM_ID)
    assert [(e.allow_deny, e.everyone) for e in after.acl_entries] == [
        (ALLOW, True)
    ]


@pytest.mark.asyncio
async def test_add_acl_entry_no_policy_raises(the_async_session):
    rap = authz_persistence.RoomAuthorizationPolicy(the_async_session)

    with pytest.raises(authz.NoSuchRoomPolicy):
        await rap.add_acl_entry(
            ROOM_ID, models.ACLEntry(allow_deny=ALLOW, everyone=True)
        )


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
    the_async_session, discriminator_kwargs
):
    rap = authz_persistence.RoomAuthorizationPolicy(the_async_session)
    await _seed_policy(
        the_async_session,
        default=DENY,
        entries=[_orm_entry(ALLOW, **discriminator_kwargs)],
    )

    await rap.add_acl_entry(
        ROOM_ID, models.ACLEntry(allow_deny=DENY, **discriminator_kwargs)
    )
    await the_async_session.commit()

    after = await rap.get_room_policy(ROOM_ID)
    assert len(after.acl_entries) == 1
    assert after.acl_entries[0].allow_deny == DENY


@pytest.mark.asyncio
async def test_add_acl_entry_keeps_other_discriminator(the_async_session):
    rap = authz_persistence.RoomAuthorizationPolicy(the_async_session)
    await _seed_policy(
        the_async_session,
        default=DENY,
        entries=[_orm_entry(ALLOW, everyone=True)],
    )

    await rap.add_acl_entry(
        ROOM_ID, models.ACLEntry(allow_deny=DENY, json_path=ROLE_JSON_PATH)
    )
    await the_async_session.commit()

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
    the_async_session, seed_kwargs, remove_kwargs
):
    rap = authz_persistence.RoomAuthorizationPolicy(the_async_session)
    await _seed_policy(
        the_async_session,
        default=DENY,
        entries=[_orm_entry(ALLOW, **seed_kwargs)],
    )

    await rap.remove_acl_entry(
        ROOM_ID, models.ACLEntryUnchecked(allow_deny=ALLOW, **remove_kwargs)
    )
    await the_async_session.commit()

    after = await rap.get_room_policy(ROOM_ID)
    assert after.acl_entries == []


@pytest.mark.asyncio
async def test_remove_acl_entry_no_match_raises(the_async_session):
    rap = authz_persistence.RoomAuthorizationPolicy(the_async_session)
    await _seed_policy(
        the_async_session,
        default=DENY,
        entries=[
            _orm_entry(ALLOW, everyone=True),
            _orm_entry(DENY, json_path=ROLE_JSON_PATH),
        ],
    )

    with pytest.raises(authz.NoSuchACLEntry):
        await rap.remove_acl_entry(
            ROOM_ID,
            models.ACLEntryUnchecked(
                allow_deny=ALLOW, json_path=ROLE_JSON_PATH
            ),
        )


@pytest.mark.asyncio
async def test_remove_acl_entry_no_policy_raises(the_async_session):
    rap = authz_persistence.RoomAuthorizationPolicy(the_async_session)

    with pytest.raises(authz.NoSuchRoomPolicy):
        await rap.remove_acl_entry(
            ROOM_ID, models.ACLEntryUnchecked(allow_deny=ALLOW, everyone=True)
        )


@pytest.mark.asyncio
async def test_remove_acl_entry_stale_json_path(the_async_session):
    rap = authz_persistence.RoomAuthorizationPolicy(the_async_session)
    await _seed_stale_entry(the_async_session, allow_deny=ALLOW)

    await rap.remove_acl_entry(
        ROOM_ID,
        models.ACLEntryUnchecked(allow_deny=ALLOW, json_path=STALE_JSON_PATH),
    )
    await the_async_session.commit()

    after = await rap.get_room_policy(ROOM_ID)
    assert after.acl_entries == []


@pytest.mark.asyncio
async def test_set_room_default_creates_when_missing(the_async_session):
    rap = authz_persistence.RoomAuthorizationPolicy(the_async_session)

    await rap.set_room_default(ROOM_ID, ALLOW)
    await the_async_session.commit()

    after = await rap.get_room_policy(ROOM_ID)
    assert after is not None
    assert after.default_allow_deny == ALLOW
    assert after.acl_entries == []


@pytest.mark.asyncio
async def test_set_room_default_updates_existing(the_async_session):
    rap = authz_persistence.RoomAuthorizationPolicy(the_async_session)
    await _seed_policy(
        the_async_session,
        default=DENY,
        entries=[_orm_entry(ALLOW, everyone=True)],
    )

    await rap.set_room_default(ROOM_ID, ALLOW)
    await the_async_session.commit()

    after = await rap.get_room_policy(ROOM_ID)
    assert after.default_allow_deny == ALLOW
    assert len(after.acl_entries) == 1
