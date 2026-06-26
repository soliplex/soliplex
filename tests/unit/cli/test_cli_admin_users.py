from __future__ import annotations

from unittest import mock

import pytest
import sqlalchemy
import typer
import yaml

from soliplex import authz as authz_package
from soliplex.authz import schema as authz_schema
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
    the_installation.authorization_dburi_async = (
        "sqlite+aiosqlite:///fake.sqlite"
    )

    found = cli_admin_users._check_admin_user_args(
        mock.sentinel.installation_path,
        "alice@example.com",
        None,
        None,
        "admin-users add",
    )

    assert found == (
        "sqlite+aiosqlite:///fake.sqlite",
        '$[?$.email == "alice@example.com"]',
    )

    get_installation.assert_called_once_with(mock.sentinel.installation_path)
    _check_ram_dburi.assert_called_once_with(
        "sqlite+aiosqlite:///fake.sqlite",
        "admin-users add",
    )


@mock.patch("soliplex.cli.admin_users.cli_util._check_ram_dburi")
@mock.patch("soliplex.cli.admin_users.cli_util.get_installation")
def test__check_admin_user_args_allow_invalid_json_path(
    get_installation, _check_ram_dburi
):
    the_installation = get_installation.return_value
    the_installation.authorization_dburi_async = (
        "sqlite+aiosqlite:///fake.sqlite"
    )

    bogus = "$[?stale_filter_func($.email)]"

    found = cli_admin_users._check_admin_user_args(
        mock.sentinel.installation_path,
        None,
        None,
        bogus,
        "admin-users delete",
        allow_invalid_json_path=True,
    )

    assert found == ("sqlite+aiosqlite:///fake.sqlite", bogus)


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
    discriminators = ['$[?$.role == "admin"]']

    cli_admin_users._dump(ctx, discriminators)

    if exp_human:
        _human_dump_admin_users.assert_called_once_with(discriminators)
        _dump_admin_users.assert_not_called()
    else:
        _dump_admin_users.assert_called_once_with(discriminators)
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
    json_paths = [
        authz_package.token_field_json_path("email", "alice@example.com"),
        authz_package.token_field_json_path("preferred_username", "bob"),
        "$[?stale_filter_func($.email)]",
    ]

    found = cli_admin_users._admin_users_as_jsonable(json_paths)

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
    json_paths = [
        authz_package.token_field_json_path("email", "alice@example.com"),
    ]

    yaml_text = cli_admin_users._admin_users_as_yaml(json_paths)

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


# ---------------------------------------------------------------------------
# Command-level tests.
#
# These drive the actual 'admin-users' subcommands through a Typer
# 'CliRunner' against a throwaway copy of 'example/minimal.yaml' backed by
# a scratch authorization database (see the 'scratch_installation' and
# 'cli_runner' fixtures in 'tests/unit/cli/conftest.py'). Every active
# command body is now exercised here rather than coverage-excluded; only
# the two '_*_dump_admin_users' UI helpers stay '# pragma NO COVER UI ONLY'.
# ---------------------------------------------------------------------------

ALICE_EMAIL = "alice@example.com"
ALICE_EMAIL_JP = authz_package.token_field_json_path("email", ALICE_EMAIL)
BOB_PU_JP = authz_package.token_field_json_path("preferred_username", "bob")
ROLE_JP = '$[?$.role == "admin"]'
# A stored query that no longer compiles (e.g. it referenced a meta-config
# filter function that has since been removed).
STALE_JP = "$[?stale_filter_func($.email)]"


def _seed_admins(scratch, *json_paths):
    """Insert AdminUser rows straight into the scratch DB."""
    session = scratch.session()
    with session:
        for json_path in json_paths:
            session.add(authz_schema.AdminUser(json_path=json_path))
        session.commit()
    session.bind.dispose()


def _seed_stale_admin(scratch, stale_json_path):
    """Plant an admin whose stored 'json_path' no longer compiles.

    The ORM's 'json_path' validator rejects a non-compiling query on
    insert (and on any attribute-set), so the stale entry is created in
    two steps: seed a normal admin carrying a *valid* placeholder query
    through 'authz_schema.AdminUser', then rewrite its 'json_path' to the
    non-compiling value with a raw UPDATE -- which does not run the
    '@validates' hook. This reproduces the on-disk state left behind when
    a meta-config filter function an entry referenced is removed, so
    'delete --allow-invalid-json-path' can be exercised end-to-end.
    """
    _seed_admins(scratch, ALICE_EMAIL_JP)
    session = scratch.session()
    with session:
        session.execute(
            sqlalchemy.text(
                "UPDATE admin_users SET json_path = :stale "
                "WHERE json_path = :placeholder"
            ),
            {"stale": stale_json_path, "placeholder": ALICE_EMAIL_JP},
        )
        session.commit()
    session.bind.dispose()


def _read_admins(scratch):
    """Read the stored admin 'json_path' values back as a set."""
    session = scratch.session()
    with session:
        result = {
            admin_user.json_path
            for admin_user in session.query(authz_schema.AdminUser)
        }
    session.bind.dispose()
    return result


def _invoke(cli_runner, scratch, subcommand, *rest, **kwargs):
    return cli_runner.invoke(
        cli_admin_users.app,
        [subcommand, str(scratch.path), *rest],
        **kwargs,
    )


# -- list -------------------------------------------------------------------


def test_list_empty(scratch_installation, cli_runner):
    result = _invoke(cli_runner, scratch_installation, "list")

    assert result.exit_code == 0
    assert '"admin_users": []' in result.output


def test_list_populated(scratch_installation, cli_runner):
    _seed_admins(scratch_installation, ALICE_EMAIL_JP, BOB_PU_JP)

    result = _invoke(cli_runner, scratch_installation, "list")

    assert result.exit_code == 0
    # Email-keyed admins surface their email in the JSON dump.
    assert ALICE_EMAIL in result.output


# -- clear ------------------------------------------------------------------


def test_clear_removes_all(scratch_installation, cli_runner):
    _seed_admins(scratch_installation, ALICE_EMAIL_JP, BOB_PU_JP)

    result = _invoke(cli_runner, scratch_installation, "clear")

    assert result.exit_code == 0
    assert _read_admins(scratch_installation) == set()


def test_clear_noop_when_empty(scratch_installation, cli_runner):
    result = _invoke(cli_runner, scratch_installation, "clear")

    assert result.exit_code == 0
    assert _read_admins(scratch_installation) == set()


# -- add --------------------------------------------------------------------


def test_add_email(scratch_installation, cli_runner):
    result = _invoke(cli_runner, scratch_installation, "add", ALICE_EMAIL)

    assert result.exit_code == 0
    assert _read_admins(scratch_installation) == {ALICE_EMAIL_JP}


def test_add_preferred_username(scratch_installation, cli_runner):
    result = _invoke(
        cli_runner,
        scratch_installation,
        "add",
        "--preferred-username",
        "bob",
    )

    assert result.exit_code == 0
    assert _read_admins(scratch_installation) == {BOB_PU_JP}


def test_add_json_path(scratch_installation, cli_runner):
    result = _invoke(
        cli_runner,
        scratch_installation,
        "add",
        "--json-path",
        ROLE_JP,
    )

    assert result.exit_code == 0
    assert _read_admins(scratch_installation) == {ROLE_JP}


def test_add_duplicate_rejected(scratch_installation, cli_runner):
    _seed_admins(scratch_installation, ALICE_EMAIL_JP)

    result = _invoke(cli_runner, scratch_installation, "add", ALICE_EMAIL)

    assert result.exit_code == 1
    # The pre-existing single row is left untouched (no duplicate inserted).
    assert _read_admins(scratch_installation) == {ALICE_EMAIL_JP}


# -- delete -----------------------------------------------------------------


def test_delete_removes_matching(scratch_installation, cli_runner):
    _seed_admins(scratch_installation, ALICE_EMAIL_JP, BOB_PU_JP)

    result = _invoke(cli_runner, scratch_installation, "delete", ALICE_EMAIL)

    assert result.exit_code == 0
    # Only the matched admin is removed; the other is preserved.
    assert _read_admins(scratch_installation) == {BOB_PU_JP}


def test_delete_no_match_errors(scratch_installation, cli_runner):
    _seed_admins(scratch_installation, BOB_PU_JP)

    result = _invoke(cli_runner, scratch_installation, "delete", ALICE_EMAIL)

    assert result.exit_code == 1
    # The non-matching admin is left in place.
    assert _read_admins(scratch_installation) == {BOB_PU_JP}


def test_delete_invalid_json_path_requires_flag(
    scratch_installation,
    cli_runner,
):
    _seed_stale_admin(scratch_installation, STALE_JP)

    # Without '--allow-invalid-json-path' the compile-validation rejects it.
    rejected = _invoke(
        cli_runner,
        scratch_installation,
        "delete",
        "--json-path",
        STALE_JP,
    )
    assert rejected.exit_code == 1
    assert _read_admins(scratch_installation) == {STALE_JP}

    # With the flag the stale entry can still be matched and removed.
    allowed = _invoke(
        cli_runner,
        scratch_installation,
        "delete",
        "--json-path",
        STALE_JP,
        "--allow-invalid-json-path",
    )
    assert allowed.exit_code == 0
    assert _read_admins(scratch_installation) == set()


# -- as-yaml / from-yaml ----------------------------------------------------


def test_as_yaml_empty_to_stdout(scratch_installation, cli_runner):
    result = _invoke(cli_runner, scratch_installation, "as-yaml")

    assert result.exit_code == 0
    assert yaml.safe_load(result.output) == {"admin_users": []}


def test_as_yaml_populated_to_stdout(scratch_installation, cli_runner):
    _seed_admins(scratch_installation, ALICE_EMAIL_JP)

    result = _invoke(cli_runner, scratch_installation, "as-yaml")

    assert result.exit_code == 0
    assert yaml.safe_load(result.output) == {
        "admin_users": [
            {
                "preferred_username": None,
                "email": ALICE_EMAIL,
                "json_path": None,
            },
        ],
    }


def test_as_yaml_to_file(scratch_installation, cli_runner, tmp_path):
    _seed_admins(scratch_installation, BOB_PU_JP)
    out = tmp_path / "admins.yaml"

    result = _invoke(
        cli_runner,
        scratch_installation,
        "as-yaml",
        "-o",
        str(out),
    )

    assert result.exit_code == 0
    assert yaml.safe_load(out.read_text()) == {
        "admin_users": [
            {
                "preferred_username": "bob",
                "email": None,
                "json_path": None,
            },
        ],
    }


def test_from_yaml_file_replaces(scratch_installation, cli_runner, tmp_path):
    # A pre-existing admin is replaced wholesale by the document's entries.
    _seed_admins(scratch_installation, ALICE_EMAIL_JP)
    doc = tmp_path / "admins.yaml"
    doc.write_text(
        yaml.safe_dump(
            {
                "admin_users": [
                    {
                        "preferred_username": "bob",
                        "email": None,
                        "json_path": None,
                    },
                    {
                        "preferred_username": None,
                        "email": None,
                        "json_path": ROLE_JP,
                    },
                ],
            },
        )
    )

    result = _invoke(
        cli_runner,
        scratch_installation,
        "from-yaml",
        "-i",
        str(doc),
    )

    assert result.exit_code == 0
    assert _read_admins(scratch_installation) == {BOB_PU_JP, ROLE_JP}


def test_from_yaml_stdin_populates(scratch_installation, cli_runner):
    doc = yaml.safe_dump(
        {
            "admin_users": [
                {
                    "preferred_username": None,
                    "email": ALICE_EMAIL,
                    "json_path": None,
                },
            ],
        },
    )

    result = _invoke(
        cli_runner,
        scratch_installation,
        "from-yaml",
        input=doc,
    )

    assert result.exit_code == 0
    assert _read_admins(scratch_installation) == {ALICE_EMAIL_JP}


def test_from_yaml_null_clears(scratch_installation, cli_runner):
    _seed_admins(scratch_installation, ALICE_EMAIL_JP, BOB_PU_JP)

    # A 'null' document read from stdin removes every admin entry.
    result = _invoke(
        cli_runner,
        scratch_installation,
        "from-yaml",
        input="null\n",
    )

    assert result.exit_code == 0
    assert _read_admins(scratch_installation) == set()


def test_as_yaml_clear_from_yaml_round_trip(
    scratch_installation,
    cli_runner,
    tmp_path,
):
    # Build a mixed set of admins through the CLI: an email, a
    # preferred_username, and a general-purpose JSONPath.
    for add_args in (
        ("add", ALICE_EMAIL),
        ("add", "--preferred-username", "bob"),
        ("add", "--json-path", ROLE_JP),
    ):
        assert (
            _invoke(cli_runner, scratch_installation, *add_args).exit_code == 0
        )

    expected = {ALICE_EMAIL_JP, BOB_PU_JP, ROLE_JP}
    assert _read_admins(scratch_installation) == expected

    # Dump them to a file ...
    dump = tmp_path / "admins.yaml"
    assert (
        _invoke(
            cli_runner,
            scratch_installation,
            "as-yaml",
            "-o",
            str(dump),
        ).exit_code
        == 0
    )

    # ... wipe the database ...
    assert _invoke(cli_runner, scratch_installation, "clear").exit_code == 0
    assert _read_admins(scratch_installation) == set()

    # ... and restore from the dump. Every admin comes back intact.
    assert (
        _invoke(
            cli_runner,
            scratch_installation,
            "from-yaml",
            "-i",
            str(dump),
        ).exit_code
        == 0
    )
    assert _read_admins(scratch_installation) == expected
