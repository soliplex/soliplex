from __future__ import annotations

import datetime
import typing

import sqlalchemy
from sqlalchemy import orm as sqla_orm
from sqlalchemy import schema as sqla_schema
from sqlalchemy.ext import asyncio as sqla_asyncio
from sqlalchemy.sql import sqltypes as sqla_sqltypes

from soliplex import authz as authz_package
from soliplex import models
from soliplex import util
from soliplex.config import installation as config_installation

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


def get_engine(
    *,
    engine_url=config_installation.SYNC_MEMORY_ENGINE_URL,
    init_schema=False,
    **engine_kwargs,
) -> sqlalchemy.Engine:
    engine = sqlalchemy.create_engine(
        engine_url,
        json_serializer=util.serialize_sqla_json,
        **engine_kwargs,
    )
    if init_schema:
        with engine.connect() as connection:
            Base.metadata.create_all(connection)

    return engine


def get_session(
    *,
    engine_url=config_installation.SYNC_MEMORY_ENGINE_URL,
    init_schema=False,
    **engine_kwargs,
) -> sqla_orm.Session:
    engine = get_engine(
        engine_url=engine_url,
        init_schema=init_schema,
        **engine_kwargs,
    )
    return sqla_orm.Session(bind=engine)


async def get_async_engine(
    *,
    engine_url=config_installation.ASYNC_MEMORY_ENGINE_URL,
    init_schema=False,
    **engine_kwargs,
):
    engine = sqla_asyncio.create_async_engine(
        engine_url,
        json_serializer=util.serialize_sqla_json,
        **engine_kwargs,
    )

    if init_schema:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    return engine


async def get_async_session(
    *,
    engine_url=config_installation.ASYNC_MEMORY_ENGINE_URL,
    init_schema=False,
    **engine_kwargs,
):
    engine = await get_async_engine(
        engine_url=engine_url,
        init_schema=init_schema,
        **engine_kwargs,
    )
    return sqla_asyncio.AsyncSession(bind=engine)
