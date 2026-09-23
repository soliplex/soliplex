from __future__ import annotations

from unittest import mock

import pytest

from soliplex.cli import cli_util
from soliplex.cli.audit import admin_users as audit_admin_users
from tests.unit.cli.audit import audit_helpers


@pytest.mark.anyio
@mock.patch("soliplex.cli.audit.admin_users.cli_util._admin_user_policy")
async def test__list_admin_discriminators(authz_policy):
    # The helper is a pass-through; 'list_admin_user_discriminators'
    # yields the stored 'AdminUser.json_path' query strings.
    discriminators = [
        '$[?$.email == "alice@example.com"]',
        '$[?$.role == "admin"]',
    ]
    policy = mock.AsyncMock()
    policy.list_admin_user_discriminators.return_value = discriminators
    authz_policy.return_value.__aenter__.return_value = policy

    found = await audit_admin_users._list_admin_discriminators(
        mock.sentinel.installation
    )

    assert found == discriminators
    authz_policy.assert_called_once_with(
        mock.sentinel.installation,
        "audit admin-users",
        allow_ram=True,
        must_exist=True,
    )
    policy.list_admin_user_discriminators.assert_awaited_once_with()


def test__admin_user_json_paths_on_an_uncreated_database(
    the_installation, tmp_path
):
    the_installation, db_path = audit_helpers.uncreated_installation(
        the_installation, tmp_path
    )

    found_paths, found_error = audit_admin_users._admin_user_json_paths(
        the_installation
    )

    assert found_paths == []
    assert found_error is None
    assert audit_helpers.tables(db_path) == set()


@pytest.mark.parametrize(
    "json_paths, exc, exp_json_paths, exp_error",
    [
        # A database nothing has created -- an in-memory one included --
        # holds no admin rows, and that is not a finding.
        (None, cli_util.DatabaseNotCreated("authz"), [], None),
        # Created, with no stored admins.
        ([], None, [], None),
        # Stored rows pass through in the order they are read.
        (
            [
                '$[?$.email == "alice@example.com"]',
                "$[?some_func($.email)]",
            ],
            None,
            [
                '$[?$.email == "alice@example.com"]',
                "$[?some_func($.email)]",
            ],
            None,
        ),
        # A database the driver cannot reach: reported, not raised.
        (
            None,
            audit_helpers.AuthzDBError(),
            [],
            audit_helpers.EXP_AUTHZ_DB_ERROR,
        ),
    ],
)
@mock.patch("soliplex.cli.audit.admin_users._list_admin_discriminators")
def test__admin_user_json_paths(
    list_admin_discriminators,
    the_installation,
    json_paths,
    exc,
    exp_json_paths,
    exp_error,
):
    if exc is not None:
        list_admin_discriminators.side_effect = exc
    else:
        list_admin_discriminators.return_value = json_paths

    found_json_paths, found_error = audit_admin_users._admin_user_json_paths(
        the_installation
    )

    assert found_json_paths == exp_json_paths
    assert found_error == exp_error
    list_admin_discriminators.assert_called_once_with(the_installation)


@pytest.mark.parametrize(
    "json_paths, exp_invalid",
    [
        # No admins.
        ([], []),
        # All valid.
        (
            [
                '$[?$.email == "alice@example.com"]',
                '$[?$.preferred_username == "bob"]',
            ],
            [],
        ),
        # Mixed: one invalid.
        (
            [
                '$[?$.email == "alice@example.com"]',
                "$[?missing_func($.email)]",
            ],
            [("$[?missing_func($.email)]", "<error>")],
        ),
        # All invalid.
        (
            ["$[?one_missing()]", "$[?another_missing()]"],
            [
                ("$[?one_missing()]", "<error>"),
                ("$[?another_missing()]", "<error>"),
            ],
        ),
    ],
)
def test__invalid_admin_user_json_paths(json_paths, exp_invalid):
    found = audit_admin_users._invalid_admin_user_json_paths(json_paths)

    normalized = [(jp, "<error>") for (jp, _err) in found]
    assert normalized == exp_invalid


# _audit_admin_users_section: ui only
# audit_admin_users: command
