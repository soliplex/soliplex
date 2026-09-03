from __future__ import annotations

import datetime
import typing

import sqlalchemy
from sqlalchemy import orm as sqla_orm
from sqlalchemy import schema as sqla_schema
from sqlalchemy.ext import asyncio as sqla_asyncio
from sqlalchemy.sql import sqltypes as sqla_sqltypes

from soliplex import authz
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
    return datetime.datetime.now(datetime.UTC)


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

    'json_path': an RFC 9535 JSONPath query matched against the user
        token; the user is an admin when the query matches at least one
        node. Email-keyed admins are stored as '$[?$.email == "..."]'
        (see 'authz.token_field_json_path'), mirroring how 'ACLEntry'
        stores its 'email' / 'preferred_username' discriminators.
    """

    __tablename__ = "admin_users"

    id_: Mapped[int] = mapped_column(primary_key=True)

    json_path: Mapped[str] = mapped_column(unique=True)

    created: Mapped[datetime.datetime] = mapped_column(
        sqla_sqltypes.TIMESTAMP(timezone=True),
        default=_timestamp,
    )

    @sqla_orm.validates("json_path")
    def _check_json_path(self, _key, value):
        return authz.validate_json_path(value)

    def check_token(
        self,
        user_token: authz.UserToken | None,
    ) -> bool:
        """Does 'user_token' match our JSONPath query?"""
        token = user_token or {}
        match = authz.the_jsonpath_environment.match(self.json_path, token)
        return match is not None


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

    default_allow_deny: Mapped[authz.AllowDeny] = mapped_column(
        default=authz.AllowDeny.DENY,
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

    @property
    def as_unchecked_model(self) -> models.RoomPolicyUnchecked:
        # Like 'as_model' but builds the unchecked model, so a stored ACL
        # entry whose 'json_path' no longer compiles does not raise.
        acl_entries = [
            acl_entry.as_unchecked_model for acl_entry in self.acl_entries
        ]
        return models.RoomPolicyUnchecked(
            room_id=self.room_id,
            default_allow_deny=self.default_allow_deny,
            acl_entries=acl_entries,
        )

    def check_token(
        self,
        user_token: authz.UserToken | None,
    ) -> authz.AllowDeny:
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

    allow_deny: Mapped[authz.AllowDeny]

    # Discriminators
    everyone: Mapped[bool] = mapped_column(default=False)
    authenticated: Mapped[bool] = mapped_column(default=False)
    json_path: Mapped[str | None] = mapped_column(default=None)

    @sqla_orm.validates("json_path")
    def _check_json_path(self, _key, value):
        return authz.validate_json_path(value)

    @classmethod
    def from_model(cls, model: models.ACLEntry):
        # 'preferred_username' and 'email' are expressed in the public
        # model but stored as equivalent JSONPath queries (highest
        # priority first, matching the legacy check_token order). The
        # public model's validator guarantees exactly one discriminator,
        # so no shadowing is possible here.
        if model.preferred_username is not None:
            json_path = authz.token_field_json_path(
                "preferred_username", model.preferred_username
            )
        elif model.email is not None:
            json_path = authz.token_field_json_path("email", model.email)
        else:
            json_path = model.json_path
        return cls(
            allow_deny=model.allow_deny,
            everyone=model.everyone,
            authenticated=model.authenticated,
            json_path=json_path,
        )

    def _model_kwargs(self) -> dict[str, str]:
        # Surface a stored 'preferred_username' / 'email' query back as
        # the matching public model field; leave general-purpose
        # queries as 'json_path'.
        kwargs: dict[str, str] = {}
        if self.json_path is not None:
            parsed = authz.parse_token_field_json_path(self.json_path)
            if parsed is not None and parsed[0] in (
                "preferred_username",
                "email",
            ):
                kwargs[parsed[0]] = parsed[1]
            else:
                kwargs["json_path"] = self.json_path
        return kwargs

    @property
    def as_model(self) -> models.ACLEntry:
        return models.ACLEntry(
            allow_deny=self.allow_deny,
            everyone=self.everyone,
            authenticated=self.authenticated,
            **self._model_kwargs(),
        )

    @property
    def as_unchecked_model(self) -> models.ACLEntryUnchecked:
        # Like 'as_model' but builds the unchecked model, so a stored
        # 'json_path' that no longer compiles does not raise.
        return models.ACLEntryUnchecked(
            allow_deny=self.allow_deny,
            everyone=self.everyone,
            authenticated=self.authenticated,
            **self._model_kwargs(),
        )

    def check_token(
        self,
        user_token: authz.UserToken | None,
    ) -> authz.AllowDeny | None:
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

        if self.json_path is not None:
            jp_match = authz.the_jsonpath_environment.match(
                self.json_path, token
            )
            if jp_match is not None:
                return self.allow_deny

        return None

    def _check_exactly_one_discriminator(self) -> None:
        active = [
            name
            for name, is_set in (
                ("everyone", self.everyone),
                ("authenticated", self.authenticated),
                ("json_path", self.json_path is not None),
            )
            if is_set
        ]
        if len(active) != 1:
            raise authz.ExactlyOneDiscriminator(active)


@sqlalchemy.event.listens_for(ACLEntry, "before_insert")
@sqlalchemy.event.listens_for(ACLEntry, "before_update")
def _acl_entry_check_discriminator(_mapper, _connection, target) -> None:
    target._check_exactly_one_discriminator()


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

    @sqlalchemy.event.listens_for(engine, "connect")
    def _set_sqlite_pragma(  # pragma: no cover
        dbapi_connection, connection_record
    ):
        # SQLite ignores foreign-key constraints -- and hence the
        # 'ON DELETE CASCADE' on room_acl_entries -- unless they are
        # enabled per connection. Mirrors
        # 'soliplex.installation._set_sqlite_pragma' (issue #950) for the
        # sync engine the CLI uses; without it, deleting a RoomPolicy
        # orphans its ACL rows instead of cascading.
        if engine.dialect.name != "sqlite":
            return
        cursor_fk = dbapi_connection.cursor()
        cursor_fk.execute("PRAGMA foreign_keys=ON")
        cursor_fk.close()

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
