from unittest import mock

import fastapi
import pytest

from soliplex import authz as authz_package


def test_invalidjsonpath_is_valueerror():
    assert issubclass(authz_package.InvalidJSONPath, ValueError)


def test_validate_json_path_passes_none():
    assert authz_package.validate_json_path(None) is None


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
    assert authz_package.validate_json_path(value) == value


@pytest.mark.parametrize(
    "value",
    [
        "not a path",
        "$[?",
    ],
)
def test_validate_json_path_rejects_invalid(value):
    with pytest.raises(authz_package.InvalidJSONPath) as exc_info:
        authz_package.validate_json_path(value)

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
    expr = authz_package.token_field_json_path(field, value)

    assert authz_package.validate_json_path(expr) == expr

    env = authz_package.the_jsonpath_environment
    assert env.match(expr, match_token) is not None
    assert env.match(expr, miss_token) is None


@pytest.mark.anyio
@mock.patch("soliplex.authz.persistence.AuthorizationPolicy")
@mock.patch("sqlalchemy.ext.asyncio.AsyncSession")
async def test_get_the_authz_policy(as_klass, ap_klass):
    engine = object()
    request = fastapi.Request(scope={"type": "http"})
    request.state.authorization_engine = engine

    counter = 0

    async for the_authz_policy in authz_package.get_the_authz_policy(request):
        assert the_authz_policy is ap_klass.return_value
        counter += 1

    assert counter == 1

    ap_klass.assert_called_once_with(
        as_klass.return_value.__aenter__.return_value,
    )

    as_klass.assert_called_once_with(bind=engine)
