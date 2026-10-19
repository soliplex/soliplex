from __future__ import annotations

from unittest import mock

import pytest

from soliplex.cli import cli_util
from soliplex.cli.audit import admin_users as audit_admin_users
from soliplex.config import authsystem as config_authsystem
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


_A_ID = "alpha"
_B_ID = "beta"


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
    ],
)
def test__discriminator_claim_names(json_path, exp_claim_names):

    found = audit_admin_users._discriminator_claim_names(json_path)

    assert found == exp_claim_names


@pytest.mark.parametrize(
    "json_paths, auth_system_kws, exp_not_carried",
    [
        # No stored admins: nothing referenced, nothing uncovered.
        ([], [(_A_ID, ("email",))], []),
        # Referenced claims carried by the (only) auth system.
        (
            ['$[?$.email == "alice@example.com"]'],
            [(_A_ID, ("email", "preferred_username"))],
            [],
        ),
        # 'sub' is always carried, whatever 'cookie_claims' says.
        (['$[?$.sub == "user-sub"]'], [(_A_ID, ())], []),
        # Uncovered claims: one pair for each auth system missing them.
        (
            ["$.realm_access.roles[0]"],
            [(_A_ID, ()), (_B_ID, ("realm_access",))],
            [(_A_ID, "realm_access")],
        ),
        # Multiple paths accumulate; output sorted by claim name.
        (
            [
                '$[?$.email == "alice@example.com"]',
                '$[?$.preferred_username == "bob"]',
            ],
            [(_A_ID, ())],
            [(_A_ID, "email"), (_A_ID, "preferred_username")],
        ),
        # No auth systems configured: no cookies exist to check.
        (['$[?$.email == "alice@example.com"]'], [], []),
    ],
)
def test__claims_not_carried(
    json_paths,
    auth_system_kws,
    exp_not_carried,
):
    configs = []
    for the_id, cookie_claims in auth_system_kws:
        config = mock.create_autospec(
            config_authsystem.OIDCAuthSystemConfig,
            id=the_id,
        )
        config.cookie_claims = list(cookie_claims)
        configs.append(config)

    found = audit_admin_users._claims_not_carried(json_paths, configs)

    assert found == exp_not_carried


# _audit_admin_users_section: ui only
# audit_admin_users: command
