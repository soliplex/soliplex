from __future__ import annotations

import abc
import enum
import functools
import json
import re
import typing

import jsonpath
from jsonpath import filter as jp_filter

# Avoid circular import when only used for typing

if typing.TYPE_CHECKING:  # avoid an import cycle at runtime
    from soliplex import models

UserToken = dict[str, typing.Any]

# Single shared environment so metaconfig hooks can inject additional
# filter functions in one place.
the_jsonpath_environment = jsonpath.JSONPathEnvironment()

# Set on the wrapper installed by 'register_jsonpath_function', so that
# re-registering a wrapper replaces rather than re-wraps it.
_WRAPPED_FILTER_MARKER = "__soliplex_wrapped_filter__"

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


class InvalidPredicateResult(ValueError):
    """Raised when a registered JSONPath filter function returns None.

    python-jsonpath counts ``None`` (JSON ``null``) as an extant, truthy
    value inside a filter expression ('JSONPathEnvironment.is_truthy'),
    so a predicate returning it on miss would match every token with at
    least one claim. The wrapper installed by
    'register_jsonpath_function' fails closed by raising this error when
    the query runs instead.
    """

    def __init__(self, name: str):
        self.name = name
        super().__init__(
            f"Filter function {name!r} returned None; authz predicates"
            f" must not return None."
        )


def register_jsonpath_function(name: str, func: typing.Any) -> None:
    """Register a named filter function into the shared environment.

    'func' must conform to python-jsonpath's filter-function protocol
    (a callable, optionally carrying 'arg_types' / 'return_type' for
    RFC 9535 well-typedness checks). It becomes usable inside JSONPath
    filter expressions as 'name(...)'.

    The stored callable is wrapped:  a call returning 'None' raises
    'InvalidPredicateResult' when the query runs; any other result
    passes through unchanged, with the engine's usual truthiness rules
    deciding the match.  'functools.wraps' carries 'func's identity, so
    metaconfig round-tripping via 'registered_jsonpath_functions' still
    resolves the original dotted name.

    Raises 'ReservedJSONPathFunctionName' if 'name' collides with one of
    the RFC 9535 built-ins.
    """
    while getattr(func, _WRAPPED_FILTER_MARKER, False):
        func = func.__wrapped__

    if name in BUILTIN_JSONPATH_FUNCTION_NAMES:
        raise ReservedJSONPathFunctionName(name)

    @functools.wraps(func)
    def wrapped_filter_function(*args, **kwargs):
        result = func(*args, **kwargs)

        if result is None:
            raise InvalidPredicateResult(name)

        return result

    setattr(wrapped_filter_function, _WRAPPED_FILTER_MARKER, True)
    the_jsonpath_environment.function_extensions[name] = (
        wrapped_filter_function
    )


def registered_jsonpath_functions() -> dict[str, typing.Any]:
    """Filter functions added via 'register_jsonpath_function'.

    Excludes the RFC 9535 built-ins, leaving only the config-supplied
    functions (e.g. for metaconfig round-tripping):  each entry is the
    wrapper installed by 'register_jsonpath_function', whose
    '__module__' / '__name__' still name the registered function.
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


class JSONPathMatchesNull(ValueError):
    """Raised when a JSONPath query string can return 'null' values"""

    def __init__(self, value: str):
        self.value = value
        super().__init__(f"JSONPath matches null: {value!r}")


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
    RFC 9535 query.  Raises ``InvalidJSONPath`` for malformed queries,
    and for blank queries (all whitespace), which compile but match
    every token:  a blank 'ALLOW' entry would grant everyone.  Callers
    (pydantic field validators, SQLAlchemy ``@validates`` hooks) can
    reject bad values at write time rather than failing later inside
    ``check_token``.
    """
    if value is None:
        return value
    if not value.strip():
        raise InvalidJSONPath(value)
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


def discriminator_claim_names(json_path: str) -> list[str]:
    """Extract the claim names referenced by a stored json_path.

    Returns the (sorted) distinct claim names a query can reference
    from the token root:  for each chain of names reachable from '$',
    or from an '@'-relative query under '$' or under one of those
    chains, the chain's first name (so '$.realm_access.roles[0]'
    yields 'realm_access', matching how the authn cookie carries
    claims).

    Parsing uses this environment's own JSONPath compiler, not pattern
    matching:  quoted values, slices, wildcards, unions, recursive
    descent, nested filters and JSONPath function extensions are all
    understood, though claims read only *inside* a function extension
    remain invisible to the audit.

    An unparseable query (e.g. authored under a metaconfig whose filter
    function no longer exists) contributes no claim names:  such rows
    are reported separately, in the invalid JSONPath block.
    """
    try:
        parsed = the_jsonpath_environment.compile(json_path)
    except jsonpath.JSONPathError:
        return []

    claims: set[str] = set()
    _collect_from_segments(parsed.segments, (), claims)
    return sorted(claims)


def _collect_from_segments(
    segments,
    chain: tuple[str, ...],
    claims: set[str],
) -> None:
    """Fold a segment sequence into the claim set, threading 'chain'.

    Each chain's first name is a referenced claim.  Within one segment,
    union selectors each fork from the incoming chain, and the first
    fork's chain continues into later segments.  Wildcard, index and
    slice segments pass the chain through unchanged.
    """
    for segment in segments:
        grown: tuple[str, ...] | None = None

        for selector in segment.selectors:
            name = getattr(selector, "name", None)

            if name is None:
                sub_path = getattr(selector, "query", None)
                if sub_path is not None:
                    _collect_from_segments(sub_path.segments, (), claims)
                    continue

                expression = getattr(selector, "expression", None)
                if expression is not None:
                    _collect_from_expression(expression, chain, claims)
                continue

            forked = (*chain, str(name))
            claims.add(forked[0])
            if grown is None:
                grown = forked

        if grown is not None:
            chain = grown


def _collect_from_expression(
    expression,
    chain: tuple[str, ...],
    claims: set[str],
) -> tuple[str, ...]:
    """Fold a filter expression's claim references into 'claims'.

    Embedded JSONPaths are folded per their kind:  a '$'-anchored query
    re-roots at '$';  an '@'-relative query continues the enclosing
    chain.  Other expressions (infix operators, literals, function
    calls) contribute only their children.
    """
    if isinstance(expression, jp_filter.FilterQuery):
        sub_chain: tuple[str, ...] = chain
        if not isinstance(expression, jp_filter.RelativeFilterQuery):
            sub_chain = ()

        _collect_from_segments(expression.path.segments, sub_chain, claims)
        return chain

    for child in expression.children():
        _collect_from_expression(child, chain, claims)

    return chain


def null_probe_tokens(claim_names: list[str]) -> list[dict]:
    """Build the synthetic tokens null-probing a stored json_path.

    One token seeds every claim name the expression references with
    JSON 'null', plus one token with no claims at all -- the shapes a
    miswritten expression is most likely to match by surprise:  bare
    selectors and presence tests count 'null' as matching,
    '$'-root or constant filters match an empty token outright.

    Claims read only inside a function extension are invisible here;
    matching that depends on nested claim structure cannot be reached
    from the first-name chains either.
    """
    tokens: list[dict] = [{name: None for name in claim_names}]
    if claim_names:
        tokens.append({})
    return tokens


def null_claims_match(json_path: str) -> dict | None:
    """Return the first null-probe token 'json_path' matches, if any.

    Runs the expression against the 'null_probe_tokens' shapes; the
    first match is returned as the evidence for an audit report.

    Queries failing 'validate_json_path' (already reported in the
    invalid block) and queries whose function extensions choke on the
    synthetic claims contribute no flags:  predicate behavior is
    software, audited only insofar as it runs here without complaint.
    """
    try:
        validate_json_path(json_path)
    except InvalidJSONPath:
        return None

    for probe_token in null_probe_tokens(
        discriminator_claim_names(json_path),
    ):
        try:
            if (
                the_jsonpath_environment.match(
                    json_path,
                    probe_token,
                )
                is not None
            ):
                return probe_token
        except Exception:
            continue

    return None


class AllowDeny(enum.Enum):
    ALLOW = "allow"
    DENY = "deny"


class Permission(enum.Enum):
    READ = "read"
    WRITE = "write"
    ADMIN = "admin"


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
    async def is_admin(
        self,
        user_token: UserToken,
    ) -> bool:
        """Is the user represented by 'user_token' an admin user?

        Matches 'user_token' against each admin entry's JSONPath query;
        the user is an admin when any query matches.

        This test is for *non-audit* checks, e.g. to support whether
        the frontend offers an admin-only option:  it is not intended
        for use where an actual admin operation is performed (see
        'check_admin_access' for that case).
        """

    @abc.abstractmethod
    async def check_admin_access(
        self,
        user_token: UserToken,
        *,
        resource: str,
        action: str,
    ) -> bool:
        """Validate that the user represented by 'user_token' is an admin user

        This check is called at the point that an auditable admin action
        is being performed.  It calls the non-audit 'is_admin' check, and then
        creates the audit record, identifying the privileged operation being
        gated using 'resource' / 'action'. Finally, it returns the result
        from 'is_admin'.
        """


class RoomAuthorizationPolicy(abc.ABC):
    """Protocol for checking / managing room authorization policies."""

    @abc.abstractmethod
    async def has_room_permission(
        self,
        room_id: str,
        user_token: UserToken | None,
        *,
        permission: Permission,
    ) -> bool:
        """Does the user have a 'permission' on a given room?

        For a room with an authorization policy, return whether the result
        of its ``check_token`` for the user token and permission is ALLOW.

        For a room without an authorization policy:

        - Return True for READ (such rooms are public for read).

        - Return False for WRITE and ADMIN.

        This test is for *non-audit* checks, e.g. to support whether
        the frontend offers an option which would require the permission:
        it is not intended for use where the actual gated operation is
        performed (see 'check_room_access' for that case).
        """

    @abc.abstractmethod
    async def check_room_access(
        self,
        room_id: str,
        user_token: UserToken | None,
        *,
        permission: Permission,
    ) -> bool:
        """Validate that the user has the required permission for a room.

        Calls the non-audit 'has_room_permission' check first.

        This check is called at the point that an auditable action
        is being performed.  It calls the non-audit 'has_room_permission'
        check, and then creates the audit record, identifying the required
        permission.  Finally, it returns the result from 'has_room_permission'.
        """

    @abc.abstractmethod
    async def filter_room_ids(
        self,
        room_ids: list[str],
        user_token: UserToken | None,
        *,
        permission: Permission,
    ) -> list[str]:
        """Filter room IDs via authz policies for 'user_token'/'permission'.

        Filter rooms with authorization policies based on those
        policies' ``check_token`` for the user token and permission.

        Include rooms without authorization policies for READ, but exclude
        such rooms for WRITE and ADMIN.
        """

    @abc.abstractmethod
    async def get_room_policy(
        self,
        room_id: str,
    ) -> models.RoomPolicy | None:
        """Return the authorization policy for the room"""

    @abc.abstractmethod
    async def update_room_policy(
        self,
        room_id: str,
        room_policy: models.RoomPolicy,
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
    ) -> models.RoomPolicyUnchecked | None:
        """Return the room policy, tolerating non-compiling 'json_path's."""

    @abc.abstractmethod
    async def list_room_policies(
        self,
    ) -> list[models.RoomPolicyUnchecked]:
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

        The policy and its 'default_allow_deny' setting are preserved.
        """

    @abc.abstractmethod
    async def add_acl_entry(
        self,
        room_id: str,
        entry: models.ACLEntry,
    ) -> None:
        """Add an ACL entry to the room's policy

        The room must already have a policy ('set_room_default' or a prior
        'update_room_policy'); otherwise 'NoSuchRoomPolicy' is raised.

        Replaces existing entries with the same discriminator and permission.
        """

    @abc.abstractmethod
    async def remove_acl_entry(
        self,
        room_id: str,
        entry: models.ACLEntryUnchecked,
    ) -> None:
        """Remove the matching ACL entry from the room's policy.

        'entry' is an unchecked model so a stored 'json_path' that no longer
        compiles can still be matched; the entry is not re-validated.

        Compare against stored entries, matching by 'allow_deny',
        'permission' and discriminator.

        Raises 'NoSuchRoomPolicy' if the room has no policy, or
        'NoSuchACLEntry' if no stored entry matches.
        """

    @abc.abstractmethod
    async def set_room_default(
        self,
        room_id: str,
        allow_deny: AllowDeny,
    ) -> None:
        """Set the room policy's 'default_allow_deny'

        Create an empty policy if none exists.
        """
