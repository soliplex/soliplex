import inspect
from unittest import mock

import pytest

from soliplex import authz
from soliplex.authz import schema as authz_schema

USER_NAME = "phreddy"
GIVEN_NAME = "Phred"
FAMILY_NAME = "Phlyntstone"
EMAIL = "phreddy@example.com"

THE_USER_CLAIMS = {
    "preferred_username": USER_NAME,
    "given_name": GIVEN_NAME,
    "family_name": FAMILY_NAME,
    "email": EMAIL,
}


def test_reservedjsonpathfunctionname_is_valueerror():
    assert issubclass(authz.ReservedJSONPathFunctionName, ValueError)


def test_invalidpredicateresult_is_valueerror():
    assert issubclass(authz.InvalidPredicateResult, ValueError)


def test_register_jsonpath_function(patched_jsonpath_functions):
    def is_admin(value):
        return value

    authz.register_jsonpath_function("is_admin", is_admin)

    registered = authz.the_jsonpath_environment.function_extensions["is_admin"]

    assert inspect.unwrap(registered) is is_admin
    assert registered.__name__ == is_admin.__name__
    assert registered.__module__ == is_admin.__module__
    assert registered("ok") == "ok"
    (from_registry,) = authz.registered_jsonpath_functions().values()
    assert inspect.unwrap(from_registry) is is_admin


def test_register_jsonpath_function_rejects_builtin(
    patched_jsonpath_functions,
):
    builtin = next(iter(authz.BUILTIN_JSONPATH_FUNCTION_NAMES))

    with pytest.raises(authz.ReservedJSONPathFunctionName) as exc_info:
        authz.register_jsonpath_function(builtin, lambda v: v)

    assert exc_info.value.name == builtin


def test_register_jsonpath_function_raises_on_none_result(
    patched_jsonpath_functions,
):
    authz.register_jsonpath_function("fo_none", lambda claims: None)

    env = authz.the_jsonpath_environment

    with pytest.raises(authz.InvalidPredicateResult) as exc_info:
        env.match("$[?fo_none($)]", PREDICATE_TOKEN)

    assert exc_info.value.name == "fo_none"


def test_register_jsonpath_function_replaces_prior_wrapper(
    patched_jsonpath_functions,
):
    def fo_bool(claims):
        return True

    authz.register_jsonpath_function("fo_bool", fo_bool)
    prior = authz.the_jsonpath_environment.function_extensions["fo_bool"]

    authz.register_jsonpath_function("fo_bool", prior)

    registered = authz.the_jsonpath_environment.function_extensions["fo_bool"]

    assert registered is not prior
    assert inspect.unwrap(registered) is fo_bool
    assert registered(PREDICATE_TOKEN) is True


def test_registered_jsonpath_functions_excludes_builtins(
    patched_jsonpath_functions,
):
    assert authz.registered_jsonpath_functions() == {}


def test_invalidjsonpath_is_valueerror():
    assert issubclass(authz.InvalidJSONPath, ValueError)


def test_validate_json_path_passes_none():
    assert authz.validate_json_path(None) is None


@pytest.mark.parametrize(
    "value",
    [
        "$",
        "$.foo",
        "$[?match($.foo, 'b.*z')]",
    ],
)
def test_validate_json_path_accepts_valid(value):
    assert authz.validate_json_path(value) == value


@pytest.mark.parametrize(
    "value",
    [
        "not a path",
        "$[?",
    ],
)
def test_validate_json_path_rejects_invalid(value):
    with pytest.raises(authz.InvalidJSONPath) as exc_info:
        authz.validate_json_path(value)

    assert exc_info.value.value == value
    assert exc_info.value.__cause__ is not None


@pytest.mark.parametrize(
    "value",
    [
        "",
        "   ",
        "\t",
    ],
)
def test_validate_json_path_rejects_blank(value):
    with pytest.raises(authz.InvalidJSONPath) as exc_info:
        authz.validate_json_path(value)

    assert exc_info.value.value == value


@pytest.mark.parametrize(
    "field, value, match_token, miss_token",
    [
        (
            "preferred_username",
            "alice",
            {"preferred_username": "alice"},
            {"preferred_username": "bob"},
        ),
        (
            "email",
            "alice@example.com",
            {"email": "alice@example.com"},
            {},
        ),
        (
            "preferred_username",
            'has"quote',
            {"preferred_username": 'has"quote'},
            {"preferred_username": "plain"},
        ),
    ],
)
def test_token_field_json_path(field, value, match_token, miss_token):
    expr = authz.token_field_json_path(field, value)

    assert authz.validate_json_path(expr) == expr

    env = authz.the_jsonpath_environment
    assert env.match(expr, match_token) is not None
    assert env.match(expr, miss_token) is None


@pytest.mark.parametrize(
    "field, value",
    [
        ("preferred_username", "alice"),
        ("email", "alice@example.com"),
        ("preferred_username", 'has"quote'),
        ("email", "a]b@example.com"),
    ],
)
def test_parse_token_field_json_path_roundtrip(field, value):
    expr = authz.token_field_json_path(field, value)

    assert authz.parse_token_field_json_path(expr) == (field, value)


@pytest.mark.parametrize(
    "value",
    [
        "$",
        "$.foo",
        "$[?match($.foo, 'b.*z')]",
        # Matches the shape, but the operand is not a JSON string:
        "$[?$.age == 42]",  # decodes to a non-str
        "$[?$.foo == bar]",  # not valid JSON at all
    ],
)
def test_parse_token_field_json_path_non_field_query(value):
    assert authz.parse_token_field_json_path(value) is None


@pytest.mark.parametrize(
    "json_path, exp_claim_names",
    [
        # Canonical single-claim discriminators.
        ('$[?$.email == "alice@example.com"]', ["email"]),
        ('$[?$.preferred_username == "bob"]', ["preferred_username"]),
        # Quoted values contribute no claim names, however evil-shaped.
        ('$[?$.email == "x@$.evil.com"]', ["email"]),
        # Filter functions' arguments are claims like any other.
        ("$[?some_func($.email)]", ["email"]),
        # Dotted references contribute only their root claim.
        ("$.realm_access.roles[0]", ["realm_access"]),
        # Bracketed references, root segment only.
        ("$['email']", ["email"]),
        # No claim references at all.
        ("$", []),
        # Nested '@'-relative queries take the enclosing chain's root.
        ('$[?$.groups[?@ == "x"]]', ["groups"]),
        ('$[?@.org.code == "XYZ"]', ["org"]),
        (
            '$[?$.org.personnel.specialties[?@ == "A1B2C3"]]',
            ["org"],
        ),
        # Unions, recursive descent:  every chain contributes its root.
        ('$["a", "b"]', ["a", "b"]),
        ("$..roles", ["roles"]),
        # A singular-query selector reads its embedded query's claims.
        ("$[$.key]", ["key"]),
        # Unparseable queries contribute nothing:  rows like these are
        # reported separately, in the invalid JSONPath block.
        ("$[", []),
        ("$[?missing_func($.email)]", []),
    ],
)
@mock.patch.dict(
    authz.the_jsonpath_environment.function_extensions,
    {"some_func": lambda *args: None},
)
def test_discriminator_claim_names(json_path, exp_claim_names):
    found = authz.discriminator_claim_names(json_path)

    assert found == exp_claim_names


@pytest.mark.parametrize(
    "claim_names, exp_tokens",
    [
        ([], [{}]),
        (["a"], [{"a": None}, {}]),
        (["a", "b"], [{"a": None, "b": None}, {}]),
    ],
)
def test_null_probe_tokens(claim_names, exp_tokens):
    found = authz.null_probe_tokens(claim_names)

    assert found == exp_tokens


@pytest.mark.parametrize(
    "json_path, exp_matched",
    [
        # A bare selector presence query matches its claim at 'null'.
        ("$.email", {"email": None}),
        # A '$'-root query matches even an empty token.
        ("$", {}),
        # Inequality comparisons treat 'null' as an ordinary value.
        ('$[?$.role != "x"]', {"role": None}),
    ],
)
def test_null_claims_match_flags_surprise_matches(json_path, exp_matched):
    found = authz.null_claims_match(json_path)

    assert found == exp_matched


@pytest.mark.parametrize(
    "json_path, registered",
    [
        # Canonical equality rules are clean.
        ('$[?$.email == "alice"]', {}),
        # Predicate-only queries:  an empty token visits no children,
        # so the predicate is not even consulted.
        ("$[?pred($)]", {"pred": lambda claims: True}),
        # Invalid and blank queries are reported in the invalid block.
        ("$[", {}),
        ("", {}),
    ],
)
def test_null_claims_match_contributes_no_flag(json_path, registered):
    with mock.patch.dict(
        authz.the_jsonpath_environment.function_extensions,
        registered,
    ):
        found = authz.null_claims_match(json_path)

    assert found is None


@mock.patch.dict(
    authz.the_jsonpath_environment.function_extensions,
    {"boom": lambda claims: 1 // 0},
)
def test_null_claims_match_ignores_raising_predicate():
    # Function extensions are deployment software, not config:  their
    # failures against synthetic claims are swallowed, not audit errors.
    found = authz.null_claims_match("$[?boom($.email)]")

    assert found is None


# ----------------------------------------------------------------------------
#   Predicate-driven authorization (afsoc-rag#2083)
# ----------------------------------------------------------------------------

PREDICATE_TOKEN = {"email": "someone@example.org", "sub": "abc"}


def _register_predicate(name, result):
    """Register a predicate which always resolves to 'result'."""
    authz.register_jsonpath_function(name, lambda claims: result)


def _allow_read_policy(name):
    """DENY-default policy with one ALLOW entry driven by 'name'."""
    return authz_schema.RoomPolicy(
        room_id="soliplex-jsonpath",
        default_allow_deny=authz.AllowDeny.DENY,
        acl_entries=[
            authz_schema.ACLEntry(
                allow_deny=authz.AllowDeny.ALLOW,
                permission=authz.Permission.READ,
                json_path=f"$[?{name}($)]",
            ),
        ],
    )


def test_none_predicate_result_raises_on_room_check(
    patched_jsonpath_functions,
):
    _register_predicate("fo_none", None)

    policy = _allow_read_policy("fo_none")

    with pytest.raises(authz.InvalidPredicateResult) as exc_info:
        policy.check_token(PREDICATE_TOKEN, permission=authz.Permission.READ)

    assert exc_info.value.name == "fo_none"


@pytest.mark.parametrize("non_matching", [False, ()])
def test_non_matching_predicate_result_denies_read(
    patched_jsonpath_functions, non_matching
):
    _register_predicate("fo_miss", non_matching)

    policy = _allow_read_policy("fo_miss")

    found = policy.check_token(
        PREDICATE_TOKEN, permission=authz.Permission.READ
    )

    assert found is authz.AllowDeny.DENY


def test_truthy_non_bool_predicate_result_allows_read(
    patched_jsonpath_functions,
):
    # A claims-dict return on match (the ragserver.afsc shape) keeps
    # matching:  the wrapper gates only 'None'; the engine's own
    # truthiness rules decide everything else.
    _register_predicate("fo_claims", {"claims": "matched"})

    policy = _allow_read_policy("fo_claims")

    found = policy.check_token(
        PREDICATE_TOKEN, permission=authz.Permission.READ
    )

    assert found is authz.AllowDeny.ALLOW


def test_empty_token_does_not_match_predicate(patched_jsonpath_functions):
    _register_predicate("fo_bool", True)

    policy = _allow_read_policy("fo_bool")

    found = policy.check_token({}, permission=authz.Permission.READ)

    assert found is authz.AllowDeny.DENY


def test_none_predicate_result_raises_on_admin_check(
    patched_jsonpath_functions,
):
    _register_predicate("fo_admin_none", None)

    admin = authz_schema.AdminUser(json_path="$[?fo_admin_none($)]")

    with pytest.raises(authz.InvalidPredicateResult) as exc_info:
        admin.check_token(PREDICATE_TOKEN)

    assert exc_info.value.name == "fo_admin_none"


def test_false_predicate_result_is_not_an_admin(patched_jsonpath_functions):
    _register_predicate("fo_admin_false", False)

    admin = authz_schema.AdminUser(json_path="$[?fo_admin_false($)]")

    found = admin.check_token(PREDICATE_TOKEN)

    assert found is False
