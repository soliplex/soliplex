import pytest

from soliplex import authz


def test_reservedjsonpathfunctionname_is_valueerror():
    assert issubclass(authz.ReservedJSONPathFunctionName, ValueError)


def test_register_jsonpath_function(patched_jsonpath_functions):
    def is_admin(value):
        return value

    authz.register_jsonpath_function("is_admin", is_admin)

    env = authz.the_jsonpath_environment
    registered = env.function_extensions["is_admin"]
    assert registered is is_admin
    assert registered("ok") == "ok"
    assert authz.registered_jsonpath_functions() == {"is_admin": is_admin}


def test_register_jsonpath_function_rejects_builtin(
    patched_jsonpath_functions,
):
    builtin = next(iter(authz.BUILTIN_JSONPATH_FUNCTION_NAMES))

    with pytest.raises(authz.ReservedJSONPathFunctionName) as exc_info:
        authz.register_jsonpath_function(builtin, lambda v: v)

    assert exc_info.value.name == builtin


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
        "",
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
