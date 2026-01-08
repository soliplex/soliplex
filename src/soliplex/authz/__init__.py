from __future__ import annotations

import abc
import enum
import typing

import fastapi
from sqlalchemy.ext import asyncio as sqla_asyncio

UserToken = dict[str, typing.Any]


class AllowDeny(enum.Enum):
    ALLOW = "allow"
    DENY = "deny"


class RoomAuthorization(abc.ABC):
    """Protocol for checking / managing room authorization policies"""

    @abc.abstractmethod
    async def check_room_access(
        self,
        room_id: str,
        user_token: UserToken | None,
    ) -> bool:
        """Can the user represented by 'user_token' can access a room?"""

    @abc.abstractmethod
    async def filter_room_ids(
        self,
        room_ids: list[str],
        user_token: UserToken | None,
    ) -> list[str]:
        """Filter room IDs based on room authz policies for 'user_token'"""


async def get_the_room_authz(request: fastapi.Request) -> RoomAuthorization:
    from . import schema

    engine = request.state.room_authz_engine
    async with sqla_asyncio.AsyncSession(bind=engine) as session:
        yield schema.RoomAuthorization(session)


depend_the_room_authz = fastapi.Depends(get_the_room_authz)
