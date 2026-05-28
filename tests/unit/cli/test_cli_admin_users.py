from __future__ import annotations

from unittest import mock

import pytest
import typer
import yaml

from soliplex import authz as authz_package
from soliplex.cli import admin_users as cli_admin_users


@pytest.fixture
def ctx():
    return mock.create_autospec(typer.Context, obj={})


@pytest.mark.parametrize(
    "w_verbose, w_quiet, w_default_verbose, exp_effective",
    [
        # Neither flag: falls back to the module default.
        (False, False, False, False),
        (False, False, True, True),
        # --verbose alone forces human.
        (True, False, False, True),
        (True, False, True, True),
        # --quiet alone forces JSON, regardless of the default.
        (False, True, False, False),
        (False, True, True, False),
        # --quiet wins when both flags are passed.
        (True, True, False, False),
        (True, True, True, False),
    ],
)
def test__admin_users_callback(
    ctx,
    w_verbose,
    w_quiet,
    w_default_verbose,
    exp_effective,
):
    with mock.patch.object(
        cli_admin_users,
        "_DEFAULT_VERBOSE",
        w_default_verbose,
    ):
        cli_admin_users._admin_users_callback(
            ctx,
            verbose=w_verbose,
            quiet=w_quiet,
        )

    assert ctx.obj == {"verbose": exp_effective}


@pytest.mark.parametrize(
    "w_exists",
    [
        # No existing admin: the insert may proceed.
        False,
        # Existing admin: reject to avoid a uniqueness-constraint blowup.
        True,
    ],
)
@mock.patch("soliplex.cli.admin_users.the_console")
def test__check_existing_admin(the_console, w_exists):
    json_path = authz_package.token_field_json_path(
        "email", "alice@example.com"
    )
    existing = mock.Mock() if w_exists else None

    session = mock.Mock()
    session.query.return_value.where.return_value.first.return_value = existing

    if not w_exists:
        cli_admin_users._check_existing_admin(session, json_path)

        the_console.rule.assert_not_called()
        the_console.print.assert_not_called()
        return

    with pytest.raises(typer.Exit) as excinfo:
        cli_admin_users._check_existing_admin(session, json_path)

    (return_code,) = excinfo.value.args
    assert return_code == 1

    the_console.rule.assert_called_once_with(
        "email=alice@example.com is already an admin",
    )
    the_console.print.assert_called_once_with("Nothing to do.")


@pytest.mark.parametrize(
    "w_email, w_pref, w_jp",
    [
        # Exactly one set: each branch in turn.
        ("alice@example.com", None, None),
        (None, "bob", None),
        (None, None, '$[?$.role == "admin"]'),
    ],
)
@mock.patch("soliplex.cli.admin_users.the_console")
def test__check_admin_discriminator_accepts_one(
    the_console, w_email, w_pref, w_jp
):
    cli_admin_users._check_admin_discriminator(w_email, w_pref, w_jp)

    the_console.rule.assert_not_called()


@pytest.mark.parametrize(
    "w_email, w_pref, w_jp",
    [
        # Nothing selected.
        (None, None, None),
        # More than one selected.
        ("alice@example.com", None, '$[?$.role == "admin"]'),
        ("alice@example.com", "bob", None),
        ("alice@example.com", "bob", '$[?$.role == "admin"]'),
    ],
)
@mock.patch("soliplex.cli.cli_util.the_console")
def test__check_admin_discriminator_rejects_other_arities(
    the_console, w_email, w_pref, w_jp
):
    with pytest.raises(typer.Exit) as excinfo:
        cli_admin_users._check_admin_discriminator(w_email, w_pref, w_jp)

    (return_code,) = excinfo.value.args
    assert return_code == 1
    the_console.rule.assert_called_once_with(
        "Exactly one discriminator required",
    )


@mock.patch("soliplex.cli.admin_users.cli_util._check_ram_dburi")
@mock.patch("soliplex.cli.admin_users.cli_util.get_installation")
def test__check_admin_user_args(get_installation, _check_ram_dburi):
    the_installation = get_installation.return_value
    the_installation.authorization_dburi_sync = "sqlite:///fake.sqlite"

    found = cli_admin_users._check_admin_user_args(
        mock.sentinel.installation_path,
        "alice@example.com",
        None,
        None,
        "admin-users add",
    )

    assert found == (
        "sqlite:///fake.sqlite",
        '$[?$.email == "alice@example.com"]',
    )

    get_installation.assert_called_once_with(mock.sentinel.installation_path)
    _check_ram_dburi.assert_called_once_with(
        "sqlite:///fake.sqlite",
        "admin-users add",
    )


@mock.patch("soliplex.cli.admin_users.cli_util._check_ram_dburi")
@mock.patch("soliplex.cli.admin_users.cli_util.get_installation")
def test__check_admin_user_args_allow_invalid_json_path(
    get_installation, _check_ram_dburi
):
    the_installation = get_installation.return_value
    the_installation.authorization_dburi_sync = "sqlite:///fake.sqlite"

    bogus = "$[?stale_filter_func($.email)]"

    found = cli_admin_users._check_admin_user_args(
        mock.sentinel.installation_path,
        None,
        None,
        bogus,
        "admin-users delete",
        allow_invalid_json_path=True,
    )

    assert found == ("sqlite:///fake.sqlite", bogus)


@pytest.mark.parametrize(
    "w_json_path, exp_describe, exp_display",
    [
        # Email-shaped query: email descriptor, email display.
        (
            authz_package.token_field_json_path("email", "alice@example.com"),
            "email=alice@example.com",
            "alice@example.com",
        ),
        # preferred_username-shaped: field descriptor, raw query display.
        (
            authz_package.token_field_json_path("preferred_username", "bob"),
            "preferred_username=bob",
            authz_package.token_field_json_path("preferred_username", "bob"),
        ),
        # Other token-field query: field descriptor, raw query display.
        (
            '$[?$.role == "admin"]',
            "role=admin",
            '$[?$.role == "admin"]',
        ),
        # Non-token-field query: raw query for both.
        ("$.weird[*]", "json_path=$.weird[*]", "$.weird[*]"),
    ],
)
def test__describe_and_display_admin(w_json_path, exp_describe, exp_display):
    assert cli_admin_users._describe_admin(w_json_path) == exp_describe
    assert cli_admin_users._admin_display(w_json_path) == exp_display


@pytest.mark.parametrize(
    "w_obj, exp_human",
    [
        # No ctx.obj at all -> JSON dispatch.
        (None, False),
        # Empty ctx.obj -> JSON dispatch.
        ({}, False),
        # ctx.obj['verbose'] falsy -> JSON dispatch.
        ({"verbose": False}, False),
        # ctx.obj['verbose'] truthy -> human dispatch.
        ({"verbose": True}, True),
    ],
)
@mock.patch("soliplex.cli.admin_users._human_dump_admin_users")
@mock.patch("soliplex.cli.admin_users._dump_admin_users")
def test__dump(
    _dump_admin_users,
    _human_dump_admin_users,
    ctx,
    w_obj,
    exp_human,
):
    ctx.obj = w_obj
    session = mock.Mock()

    cli_admin_users._dump(ctx, session)

    if exp_human:
        _human_dump_admin_users.assert_called_once_with(session)
        _dump_admin_users.assert_not_called()
    else:
        _dump_admin_users.assert_called_once_with(session)
        _human_dump_admin_users.assert_not_called()


@pytest.mark.parametrize(
    "w_json_path, exp",
    [
        # Stored email-shortcut: surfaced back as 'email'.
        (
            authz_package.token_field_json_path("email", "alice@example.com"),
            {
                "preferred_username": None,
                "email": "alice@example.com",
                "json_path": None,
            },
        ),
        # Stored preferred_username-shortcut.
        (
            authz_package.token_field_json_path("preferred_username", "bob"),
            {
                "preferred_username": "bob",
                "email": None,
                "json_path": None,
            },
        ),
        # General-purpose JSONPath: surface as 'json_path' verbatim.
        (
            '$[?$.role == "admin"]',
            {
                "preferred_username": None,
                "email": None,
                "json_path": '$[?$.role == "admin"]',
            },
        ),
        # Canonical-form-but-for-some-other-field: surface as 'json_path'.
        (
            '$[?$.sub == "abc"]',
            {
                "preferred_username": None,
                "email": None,
                "json_path": '$[?$.sub == "abc"]',
            },
        ),
        # Invalid stored 'json_path': dumped verbatim, no validation.
        (
            "$[?stale_filter_func($.email)]",
            {
                "preferred_username": None,
                "email": None,
                "json_path": "$[?stale_filter_func($.email)]",
            },
        ),
    ],
)
def test__admin_user_as_jsonable(w_json_path, exp):
    assert cli_admin_users._admin_user_as_jsonable(w_json_path) == exp


def test__admin_users_as_jsonable_empty():
    assert cli_admin_users._admin_users_as_jsonable([]) == {"admin_users": []}


def test__admin_users_as_jsonable_populated():
    rows = [
        mock.Mock(
            json_path=authz_package.token_field_json_path(
                "email", "alice@example.com"
            )
        ),
        mock.Mock(
            json_path=authz_package.token_field_json_path(
                "preferred_username", "bob"
            )
        ),
        mock.Mock(json_path="$[?stale_filter_func($.email)]"),
    ]

    found = cli_admin_users._admin_users_as_jsonable(rows)

    assert found == {
        "admin_users": [
            {
                "preferred_username": None,
                "email": "alice@example.com",
                "json_path": None,
            },
            {
                "preferred_username": "bob",
                "email": None,
                "json_path": None,
            },
            {
                "preferred_username": None,
                "email": None,
                "json_path": "$[?stale_filter_func($.email)]",
            },
        ],
    }


def test__admin_users_as_yaml_round_trips():
    rows = [
        mock.Mock(
            json_path=authz_package.token_field_json_path(
                "email", "alice@example.com"
            )
        ),
    ]

    yaml_text = cli_admin_users._admin_users_as_yaml(rows)

    assert yaml.safe_load(yaml_text) == {
        "admin_users": [
            {
                "preferred_username": None,
                "email": "alice@example.com",
                "json_path": None,
            },
        ],
    }


@pytest.mark.parametrize(
    "w_entry, exp",
    [
        # 'email' shortcut -> canonical query.
        (
            {
                "preferred_username": None,
                "email": "alice@example.com",
                "json_path": None,
            },
            authz_package.token_field_json_path("email", "alice@example.com"),
        ),
        # 'preferred_username' shortcut -> canonical query.
        (
            {
                "preferred_username": "bob",
                "email": None,
                "json_path": None,
            },
            authz_package.token_field_json_path("preferred_username", "bob"),
        ),
        # Literal 'json_path' passes through unchanged.
        (
            {
                "preferred_username": None,
                "email": None,
                "json_path": '$[?$.role == "admin"]',
            },
            '$[?$.role == "admin"]',
        ),
    ],
)
def test__admin_user_from_jsonable(w_entry, exp):
    assert cli_admin_users._admin_user_from_jsonable(w_entry) == exp


@pytest.mark.parametrize(
    "w_entry",
    [
        # Nothing specified.
        {
            "preferred_username": None,
            "email": None,
            "json_path": None,
        },
        # Multiple specified.
        {
            "preferred_username": "bob",
            "email": "alice@example.com",
            "json_path": None,
        },
    ],
)
@mock.patch("soliplex.cli.cli_util.the_console")
def test__admin_user_from_jsonable_rejects_invalid(the_console, w_entry):
    with pytest.raises(typer.Exit) as excinfo:
        cli_admin_users._admin_user_from_jsonable(w_entry)

    (return_code,) = excinfo.value.args
    assert return_code == 1
    the_console.rule.assert_called_once_with(
        "Exactly one discriminator required",
    )


@pytest.mark.parametrize(
    "w_data, exp",
    [
        # 'null' document -> empty list.
        (None, []),
        # Missing key -> empty list.
        ({}, []),
        # Empty list.
        ({"admin_users": []}, []),
        # Populated list.
        (
            {
                "admin_users": [
                    {
                        "preferred_username": None,
                        "email": "alice@example.com",
                        "json_path": None,
                    },
                    {
                        "preferred_username": "bob",
                        "email": None,
                        "json_path": None,
                    },
                ],
            },
            [
                authz_package.token_field_json_path(
                    "email", "alice@example.com"
                ),
                authz_package.token_field_json_path(
                    "preferred_username", "bob"
                ),
            ],
        ),
    ],
)
def test__admin_users_from_jsonable(w_data, exp):
    assert cli_admin_users._admin_users_from_jsonable(w_data) == exp
