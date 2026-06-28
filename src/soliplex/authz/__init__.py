from __future__ import annotations

import abc
import enum
import json
import re
import typing

import jsonpath

# Avoid circular import when only used for typing
# from soliplex import models

UserToken = dict[str, typing.Any]

# Single shared environment so metaconfig hooks can inject additional
# filter functions in one place.
the_jsonpath_environment = jsonpath.JSONPathEnvironment()

# Names of the RFC 9535 built-in filter functions, captured before any
# metaconfig registration. Anything added to the environment beyond these
# was supplied by config, so the metaconfig can round-trip just those.
BUILTIN_JSONPATH_FUNCTION_NAMES = frozenset(
    the_jsonpath_environment.function_extensions
)


class ReservedJSONPathFunctionName(ValueError):
    """Raised when a registration would replace an RFC 9535 built-in."""

    def __init__(self, name: str):
        self.name = name
        super().__init__(
            f"Cannot override built-in JSONPath function: {name!r}."
        )


def register_jsonpath_function(name: str, func: typing.Any) -> None:
    """Register a named filter function into the shared environment.

    'func' must conform to python-jsonpath's filter-function protocol
    (a callable, optionally carrying 'arg_types' / 'return_type' for
    RFC 9535 well-typedness checks). It becomes usable inside JSONPath
    filter expressions as 'name(...)'.

    Raises 'ReservedJSONPathFunctionName' if 'name' collides with one of
    the RFC 9535 built-ins.
    """
    if name in BUILTIN_JSONPATH_FUNCTION_NAMES:
        raise ReservedJSONPathFunctionName(name)
    the_jsonpath_environment.function_extensions[name] = func


def registered_jsonpath_functions() -> dict[str, typing.Any]:
    """Filter functions added via 'register_jsonpath_function'.

    Excludes the RFC 9535 built-ins, leaving only the config-supplied
    functions (e.g. for metaconfig round-tripping).
    """
    return {
        name: func
        for name, func in the_jsonpath_environment.function_extensions.items()
        if name not in BUILTIN_JSONPATH_FUNCTION_NAMES
    }


class InvalidJSONPath(ValueError):
    """Raised when a JSONPath query string fails to compile."""

    def __init__(self, value: str):
        self.value = value
        super().__init__(f"Invalid JSONPath: {value!r}")


class ExactlyOneDiscriminator(ValueError):
    """Raised when an ACL entry does not set exactly one discriminator."""

    def __init__(self, discriminators: typing.Iterable[str]):
        self.discriminators = tuple(discriminators)
        got = ", ".join(self.discriminators) or "(none)"
        super().__init__(
            f"ACLEntry requires exactly one discriminator; got: {got}."
        )


class NoSuchAdminUser(ValueError):
    """Raised when no admin user matches a given JSONPath discriminator."""

    def __init__(self, json_path):
        self.json_path = json_path
        super().__init__(f"No admin user exists with json_path: {json_path}")


class AdminUserExists(ValueError):
    """Raised when an admin user already exists for a discriminator."""

    def __init__(self, json_path):
        self.json_path = json_path
        super().__init__(
            f"Admin user already exists with json_path: {json_path}"
        )


class NoSuchRoomPolicy(ValueError):
    """Raised when no authorization policy exists for a room."""

    def __init__(self, room_id):
        self.room_id = room_id
        super().__init__(f"No policy exists for room: {room_id}")


class NoSuchACLEntry(ValueError):
    """Raised when no stored ACL entry matches a room operation."""

    def __init__(self, room_id):
        self.room_id = room_id
        super().__init__(f"No matching ACL entry in room: {room_id}")


def validate_json_path(value: str | None) -> str | None:
    """Validate a JSONPath query string.

    Returns ``value`` unchanged for ``None`` or a syntactically valid
    RFC 9535 query.  Raises ``InvalidJSONPath`` for malformed queries
    so that callers (pydantic field validators, SQLAlchemy
    ``@validates`` hooks) can reject bad values at write time rather
    than failing later inside ``check_token``.
    """
    if value is None:
        return value
    try:
        the_jsonpath_environment.compile(value)
    except jsonpath.JSONPathError as exc:
        raise InvalidJSONPath(value) from exc
    return value


def token_field_json_path(field: str, value: str) -> str:
    """Build a JSONPath query matching ``token[field] == value``.

    Used to translate the legacy ``preferred_username`` and ``email``
    ACL discriminators into RFC 9535 queries stored in
    ``ACLEntry.json_path`` (those columns are being removed).  The
    caller is responsible for passing a safe ``field`` identifier --
    the value is JSON-encoded so embedded quotes round-trip safely.
    """
    return f"$[?$.{field} == {json.dumps(value)}]"


_TOKEN_FIELD_JSON_PATH_RE = re.compile(
    r"^\$\[\?\$\.(?P<field>[A-Za-z_][A-Za-z0-9_]*) == (?P<value>.+)\]$"
)


def parse_token_field_json_path(value: str) -> tuple[str, str] | None:
    """Inverse of ``token_field_json_path``.

    Returns ``(field, string_value)`` when ``value`` has the exact shape
    produced by ``token_field_json_path``, otherwise ``None`` (e.g. for
    a general-purpose JSONPath query that was authored directly).
    """
    match = _TOKEN_FIELD_JSON_PATH_RE.match(value)
    if match is None:
        return None
    try:
        decoded = json.loads(match.group("value"))
    except json.JSONDecodeError:
        return None
    if not isinstance(decoded, str):
        return None
    return match.group("field"), decoded


class AllowDeny(enum.Enum):
    ALLOW = "allow"
    DENY = "deny"


class AdminUserPolicy(abc.ABC):
    """Protocol for checking / managing admin-user discriminators."""

    @abc.abstractmethod
    async def list_admin_user_discriminators(self) -> list[str]:
        """List JSONPath discriminators which identify admin users.

        Discriminators may be tied to individuals (e.g., via their
        email addresses), or to claims which identify groups or
        roles attached to the user.
        """

    @abc.abstractmethod
    async def add_admin_user_discriminator(self, json_path: str):
        """Add a user discriminator to the admin users table.

        Discriminators may be tied to individuals (e.g., via their
        email addresses), or to claims which identify groups or
        roles attached to the user.
        """

    @abc.abstractmethod
    async def remove_admin_user_discriminator(self, json_path: str):
        """Remove a user discriminator from the admin users table.

        Discriminators may be tied to individuals (e.g., via their
        email addresses), or to claims which identify groups or
        roles attached to the user.
        """

    @abc.abstractmethod
    async def clear_admin_user_discriminators(self):
        """Remove all admin user discriminators from the admin users table."""

    @abc.abstractmethod
    async def list_admin_users(self) -> list[str]:
        """Deprecated alias for 'list_admin_user_discriminators'."""

    @abc.abstractmethod
    async def add_admin_user(self, email: str):
        """Deprecated alias for 'add_admin_user_discriminator'.

        Translates 'email' to the equivalent JSONPath expression,
        '$[?$.email == "..."]', then delegates.
        """

    @abc.abstractmethod
    async def remove_admin_user(self, email: str):
        """Deprecated alias for 'remove_admin_user_discriminator'.

        Translates 'email' to the equivalent JSONPath expression,
        '$[?$.email == "..."]', then delegates.
        """

    @abc.abstractmethod
    async def check_admin_access(self, user_token: UserToken) -> bool:
        """Is the user represented by 'user_token' an admin user?

        Matches 'user_token' against each admin entry's JSONPath query;
        the user is an admin when any query matches.
        """


class RoomAuthorizationPolicy(abc.ABC):
    """Protocol for checking / managing room authorization policies."""

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
    ) -> models.RoomPolicy | None:  # noqa: F821
        """Return the authorization policy for the room"""

    @abc.abstractmethod
    async def update_room_policy(
        self,
        room_id: str,
        room_policy: models.RoomPolicy,  # noqa: F821
    ) -> None:
        """Update the authorization policy for the room"""

    @abc.abstractmethod
    async def delete_room_policy(
        self,
        room_id: str,
    ) -> None:
        """Delete the authorization policy for the room"""

    @abc.abstractmethod
    async def get_room_policy_unchecked(
        self,
        room_id: str,
    ) -> models.RoomPolicyUnchecked | None:  # noqa: F821
        """Return the room policy, tolerating non-compiling 'json_path's."""

    @abc.abstractmethod
    async def list_room_policies(
        self,
    ) -> list[models.RoomPolicyUnchecked]:  # noqa: F821
        """List every stored room policy as an unchecked model.

        Each policy is returned as the unchecked model -- the analogue
        of 'get_room_policy_unchecked' over the whole table -- so a
        stored ACL entry whose 'json_path' no longer compiles is
        surfaced rather than raising, exactly what an audit needs. The
        order is unspecified.
        """

    @abc.abstractmethod
    async def clear_room_acl(self, room_id: str) -> None:
        """Remove all ACL entries from the room's policy.

        The policy row and its 'default_allow_deny' are preserved.
        """

    @abc.abstractmethod
    async def add_acl_entry(
        self,
        room_id: str,
        entry: models.ACLEntry,  # noqa: F821
    ) -> None:
        """Add an ACL entry to the room's policy, replacing any entry with
        the same discriminator."""

    @abc.abstractmethod
    async def remove_acl_entry(
        self,
        room_id: str,
        entry: models.ACLEntryUnchecked,  # noqa: F821
    ) -> None:
        """Remove the matching ACL entry from the room's policy."""

    @abc.abstractmethod
    async def set_room_default(
        self,
        room_id: str,
        allow_deny: AllowDeny,
    ) -> None:
        """Set the room policy's 'default_allow_deny', creating an empty
        policy if none exists."""
