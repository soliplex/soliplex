from __future__ import annotations

import abc
import enum
import typing

import fastapi
from sqlalchemy.ext import asyncio as sqla_asyncio

# Avoid circular import when only used for typing
# from soliplex import models

UserToken = dict[str, typing.Any]


class AllowDeny(enum.Enum):
    ALLOW = "allow"
    DENY = "deny"


class AuthorizationPolicy(abc.ABC):
    """Protocol for checking / managing authorization policies"""

    @abc.abstractmethod
    async def list_admin_users(self) -> list[str]:
        """List user emails in the admin users table."""

    @abc.abstractmethod
    async def add_admin_user(self, email: str):
        """Add a user to the admin users table."""

    @abc.abstractmethod
    async def remove_admin_user(self, email: str):
        """Remove a user from the admin users table."""

    @abc.abstractmethod
    async def check_admin_access(self, user_token: UserToken) -> bool:
        """Is the user represented by 'user_token' an admin user?"""

    @abc.abstractmethod
    async def check_room_access(
        self,
        room_id: str,
        user_token: UserToken | None,
    ) -> bool:
        """Can the user represented by 'user_token' access a room?"""

    @abc.abstractmethod
    async def filter_room_ids(
        self,
        room_ids: list[str],
        user_token: UserToken | None,
    ) -> list[str]:
        """Filter room IDs based on room authz policies for 'user_token'"""

    @abc.abstractmethod
    async def get_room_policy(
        self,
        room_id: str,
        user_token: UserToken,
    ) -> models.RoomPolicy | None:  # noqa: F821
        """Return the authorization policy for the room"""

    @abc.abstractmethod
    async def update_room_policy(
        self,
        room_id: str,
        room_policy: models.RoomPolicy,  # noqa: F821
        user_token: UserToken,
    ) -> None:
        """Update the authorization policy for the room"""

    @abc.abstractmethod
    async def delete_room_policy(
        self,
        room_id: str,
        user_token: UserToken,
    ) -> None:
        """Delete the authorization policy for the room"""


async def get_the_authz_policy(
    request: fastapi.Request,
) -> AuthorizationPolicy:
    from . import schema

    engine = request.state.authorization_engine
    async with sqla_asyncio.AsyncSession(bind=engine) as session:
        yield schema.AuthorizationPolicy(session)


depend_the_authz_policy = fastapi.Depends(get_the_authz_policy)
