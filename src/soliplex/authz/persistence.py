"""Implement 'authz.AuthorizationPolicy' using SQLAlchemy persistence"""

from __future__ import annotations

import contextlib

from sqlalchemy import sql as sqla_sql
from sqlalchemy.ext import asyncio as sqla_asyncio

from soliplex import authz as authz_package
from soliplex import models
from soliplex.authz import schema as authz_schema


class NoSuchAdminUser(ValueError):
    def __init__(self, email):
        self.email = email
        super().__init__(f"No admin user exists with email: {email}")


class AdminUserExists(ValueError):
    def __init__(self, email):
        self.email = email
        super().__init__(f"Admin user already exists with email: {email}")


class NotAdminUser(ValueError):
    def __init__(self, email):
        self.email = email
        super().__init__(f"Non-admin user, email: {email}")


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


class AuthorizationPolicy(authz_package.AuthorizationPolicy):
    def __init__(self, session: sqla_asyncio.AsyncSession):
        self._session = session

    @property
    @contextlib.asynccontextmanager
    async def session(self):
        async with self._session.begin():
            yield self._session

    async def list_admin_users(self) -> list[str]:
        """List admin users in the admin users table.

        An email-keyed admin (stored as '$[?$.email == "..."]') is
        surfaced as its email; an admin created with a non-email
        JSONPath query is surfaced as the raw query string.
        """
        query = sqla_sql.select(authz_schema.AdminUser)
        async with self.session as session:
            result = []
            for admin_user in await session.scalars(query):
                parsed = authz_package.parse_token_field_json_path(
                    admin_user.json_path
                )
                if parsed is not None and parsed[0] == "email":
                    result.append(parsed[1])
                else:
                    result.append(admin_user.json_path)
            return result

    async def add_admin_user(self, email: str):
        """Add a user to the admin users table, keyed by email."""
        json_path = authz_package.token_field_json_path("email", email)
        async with self.session as session:
            user = await _find_admin_user_by_json_path(json_path, session)

            if user is not None:
                raise AdminUserExists(email=email)

            user = authz_schema.AdminUser(json_path=json_path)
            session.add(user)

    async def remove_admin_user(self, email: str):
        """Remove a user from the admin users table, keyed by email."""
        json_path = authz_package.token_field_json_path("email", email)
        async with self.session as session:
            user = await _find_admin_user_by_json_path(json_path, session)

            if user is None:
                raise NoSuchAdminUser(email=email)

            await session.delete(user)

    async def check_admin_access(
        self,
        user_token: authz_package.UserToken,
    ) -> bool:
        """Is the user represented by 'user_token' an admin user?"""
        async with self.session as session:
            return await _user_is_admin(user_token, session)

    async def check_room_access(
        self,
        room_id: str,
        user_token: authz_package.UserToken | None,
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
            return allow_deny == authz_package.AllowDeny.ALLOW
        else:
            return True

    async def filter_room_ids(
        self,
        room_ids: list[str],
        user_token: authz_package.UserToken | None,
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
                    if allow_deny != authz_package.AllowDeny.ALLOW:
                        continue
                result.append(room_id)

        return result

    async def get_room_policy(
        self,
        room_id: str,
        user_token: authz_package.UserToken,
    ) -> models.RoomPolicy | None:
        """Return the authorization policy for the room"""
        async with self.session as session:
            if not await _user_is_admin(user_token, session):
                raise NotAdminUser(user_token["email"])

            policy = await _find_room_policy(room_id, session)

        if policy is not None:
            await policy.awaitable_attrs.acl_entries
            return policy.as_model

        return None

    async def update_room_policy(
        self,
        room_id: str,
        room_policy: models.RoomPolicy,
        user_token: authz_package.UserToken,
    ) -> None:
        """Update the authorization policy for the room"""
        async with self.session as session:
            if not await _user_is_admin(user_token, session):
                raise NotAdminUser(user_token["email"])

            policy = await _find_room_policy(room_id, session)

            if policy is not None:
                await policy.awaitable_attrs.acl_entries

                async with session.begin_nested():
                    await session.delete(policy)

            new_policy = authz_schema.RoomPolicy.from_model(room_policy)

            async with session.begin_nested():
                session.add(new_policy)

        return None

    async def delete_room_policy(
        self,
        room_id: str,
        user_token: authz_package.UserToken,
    ) -> None:
        """Delete any existing authorization policy for the room"""
        async with self.session as session:
            if not await _user_is_admin(user_token, session):
                raise NotAdminUser(user_token["email"])

            policy = await _find_room_policy(room_id, session)

            if policy is not None:
                async with session.begin_nested():
                    await session.delete(policy)
