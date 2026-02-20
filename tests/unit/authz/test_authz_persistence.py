from unittest import mock

import pytest
from sqlalchemy.ext import asyncio as sqla_asyncio

from soliplex import authz as authz_package
from soliplex import models
from soliplex.authz import persistence as authz_persistence
from soliplex.authz import schema as authz_schema

EMAIL = "phreddy@example.com"
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
async def test_authorizationpolicy_session(faux_sqlaa_session):
    ap = authz_persistence.AuthorizationPolicy(faux_sqlaa_session)
    begin = faux_sqlaa_session.begin

    async with ap.session as session:
        assert session is faux_sqlaa_session

        begin.assert_called_once_with()
        begin.return_value.__aenter__.assert_called_once_with()
        begin.return_value.__aexit__.assert_not_called()

    begin.return_value.__aenter__.assert_called_once_with()


@pytest.mark.asyncio
async def test_authorizationpolicy_crud_admin_user(the_async_session):
    ap = authz_persistence.AuthorizationPolicy(the_async_session)

    found = await ap.list_admin_users()

    assert found == []

    await ap.add_admin_user(email=EMAIL)
    user = await authz_persistence._find_admin_user(
        email=EMAIL,
        session=the_async_session,
    )
    assert user is not None
    await the_async_session.commit()

    found = await ap.list_admin_users()
    assert found == [EMAIL]
    await the_async_session.commit()

    with pytest.raises(authz_persistence.AdminUserExists):
        await ap.add_admin_user(email=EMAIL)

    no_dupe = await authz_persistence._find_admin_user(
        email=EMAIL,
        session=the_async_session,
    )
    assert no_dupe is user
    await the_async_session.commit()

    found = await ap.list_admin_users()
    assert found == [EMAIL]
    await the_async_session.commit()

    await ap.remove_admin_user(email=EMAIL)
    gone = await authz_persistence._find_admin_user(
        email=EMAIL,
        session=the_async_session,
    )
    assert gone is None
    await the_async_session.commit()

    found = await ap.list_admin_users()
    assert found == []
    await the_async_session.commit()

    with pytest.raises(authz_persistence.NoSuchAdminUser):
        await ap.remove_admin_user(email=EMAIL)


@pytest.mark.asyncio
async def test_authorizationpolicy_check_admin_access(the_async_session):
    ap = authz_persistence.AuthorizationPolicy(the_async_session)

    assert not await ap.check_admin_access(USER_TOKEN)

    await ap.add_admin_user(email=EMAIL)

    assert await ap.check_admin_access(USER_TOKEN)

    await ap.remove_admin_user(email=EMAIL)

    assert not await ap.check_admin_access(USER_TOKEN)


@pytest.mark.asyncio
async def test_authorizationpolicy_check_room_access(the_async_session):
    ap = authz_persistence.AuthorizationPolicy(the_async_session)

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
    ap = authz_persistence.AuthorizationPolicy(the_async_session)

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
    ap = authz_persistence.AuthorizationPolicy(the_async_session)

    with pytest.raises(authz_persistence.NotAdminUser):
        await ap.get_room_policy(ROOM_ID, USER_TOKEN)

    acl_entry_model = models.ACLEntry(
        allow_deny=authz_package.AllowDeny.ALLOW,
        everyone=True,
    )
    policy_model = models.RoomPolicy(
        room_id=ROOM_ID,
        acl_entries=[acl_entry_model],
    )

    with pytest.raises(authz_persistence.NotAdminUser):
        await ap.update_room_policy(ROOM_ID, policy_model, USER_TOKEN)

    with pytest.raises(authz_persistence.NotAdminUser):
        await ap.delete_room_policy(ROOM_ID, USER_TOKEN)


@pytest.mark.asyncio
async def test_authorizationpolicy_room_policy_crud(the_async_session):
    ap = authz_persistence.AuthorizationPolicy(the_async_session)

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
