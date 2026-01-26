from __future__ import annotations

import contextlib
import datetime
import typing

import sqlalchemy
from sqlalchemy import orm as sqla_orm
from sqlalchemy import schema as sqla_schema
from sqlalchemy import sql as sqla_sql
from sqlalchemy.ext import asyncio as sqla_asyncio
from sqlalchemy.sql import sqltypes as sqla_sqltypes

from soliplex import authz as authz_package
from soliplex import config
from soliplex import models

AsyncAttrs = sqla_asyncio.AsyncAttrs
DeclarativeBase = sqla_orm.DeclarativeBase
ForeignKey = sqlalchemy.ForeignKey
Mapped = sqla_orm.Mapped
mapped_column = sqla_orm.mapped_column
relationship = sqla_orm.relationship


def _timestamp() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)  # noqa UP07


# Recommended naming convention used by Alembic, as various different database
# providers will autogenerate vastly different names making migrations more
# difficult. See: https://alembic.sqlalchemy.org/en/latest/naming.html
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

JSON_Mapped_From = dict[str, typing.Any]

metadata = sqla_schema.MetaData(naming_convention=NAMING_CONVENTION)


class Base(AsyncAttrs, DeclarativeBase):
    metadata = metadata
    type_annotation_map = {
        JSON_Mapped_From: sqla_sqltypes.JSON,
    }


class AdminUser(Base):
    """Info for users configured as admins.

    'email': email address
    """

    __tablename__ = "admin_users"

    id_: Mapped[int] = mapped_column(primary_key=True)

    email: Mapped[str] = mapped_column(unique=True)

    created: Mapped[datetime.datetime] = mapped_column(
        sqla_sqltypes.TIMESTAMP(timezone=True),
        default=_timestamp,
    )


class RoomPolicy(Base):
    """Describe authorization policy for a room

    'room_id': name of the room (distinct from our actual primary key).

    'default_allow_deny': whether the room is allowed / denied if no
        ACLEntry matches the user's token.

    'acl_entries": stored in the 'RoomACLEntry' table via a
        one-to-many relationship.
    """

    __tablename__ = "room_policies"

    id_: Mapped[int] = mapped_column(primary_key=True)

    room_id: Mapped[str] = mapped_column(unique=True)

    created: Mapped[datetime.datetime] = mapped_column(
        sqla_sqltypes.TIMESTAMP(timezone=True),
        default=_timestamp,
    )

    default_allow_deny: Mapped[authz_package.AllowDeny] = mapped_column(
        default=authz_package.AllowDeny.DENY,
    )

    acl_entries: Mapped[list[ACLEntry]] = relationship(
        back_populates="room_policy",
        order_by="ACLEntry.created",
        cascade="all, delete",
        passive_deletes=True,
    )

    @classmethod
    def from_model(cls, model: models.RoomPolicy):
        return cls(
            room_id=model.room_id,
            default_allow_deny=model.default_allow_deny,
            acl_entries=[
                ACLEntry.from_model(model=acl_entry_model)
                for acl_entry_model in model.acl_entries
            ],
        )

    @property
    def as_model(self) -> models.RoomPolicy:
        acl_entries = [acl_entry.as_model for acl_entry in self.acl_entries]
        return models.RoomPolicy(
            room_id=self.room_id,
            default_allow_deny=self.default_allow_deny,
            acl_entries=acl_entries,
        )

    def check_token(
        self,
        user_token: authz_package.UserToken | None,
    ) -> authz_package.AllowDeny:
        """Check the supplied token against our ACL entries

        If one of them returns non-None, return that value.

        Otherwise, return our 'default_allow_deny'.
        """
        for entry in self.acl_entries:
            found = entry.check_token(user_token)

            if found is not None:
                return found

        return self.default_allow_deny


class ACLEntry(Base):
    """Allow / deny access to a room based on fields in the user's token"""

    __tablename__ = "room_acl_entries"

    id_: Mapped[int] = mapped_column(primary_key=True)

    room_policy_id_: Mapped[int] = mapped_column(
        ForeignKey("room_policies.id_", ondelete="CASCADE"),
    )
    room_policy: sqla_orm.Mapped[RoomPolicy] = relationship(
        back_populates="acl_entries",
    )

    created: Mapped[datetime.datetime] = mapped_column(
        sqla_sqltypes.TIMESTAMP(timezone=True),
        default=_timestamp,
    )

    allow_deny: Mapped[authz_package.AllowDeny]

    # Discriminators
    everyone: Mapped[bool] = mapped_column(default=False)
    authenticated: Mapped[bool] = mapped_column(default=False)
    preferred_username: Mapped[str | None] = mapped_column(default=None)
    email: Mapped[str | None] = mapped_column(default=None)

    @classmethod
    def from_model(cls, model: models.ACLEntry):
        return cls(
            allow_deny=model.allow_deny,
            everyone=model.everyone,
            authenticated=model.authenticated,
            preferred_username=model.preferred_username,
            email=model.email,
        )

    @property
    def as_model(self) -> models.ACLEntry:
        return models.ACLEntry(
            allow_deny=self.allow_deny,
            everyone=self.everyone,
            authenticated=self.authenticated,
            preferred_username=self.preferred_username,
            email=self.email,
        )

    def check_token(
        self,
        user_token: authz_package.UserToken | None,
    ) -> authz_package.AllowDeny | None:
        """Check the supplied token against our discriminators

        If 'user_token' matches one of our discriminators, return our flag

        Otherwise, return None.
        """
        if self.everyone:
            return self.allow_deny

        if self.authenticated:
            if user_token is not None:
                return self.allow_deny

        token = user_token or {}

        if self.preferred_username is not None:
            if token.get("preferred_username") == self.preferred_username:
                return self.allow_deny

        if self.email is not None:
            if token.get("email") == self.email:
                return self.allow_deny

        return None


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


async def _find_admin_user(
    email: str,
    session,
) -> AdminUser | None:
    query = sqla_sql.select(AdminUser).where(AdminUser.email == email)
    user = (await session.scalars(query)).first()

    return user


async def _find_room_policy(
    room_id: str,
    session,
) -> RoomPolicy | None:
    query = sqla_sql.select(RoomPolicy).where(RoomPolicy.room_id == room_id)
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

    async def add_admin_user(self, email: str):
        """Add a user to the admin users table."""
        async with self.session as session:
            user = await _find_admin_user(email, session)

            if user is not None:
                raise AdminUserExists(email=email)

            user = AdminUser(email=email)
            session.add(user)

    async def remove_admin_user(self, email: str):
        """Remove a user from the admin users table."""
        async with self.session as session:
            user = await _find_admin_user(email, session)

            if user is None:
                raise NoSuchAdminUser(email=email)

            await session.delete(user)

    async def check_admin_access(
        self,
        user_token: authz_package.UserToken,
    ) -> bool:
        """Is the user represented by 'user_token' an admin user?"""
        async with self.session as session:
            user = await _find_admin_user(user_token["email"], session)

        return user is not None

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
            email = user_token["email"]
            user = await _find_admin_user(email, session)

            if user is None:
                raise NotAdminUser(email)

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
            email = user_token["email"]
            user = await _find_admin_user(email, session)

            if user is None:
                raise NotAdminUser(email)

            policy = await _find_room_policy(room_id, session)

            if policy is not None:
                await policy.awaitable_attrs.acl_entries

                async with session.begin_nested():
                    await session.delete(policy)

            new_policy = RoomPolicy.from_model(room_policy)

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
            email = user_token["email"]
            user = await _find_admin_user(email, session)

            if user is None:
                raise NotAdminUser(email)

            policy = await _find_room_policy(room_id, session)

            if policy is not None:
                async with session.begin_nested():
                    await session.delete(policy)


async def get_async_session(
    engine_url=config.ASYNC_MEMORY_ENGINE_URL,
    init_schema=False,
    **engine_kwargs,
):
    engine = sqla_asyncio.create_async_engine(engine_url, **engine_kwargs)

    if init_schema:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    return sqla_asyncio.AsyncSession(bind=engine)


def get_session(
    engine_url=config.SYNC_MEMORY_ENGINE_URL,
    init_schema=False,
    **engine_kwargs,
):
    engine = sqlalchemy.create_engine(engine_url, **engine_kwargs)

    if init_schema:
        with engine.connect() as connection:
            Base.metadata.create_all(connection)

    return sqla_orm.Session(bind=engine)
