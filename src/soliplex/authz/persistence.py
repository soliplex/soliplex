"""SQLAlchemy persistence for the 'authz' policy interfaces.

Implements 'authz.AdminUserPolicy' and 'authz.RoomAuthorizationPolicy'.
"""

from __future__ import annotations

import contextlib
import typing

from sqlalchemy import sql as sqla_sql
from sqlalchemy.ext import asyncio as sqla_asyncio

from soliplex import authz
from soliplex import loggers
from soliplex import models
from soliplex.authz import schema as authz_schema


def _entry_discriminator(
    entry: models.ACLEntryUnchecked,
) -> tuple[bool, bool, str | None]:
    """Resolve an ACL-entry model's discriminator without compiling.

    Collapses the 'preferred_username' / 'email' claim shortcuts to the
    equivalent stored 'json_path' string (highest priority first, matching
    'authz_schema.ACLEntry.from_model'), so a possibly-stale 'json_path'
    can be matched against stored rows by string equality. Returns the
    '(everyone, authenticated, json_path)' triple.
    """
    json_path = entry.json_path
    if entry.preferred_username is not None:
        json_path = authz.token_field_json_path(
            "preferred_username", entry.preferred_username
        )
    elif entry.email is not None:
        json_path = authz.token_field_json_path("email", entry.email)
    return entry.everyone, entry.authenticated, json_path


async def _find_admin_user_by_json_path(
    json_path: str,
    session,
) -> authz_schema.AdminUser | None:
    query = sqla_sql.select(authz_schema.AdminUser).where(
        authz_schema.AdminUser.json_path == json_path
    )
    user = (await session.scalars(query)).first()

    return user


async def _user_is_admin(user_token, session) -> bool:
    """Does any admin entry's JSONPath query match 'user_token'?"""
    query = sqla_sql.select(authz_schema.AdminUser)
    for admin_user in await session.scalars(query):
        if admin_user.check_token(user_token):
            return True
    return False


async def _find_room_policy(
    room_id: str,
    session,
) -> authz_schema.RoomPolicy | None:
    query = sqla_sql.select(authz_schema.RoomPolicy).where(
        authz_schema.RoomPolicy.room_id == room_id
    )
    policy = (await session.scalars(query)).first()

    return policy


class _SessionPolicy:
    """Async-session plumbing shared by the concrete policies."""

    def __init__(self, session: sqla_asyncio.AsyncSession):
        self._session = session

    @property
    @contextlib.asynccontextmanager
    async def session(self):
        # Yield the caller-owned session as-is: the session owner (a
        # FastAPI dependency or the CLI '_authz_session' context manager)
        # owns the transaction boundary and commits the unit of work
        # exactly once. Policy methods here never open their own
        # transaction or commit, so callers -- and tests -- need no
        # interleaved commits.
        yield self._session


class AdminUserPolicy(_SessionPolicy, authz.AdminUserPolicy):
    def __init__(
        self,
        session: sqla_asyncio.AsyncSession,
        claims: dict[str, typing.Any],
    ):
        super().__init__(session)
        self._audit = loggers.AdminUsersAuditLog(claims=claims)

    async def list_admin_user_discriminators(self) -> list[str]:
        """List JSONPath discriminators which identify admin users.

        Discriminators may be tied to individuals (e.g., via their
        email addresses), or to claims which identify groups or
        roles attached to the user.
        """
        query = sqla_sql.select(authz_schema.AdminUser)
        async with self.session as session:
            discriminators = [
                admin_user.json_path
                for admin_user in await session.scalars(query)
            ]
        self._audit.admin_users_listed()
        return discriminators

    async def add_admin_user_discriminator(self, json_path: str):
        """Add a user discriminator to the admin users table.

        Discriminators may be tied to individuals (e.g., via their
        email addresses), or to claims which identify groups or
        roles attached to the user.
        """
        async with self.session as session:
            user = await _find_admin_user_by_json_path(json_path, session)

            if user is not None:
                exc = authz.AdminUserExists(json_path=json_path)
                self._audit.admin_user_add_failed(json_path, reason=str(exc))
                raise exc

            user = authz_schema.AdminUser(json_path=json_path)
            session.add(user)
        self._audit.admin_user_added(json_path)

    async def remove_admin_user_discriminator(self, json_path: str):
        """Remove a user discriminator from the admin users table.

        Discriminators may be tied to individuals (e.g., via their
        email addresses), or to claims which identify groups or
        roles attached to the user.
        """
        async with self.session as session:
            user = await _find_admin_user_by_json_path(json_path, session)

            if user is None:
                exc = authz.NoSuchAdminUser(json_path=json_path)
                self._audit.admin_user_remove_failed(
                    json_path, reason=str(exc)
                )
                raise exc

            await session.delete(user)
        self._audit.admin_user_removed(json_path)

    async def clear_admin_user_discriminators(self):
        """Remove all admin user discriminators from the admin users table."""
        query = sqla_sql.select(authz_schema.AdminUser)
        async with self.session as session:
            for admin_user in await session.scalars(query):
                await session.delete(admin_user)
        self._audit.admin_users_cleared()

    async def list_admin_users(self) -> list[str]:
        """Deprecated alias for 'list_admin_user_discriminators'."""
        return await self.list_admin_user_discriminators()

    async def add_admin_user(self, email: str):
        """Deprecated alias for 'add_admin_user_discriminator'.

        Translates 'email' to the equivalent JSONPath expression,
        '$[?$.email == "..."]', then delegates.
        """
        json_path = authz.token_field_json_path("email", email)
        await self.add_admin_user_discriminator(json_path)

    async def remove_admin_user(self, email: str):
        """Deprecated alias for 'remove_admin_user_discriminator'.

        Translates 'email' to the equivalent JSONPath expression,
        '$[?$.email == "..."]', then delegates.
        """
        json_path = authz.token_field_json_path("email", email)
        await self.remove_admin_user_discriminator(json_path)

    async def check_admin_access(
        self,
        user_token: authz.UserToken,
    ) -> bool:
        """Is the user represented by 'user_token' an admin user?"""
        async with self.session as session:
            is_admin = await _user_is_admin(user_token, session)
        if is_admin:
            self._audit.admin_access_allowed()
        else:
            self._audit.admin_access_denied()
        return is_admin


class RoomAuthorizationPolicy(_SessionPolicy, authz.RoomAuthorizationPolicy):
    def __init__(
        self,
        session: sqla_asyncio.AsyncSession,
        claims: dict[str, typing.Any],
    ):
        super().__init__(session)
        self._audit = loggers.RoomAuthzAuditLog(claims=claims)

    async def check_room_access(
        self,
        room_id: str,
        user_token: authz.UserToken | None,
    ) -> bool:
        """Can the user represented by 'user_token' can access a room?

        If an authorization policy exists for the room, check that it allows
        access for the user token.

        Otherwise, return True (i.e., the room is public).
        """
        async with self.session as session:
            policy = await _find_room_policy(room_id, session)

            if policy is not None:
                await policy.awaitable_attrs.acl_entries
                allow_deny = policy.check_token(user_token)
                return allow_deny == authz.AllowDeny.ALLOW
            else:
                return True

    async def filter_room_ids(
        self,
        room_ids: list[str],
        user_token: authz.UserToken | None,
    ) -> list[str]:
        """Filter room IDs based on room authz policies for 'user_token'

        For each room, if an authorization policy exists for the room,
        check that it allows access for the user token.

        Otherwise, treat the room as public.
        """
        result = []
        async with self.session as session:
            for room_id in room_ids:
                policy = await _find_room_policy(room_id, session)
                if policy is not None:
                    await policy.awaitable_attrs.acl_entries
                    allow_deny = policy.check_token(user_token)
                    if allow_deny != authz.AllowDeny.ALLOW:
                        continue
                result.append(room_id)

        return result

    async def get_room_policy(
        self,
        room_id: str,
    ) -> models.RoomPolicy | None:
        """Return the authorization policy for the room"""
        async with self.session as session:
            policy = await _find_room_policy(room_id, session)

            if policy is not None:
                await policy.awaitable_attrs.acl_entries
                result = policy.as_model
            else:
                result = None
        self._audit.room_policy_read(room_id)
        return result

    async def get_room_policy_unchecked(
        self,
        room_id: str,
    ) -> models.RoomPolicyUnchecked | None:
        """Return the room policy, tolerating non-compiling 'json_path's.

        The analogue of 'get_room_policy' for callers (e.g. the CLI) that
        must inspect a policy even when a stored ACL entry's 'json_path'
        no longer compiles. Returns the unchecked model, which carries
        such a 'json_path' without raising.
        """
        async with self.session as session:
            policy = await _find_room_policy(room_id, session)

            if policy is not None:
                await policy.awaitable_attrs.acl_entries
                result = policy.as_unchecked_model
            else:
                result = None
        self._audit.room_policy_read(room_id)
        return result

    async def list_room_policies(
        self,
    ) -> list[models.RoomPolicyUnchecked]:
        """List every stored room policy as an unchecked model.

        The analogue of 'get_room_policy_unchecked' over the whole
        table: each policy (and its ACL entries) is returned as the
        unchecked model, so a stored 'json_path' that no longer compiles
        is surfaced rather than raising -- exactly what an audit needs.
        """
        query = sqla_sql.select(authz_schema.RoomPolicy)
        async with self.session as session:
            policies = list(await session.scalars(query))
            for policy in policies:
                await policy.awaitable_attrs.acl_entries
            result = [policy.as_unchecked_model for policy in policies]
        self._audit.room_policies_listed()
        return result

    async def update_room_policy(
        self,
        room_id: str,
        room_policy: models.RoomPolicy,
    ) -> None:
        """Update the authorization policy for the room

        'room_id' is authoritative: the stored policy is written for
        'room_id' regardless of the 'room_id' carried by 'room_policy'.
        """
        async with self.session as session:
            policy = await _find_room_policy(room_id, session)

            if policy is not None:
                await policy.awaitable_attrs.acl_entries

                async with session.begin_nested():
                    await session.delete(policy)

            new_policy = authz_schema.RoomPolicy.from_model(room_policy)
            new_policy.room_id = room_id

            async with session.begin_nested():
                session.add(new_policy)

        self._audit.room_policy_updated(room_id)
        return None

    async def delete_room_policy(
        self,
        room_id: str,
    ) -> None:
        """Delete any existing authorization policy for the room"""
        async with self.session as session:
            policy = await _find_room_policy(room_id, session)

            if policy is not None:
                # Load the ACL entries so the ORM 'delete' cascade removes
                # them along with the policy. Without this they are only
                # cleaned up by the DB-level 'ON DELETE CASCADE', which the
                # async SQLite engine does not enforce -- leaving orphans
                # that SQLite's primary-key reuse can re-attach to the next
                # policy created for the same room.
                await policy.awaitable_attrs.acl_entries

                async with session.begin_nested():
                    await session.delete(policy)

        self._audit.room_policy_deleted(room_id)

    async def clear_room_acl(self, room_id: str) -> None:
        """Remove all ACL entries from the room's policy.

        The policy row and its 'default_allow_deny' are preserved. A
        no-op if the room has no policy.
        """
        async with self.session as session:
            policy = await _find_room_policy(room_id, session)

            if policy is not None:
                await policy.awaitable_attrs.acl_entries
                for acl_entry in list(policy.acl_entries):
                    await session.delete(acl_entry)
        self._audit.acl_cleared(room_id)

    async def add_acl_entry(
        self,
        room_id: str,
        entry: models.ACLEntry,
    ) -> None:
        """Add an ACL entry to the room's policy.

        The room must already have a policy ('set_room_default' or a prior
        'update_room_policy'); otherwise 'NoSuchRoomPolicy' is raised. Any
        existing entry with the same discriminator is replaced.
        """
        new_acl = authz_schema.ACLEntry.from_model(entry)

        async with self.session as session:
            policy = await _find_room_policy(room_id, session)

            if policy is None:
                exc = authz.NoSuchRoomPolicy(room_id=room_id)
                self._audit.acl_entry_add_failed(
                    room_id, entry, reason=str(exc)
                )
                raise exc

            await policy.awaitable_attrs.acl_entries
            for existing in list(policy.acl_entries):
                if (
                    (new_acl.everyone and existing.everyone)
                    or (new_acl.authenticated and existing.authenticated)
                    or (
                        new_acl.json_path is not None
                        and existing.json_path == new_acl.json_path
                    )
                ):
                    await session.delete(existing)

            new_acl.room_policy = policy
            session.add(new_acl)
        self._audit.acl_entry_added(room_id, entry)

    async def remove_acl_entry(
        self,
        room_id: str,
        entry: models.ACLEntryUnchecked,
    ) -> None:
        """Remove the matching ACL entry from the room's policy.

        Matches stored entries by 'allow_deny' and discriminator. 'entry'
        is the unchecked model so a stored 'json_path' that no longer
        compiles can still be matched; the entry is not re-validated.

        Raises 'NoSuchRoomPolicy' if the room has no policy, or
        'NoSuchACLEntry' if no stored entry matches.
        """
        everyone, authenticated, json_path = _entry_discriminator(entry)

        async with self.session as session:
            policy = await _find_room_policy(room_id, session)

            if policy is None:
                exc = authz.NoSuchRoomPolicy(room_id=room_id)
                self._audit.acl_entry_remove_failed(
                    room_id, entry, reason=str(exc)
                )
                raise exc

            await policy.awaitable_attrs.acl_entries
            matches = [
                existing
                for existing in policy.acl_entries
                if existing.allow_deny == entry.allow_deny
                and (
                    (everyone and existing.everyone)
                    or (authenticated and existing.authenticated)
                    or (
                        json_path is not None
                        and existing.json_path == json_path
                    )
                )
            ]

            if not matches:
                exc = authz.NoSuchACLEntry(room_id=room_id)
                self._audit.acl_entry_remove_failed(
                    room_id, entry, reason=str(exc)
                )
                raise exc

            for existing in matches:
                await session.delete(existing)
        self._audit.acl_entry_removed(room_id, entry)

    async def set_room_default(
        self,
        room_id: str,
        allow_deny: authz.AllowDeny,
    ) -> None:
        """Set the room policy's 'default_allow_deny'.

        Existing ACL entries are preserved. If the room has no policy, an
        empty one is created with the given default.
        """
        async with self.session as session:
            policy = await _find_room_policy(room_id, session)

            if policy is None:
                session.add(
                    authz_schema.RoomPolicy(
                        room_id=room_id,
                        default_allow_deny=allow_deny,
                    )
                )
            else:
                policy.default_allow_deny = allow_deny
        self._audit.room_default_set(room_id, allow_deny)
