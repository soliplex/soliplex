from __future__ import annotations

from unittest import mock

import pytest
import typer

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
    "w_email, w_pref, w_jp, exp",
    [
        (
            "alice@example.com",
            None,
            None,
            authz_package.token_field_json_path("email", "alice@example.com"),
        ),
        (
            None,
            "bob",
            None,
            authz_package.token_field_json_path("preferred_username", "bob"),
        ),
        (None, None, '$[?$.role == "admin"]', '$[?$.role == "admin"]'),
    ],
)
@mock.patch("soliplex.cli.admin_users.the_console")
def test__resolve_admin_json_path(the_console, w_email, w_pref, w_jp, exp):
    found = cli_admin_users._resolve_admin_json_path(w_email, w_pref, w_jp)

    assert found == exp
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
@mock.patch("soliplex.cli.admin_users.the_console")
def test__resolve_admin_json_path_not_exactly_one(
    the_console, w_email, w_pref, w_jp
):
    with pytest.raises(typer.Exit) as excinfo:
        cli_admin_users._resolve_admin_json_path(w_email, w_pref, w_jp)

    (return_code,) = excinfo.value.args
    assert return_code == 1
    the_console.rule.assert_called_once_with(
        "Exactly one discriminator required",
    )


@mock.patch("soliplex.cli.admin_users.the_console")
def test__resolve_admin_json_path_invalid(the_console):
    with pytest.raises(typer.Exit) as excinfo:
        cli_admin_users._resolve_admin_json_path(None, None, "$[?(bogus")

    (return_code,) = excinfo.value.args
    assert return_code == 1
    the_console.rule.assert_called_once_with("Invalid JSONPath")


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
