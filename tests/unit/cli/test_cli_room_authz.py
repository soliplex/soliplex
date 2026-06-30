from __future__ import annotations

from unittest import mock

import pytest
import sqlalchemy
import typer
import yaml

from soliplex import authz
from soliplex import installation
from soliplex import models
from soliplex.authz import schema as authz_schema
from soliplex.cli import room_authz as cli_room_authz
from soliplex.config import installation as config_installation


@pytest.fixture
def ctx():
    return mock.create_autospec(typer.Context, obj={})


@pytest.fixture
def the_installation() -> installation.Installation:
    i_config = mock.create_autospec(config_installation.InstallationConfig)
    return installation.Installation(_config=i_config)


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
@mock.patch("soliplex.cli.cli_util._configure_cli_logging")
def test__room_authz_callback(
    configure_logging,
    ctx,
    w_verbose,
    w_quiet,
    w_default_verbose,
    exp_effective,
):
    with mock.patch.object(
        cli_room_authz,
        "_DEFAULT_VERBOSE",
        w_default_verbose,
    ):
        cli_room_authz._room_authz_callback(
            ctx,
            verbose=w_verbose,
            quiet=w_quiet,
            cli_log_config=None,
        )

    assert ctx.obj == {"verbose": exp_effective}
    configure_logging.assert_called_once_with(None)


@pytest.mark.parametrize(
    "w_configured, w_room_id, exp_raises",
    [
        # No configured rooms; any id is unknown.
        ([], "anything", True),
        # Configured rooms; matching id is OK.
        (["chat"], "chat", False),
        (["chat", "search"], "search", False),
        # Configured rooms; non-matching id is rejected.
        (["chat"], "search", True),
        (["chat", "search"], "nosuch", True),
    ],
)
@mock.patch("soliplex.cli.room_authz.the_console")
def test__check_room_id(
    the_console,
    the_installation,
    w_configured,
    w_room_id,
    exp_raises,
):
    the_installation._config.room_configs = {
        rid: mock.Mock() for rid in w_configured
    }

    if not exp_raises:
        cli_room_authz._check_room_id(the_installation, w_room_id)

        the_console.rule.assert_not_called()
        the_console.print.assert_not_called()
        return

    with pytest.raises(typer.Exit) as excinfo:
        cli_room_authz._check_room_id(the_installation, w_room_id)

    (return_code,) = excinfo.value.args
    assert return_code == 1

    the_console.rule.assert_called_once_with(
        f"No room configured with id '{w_room_id}'",
    )
    if w_configured:
        the_console.print.assert_called_once_with(
            f"Configured rooms: {', '.join(sorted(w_configured))}",
        )
    else:
        the_console.print.assert_called_once_with(
            "The installation has no rooms configured.",
        )


@pytest.mark.parametrize(
    "w_kwargs, exp_text",
    [
        # 'everyone' wins outright.
        ({"everyone": True}, "everyone"),
        # ... even when other discriminators are also set.
        (
            {"everyone": True, "authenticated": True, "json_path": "$.foo"},
            "everyone",
        ),
        # 'authenticated' is the second priority.
        ({"authenticated": True}, "authenticated"),
        # A 'preferred_username' entry (the model surfaces it directly).
        ({"preferred_username": "alice"}, "preferred_username=alice"),
        # An 'email' entry.
        ({"email": "alice@example.com"}, "email=alice@example.com"),
        # A general-purpose query is shown verbatim.
        (
            {"json_path": "$[?match($.foo, 'b.*z')]"},
            "json_path=$[?match($.foo, 'b.*z')]",
        ),
        # No discriminator set is treated as invalid (defensive).
        ({}, "(invalid: no discriminator set)"),
    ],
)
def test__describe_discriminator(w_kwargs, exp_text):
    entry = models.ACLEntryUnchecked(**w_kwargs)

    found = cli_room_authz._describe_discriminator(entry)

    assert found == exp_text


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
@mock.patch("soliplex.cli.room_authz._human_dump_room_policy")
@mock.patch("soliplex.cli.room_authz._dump_room_policy")
def test__dump(
    _dump_room_policy,
    _human_dump_room_policy,
    ctx,
    w_obj,
    exp_human,
):
    ctx.obj = w_obj
    policy = mock.Mock()

    cli_room_authz._dump(ctx, "room-1", policy)

    if exp_human:
        _human_dump_room_policy.assert_called_once_with("room-1", policy)
        _dump_room_policy.assert_not_called()
    else:
        _dump_room_policy.assert_called_once_with(policy)
        _human_dump_room_policy.assert_not_called()


def _mock_acl_entry(
    *,
    allow_deny=authz.AllowDeny.DENY,
    everyone=False,
    authenticated=False,
    preferred_username=None,
    email=None,
    json_path=None,
):
    return models.ACLEntryUnchecked(
        allow_deny=allow_deny,
        everyone=everyone,
        authenticated=authenticated,
        preferred_username=preferred_username,
        email=email,
        json_path=json_path,
    )


@pytest.mark.parametrize(
    "w_entry_kw, exp",
    [
        # 'everyone' entry: no discriminator fields beyond the flag.
        (
            {"allow_deny": authz.AllowDeny.ALLOW, "everyone": True},
            {
                "allow_deny": "ALLOW",
                "everyone": True,
                "authenticated": False,
                "preferred_username": None,
                "email": None,
                "json_path": None,
            },
        ),
        # 'authenticated' entry.
        (
            {
                "allow_deny": authz.AllowDeny.DENY,
                "authenticated": True,
            },
            {
                "allow_deny": "DENY",
                "everyone": False,
                "authenticated": True,
                "preferred_username": None,
                "email": None,
                "json_path": None,
            },
        ),
        # A 'preferred_username' entry (the model surfaces it directly).
        (
            {
                "allow_deny": authz.AllowDeny.ALLOW,
                "preferred_username": "alice",
            },
            {
                "allow_deny": "ALLOW",
                "everyone": False,
                "authenticated": False,
                "preferred_username": "alice",
                "email": None,
                "json_path": None,
            },
        ),
        # An 'email' entry.
        (
            {
                "allow_deny": authz.AllowDeny.ALLOW,
                "email": "alice@example.com",
            },
            {
                "allow_deny": "ALLOW",
                "everyone": False,
                "authenticated": False,
                "preferred_username": None,
                "email": "alice@example.com",
                "json_path": None,
            },
        ),
        # General-purpose JSONPath: passed through verbatim.
        (
            {
                "allow_deny": authz.AllowDeny.DENY,
                "json_path": "$[?match($.foo, 'b.*z')]",
            },
            {
                "allow_deny": "DENY",
                "everyone": False,
                "authenticated": False,
                "preferred_username": None,
                "email": None,
                "json_path": "$[?match($.foo, 'b.*z')]",
            },
        ),
        # A stored 'json_path' that no longer compiles: passed through
        # (the unchecked model carries it without validation).
        (
            {
                "allow_deny": authz.AllowDeny.DENY,
                "json_path": "$[?stale_filter_func($.email)]",
            },
            {
                "allow_deny": "DENY",
                "everyone": False,
                "authenticated": False,
                "preferred_username": None,
                "email": None,
                "json_path": "$[?stale_filter_func($.email)]",
            },
        ),
    ],
)
def test__acl_entry_as_jsonable(w_entry_kw, exp):
    entry = _mock_acl_entry(**w_entry_kw)

    found = cli_room_authz._acl_entry_as_jsonable(entry)

    assert found == exp


def test__room_policy_as_jsonable_none():
    assert cli_room_authz._room_policy_as_jsonable(None) is None


def test__room_policy_as_jsonable_empty():
    policy = models.RoomPolicyUnchecked(
        room_id="chat",
        default_allow_deny=authz.AllowDeny.DENY,
        acl_entries=[],
    )

    found = cli_room_authz._room_policy_as_jsonable(policy)

    assert found == {
        "room_id": "chat",
        "default_allow_deny": "DENY",
        "acl_entries": [],
    }


def test__room_policy_as_jsonable_populated_w_invalid_json_path():
    # The middle entry's 'json_path' would fail compilation today;
    # dumping must still succeed (the unchecked model carries it).
    policy = models.RoomPolicyUnchecked(
        room_id="chat",
        default_allow_deny=authz.AllowDeny.ALLOW,
        acl_entries=[
            _mock_acl_entry(
                allow_deny=authz.AllowDeny.ALLOW,
                email="alice@example.com",
            ),
            _mock_acl_entry(
                allow_deny=authz.AllowDeny.DENY,
                json_path="$[?stale_filter_func($.email)]",
            ),
            _mock_acl_entry(
                allow_deny=authz.AllowDeny.DENY,
                everyone=True,
            ),
        ],
    )

    found = cli_room_authz._room_policy_as_jsonable(policy)

    assert found == {
        "room_id": "chat",
        "default_allow_deny": "ALLOW",
        "acl_entries": [
            {
                "allow_deny": "ALLOW",
                "everyone": False,
                "authenticated": False,
                "preferred_username": None,
                "email": "alice@example.com",
                "json_path": None,
            },
            {
                "allow_deny": "DENY",
                "everyone": False,
                "authenticated": False,
                "preferred_username": None,
                "email": None,
                "json_path": "$[?stale_filter_func($.email)]",
            },
            {
                "allow_deny": "DENY",
                "everyone": True,
                "authenticated": False,
                "preferred_username": None,
                "email": None,
                "json_path": None,
            },
        ],
    }


def test__room_policy_as_yaml_none():
    assert yaml.safe_load(cli_room_authz._room_policy_as_yaml(None)) is None


def test__room_policy_as_yaml_populated():
    policy = models.RoomPolicyUnchecked(
        room_id="chat",
        default_allow_deny=authz.AllowDeny.ALLOW,
        acl_entries=[
            _mock_acl_entry(
                allow_deny=authz.AllowDeny.ALLOW,
                email="alice@example.com",
            ),
        ],
    )

    found = cli_room_authz._room_policy_as_yaml(policy)

    assert yaml.safe_load(found) == {
        "room_id": "chat",
        "default_allow_deny": "ALLOW",
        "acl_entries": [
            {
                "allow_deny": "ALLOW",
                "everyone": False,
                "authenticated": False,
                "preferred_username": None,
                "email": "alice@example.com",
                "json_path": None,
            },
        ],
    }


@pytest.mark.parametrize(
    "jsonable, expected",
    [
        # A 'null' document -> no policy.
        (None, None),
        # Empty policy: default-DENY, no ACL entries.
        (
            {
                "room_id": "chat",
                "default_allow_deny": "DENY",
                "acl_entries": [],
            },
            models.RoomPolicy(
                room_id="chat",
                default_allow_deny=authz.AllowDeny.DENY,
                acl_entries=[],
            ),
        ),
        # Populated policy: 'AllowDeny' member names are converted back
        # to enum members; each entry keeps its single discriminator.
        (
            {
                "room_id": "chat",
                "default_allow_deny": "ALLOW",
                "acl_entries": [
                    {
                        "allow_deny": "ALLOW",
                        "everyone": False,
                        "authenticated": False,
                        "preferred_username": None,
                        "email": "alice@example.com",
                        "json_path": None,
                    },
                    {
                        "allow_deny": "DENY",
                        "everyone": True,
                        "authenticated": False,
                        "preferred_username": None,
                        "email": None,
                        "json_path": None,
                    },
                ],
            },
            models.RoomPolicy(
                room_id="chat",
                default_allow_deny=authz.AllowDeny.ALLOW,
                acl_entries=[
                    models.ACLEntry(
                        allow_deny=authz.AllowDeny.ALLOW,
                        email="alice@example.com",
                    ),
                    models.ACLEntry(
                        allow_deny=authz.AllowDeny.DENY,
                        everyone=True,
                    ),
                ],
            ),
        ),
    ],
)
def test__room_policy_from_jsonable(jsonable, expected):
    assert cli_room_authz._room_policy_from_jsonable(jsonable) == expected


@pytest.mark.parametrize(
    "room_id, model, expected",
    [
        # Explicit room_id wins, even when the model carries one.
        ("chat", None, "chat"),
        (
            "chat",
            models.RoomPolicy(room_id="search"),
            "chat",
        ),
        # No explicit room_id -> fall back to the model's room_id.
        (None, models.RoomPolicy(room_id="search"), "search"),
        # Neither available -> None.
        (None, None, None),
    ],
)
def test__effective_room_id(room_id, model, expected):
    assert cli_room_authz._effective_room_id(room_id, model) == expected


@pytest.mark.parametrize(
    "w_allow, w_deny, exp_allow_deny",
    [
        (True, False, authz.AllowDeny.ALLOW),
        (False, True, authz.AllowDeny.DENY),
    ],
)
def test__resolve_allow_deny_returns_enum(w_allow, w_deny, exp_allow_deny):
    found = cli_room_authz._resolve_allow_deny(w_allow, w_deny)

    assert found is exp_allow_deny


@pytest.mark.parametrize(
    "w_allow, w_deny, exp_flags_given",
    [
        # Neither set: the error message reports '(none)'.
        (False, False, ["(none)"]),
        # Both set: the error message lists both flag names.
        (True, True, ["--allow", "--deny"]),
    ],
)
@mock.patch("soliplex.cli.room_authz.the_console")
def test__resolve_allow_deny_mutex_violation(
    the_console,
    w_allow,
    w_deny,
    exp_flags_given,
):
    with pytest.raises(typer.Exit) as excinfo:
        cli_room_authz._resolve_allow_deny(w_allow, w_deny)

    (return_code,) = excinfo.value.args
    assert return_code == 1

    the_console.rule.assert_called_once_with(
        "Exactly one of '--allow' or '--deny' required",
    )
    the_console.print.assert_called_once_with(
        f"Pass exactly one of '--allow' or '--deny'. Got: {exp_flags_given}.",
    )


@mock.patch("soliplex.cli.room_authz.cli_util._check_ram_dburi")
@mock.patch("soliplex.cli.room_authz.cli_util.get_installation")
def test__check_acl_entry_args(get_installation, _check_ram_dburi):
    the_installation = get_installation.return_value
    the_installation._config.room_configs = {"chat": mock.Mock()}
    the_installation.authorization_dburi_async = "sqlite:///fake.sqlite"

    found = cli_room_authz._check_acl_entry_args(
        mock.sentinel.installation_path,
        "chat",
        allow=True,
        deny=False,
        everyone=False,
        authenticated=False,
        json_path=None,
        preferred_username="alice",
        email=None,
        command="room-authz add-acl-entry",
    )

    assert found == (
        "sqlite:///fake.sqlite",
        authz.AllowDeny.ALLOW,
        '$[?$.preferred_username == "alice"]',
    )

    get_installation.assert_called_once_with(mock.sentinel.installation_path)
    _check_ram_dburi.assert_called_once_with(
        "sqlite:///fake.sqlite",
        "room-authz add-acl-entry",
    )


@mock.patch("soliplex.cli.room_authz.cli_util._check_ram_dburi")
@mock.patch("soliplex.cli.room_authz.cli_util.get_installation")
def test__check_acl_entry_args_allow_invalid_json_path(
    get_installation,
    _check_ram_dburi,
):
    the_installation = get_installation.return_value
    the_installation._config.room_configs = {"chat": mock.Mock()}
    the_installation.authorization_dburi_async = "sqlite:///fake.sqlite"

    bogus = "$[?stale_filter_func($.email)]"

    found = cli_room_authz._check_acl_entry_args(
        mock.sentinel.installation_path,
        "chat",
        allow=False,
        deny=True,
        everyone=False,
        authenticated=False,
        json_path=bogus,
        preferred_username=None,
        email=None,
        command="room-authz delete-acl-entry",
        allow_invalid_json_path=True,
    )

    assert found == (
        "sqlite:///fake.sqlite",
        authz.AllowDeny.DENY,
        bogus,
    )


# ---------------------------------------------------------------------------
# Command-level tests.
#
# These drive the actual 'room-authz' subcommands through a Typer
# 'CliRunner' against a throwaway copy of 'example/minimal.yaml' backed by
# a scratch authorization database (see the 'scratch_installation' and
# 'cli_runner' fixtures in 'tests/unit/cli/conftest.py'). Every command
# body is now exercised here rather than coverage-excluded; only the two
# '_*_dump_room_policy' helpers stay '# pragma NO COVER UI ONLY'.
# ---------------------------------------------------------------------------

ALLOW = authz.AllowDeny.ALLOW
DENY = authz.AllowDeny.DENY

ALICE_EMAIL = "alice@example.com"
ALICE_EMAIL_JP = authz.token_field_json_path("email", ALICE_EMAIL)
# A stored query that no longer compiles (e.g. it referenced a meta-config
# filter function that has since been removed).
STALE_JP = "$[?stale_filter_func($.email)]"


def _entry(allow_deny, *, everyone=False, authenticated=False, json_path=None):
    """An ACL-entry kwargs dict in the shape the commands build/store."""
    return {
        "allow_deny": allow_deny,
        "everyone": everyone,
        "authenticated": authenticated,
        "json_path": json_path,
    }


def _seed_policy(scratch, room_id, default_allow_deny, entries=()):
    """Insert a RoomPolicy (and ACL entries) straight into the scratch DB."""
    session = scratch.session()
    with session:
        policy = authz_schema.RoomPolicy(
            room_id=room_id,
            default_allow_deny=default_allow_deny,
        )
        session.add(policy)
        session.flush()
        for entry_kw in entries:
            session.add(
                authz_schema.ACLEntry(room_policy=policy, **entry_kw),
            )
        session.commit()
    session.bind.dispose()


def _seed_stale_acl_entry(scratch, room_id, allow_deny, stale_json_path):
    """Plant an ACL entry whose stored 'json_path' no longer compiles.

    The ORM's 'json_path' validator rejects a non-compiling query on
    insert (and on any attribute-set), so the stale entry is created in
    two steps: seed a normal entry carrying a *valid* placeholder query
    through 'authz_schema.ACLEntry', then rewrite that entry's
    'json_path' to the non-compiling value with a raw UPDATE -- which
    does not run the '@validates' hook. This reproduces the on-disk
    state left behind when a meta-config filter function an entry
    referenced is removed, so 'delete-acl-entry --allow-invalid-json-path'
    can be exercised end-to-end.
    """
    _seed_policy(
        scratch,
        room_id,
        DENY,
        [_entry(allow_deny, json_path=ALICE_EMAIL_JP)],
    )
    session = scratch.session()
    with session:
        session.execute(
            sqlalchemy.text(
                "UPDATE room_acl_entries SET json_path = :stale "
                "WHERE json_path = :placeholder"
            ),
            {"stale": stale_json_path, "placeholder": ALICE_EMAIL_JP},
        )
        session.commit()
    session.bind.dispose()


def _read_policy(scratch, room_id):
    """Read a room's policy back from the scratch DB, or None.

    ACL entries are returned as a set of '(allow_deny, everyone,
    authenticated, json_path)' tuples -- a set because the 'AllowDeny'
    enum is not orderable, so sets sidestep ordering entirely.
    """
    session = scratch.session()
    with session:
        policy = (
            session.query(authz_schema.RoomPolicy)
            .where(authz_schema.RoomPolicy.room_id == room_id)
            .first()
        )
        if policy is None:
            result = None
        else:
            result = {
                "default": policy.default_allow_deny,
                "entries": {
                    (
                        entry.allow_deny,
                        entry.everyone,
                        entry.authenticated,
                        entry.json_path,
                    )
                    for entry in policy.acl_entries
                },
            }
    session.bind.dispose()
    return result


def _invoke(cli_runner, scratch, subcommand, *rest, **kwargs):
    return cli_runner.invoke(
        cli_room_authz.app,
        [subcommand, str(scratch.path), *rest],
        **kwargs,
    )


@mock.patch("soliplex.cli.cli_util._configure_cli_logging")
def test_cli_log_config_from_env(
    configure_logging, scratch_installation, cli_runner, tmp_path
):
    # The '--cli-log-config' option is backed by 'SOLIPLEX_CLI_LOG_CONFIG'
    # via Typer's 'envvar='; the env value reaches the callback as a Path.
    cfg = tmp_path / "audit-logging.yaml"
    cfg.write_text("version: 1\n")

    result = _invoke(
        cli_runner,
        scratch_installation,
        "show",
        "chat",
        env={"SOLIPLEX_CLI_LOG_CONFIG": str(cfg)},
    )

    assert result.exit_code == 0
    # The group callback (which runs first) forwards the env-derived Path;
    # the '_authz_session' safety net then calls it again with no argument.
    assert configure_logging.call_args_list[0] == mock.call(cfg)


# -- show -------------------------------------------------------------------


def test_show_configured_room(scratch_installation, cli_runner):
    _seed_policy(scratch_installation, "chat", DENY)

    result = _invoke(cli_runner, scratch_installation, "show", "chat")

    assert result.exit_code == 0
    assert '"room_id": "chat"' in result.output


def test_show_unconfigured_room_requires_allow_stale(
    scratch_installation,
    cli_runner,
):
    # A policy left behind by a removed/renamed room.
    _seed_policy(scratch_installation, "ghost", DENY)

    # Without '--allow-stale' the configured-room check rejects it.
    rejected = _invoke(cli_runner, scratch_installation, "show", "ghost")
    assert rejected.exit_code == 1

    # With '--allow-stale' the stale policy can still be inspected.
    allowed = _invoke(
        cli_runner,
        scratch_installation,
        "show",
        "ghost",
        "--allow-stale",
    )
    assert allowed.exit_code == 0
    assert '"room_id": "ghost"' in allowed.output


# -- make-private -----------------------------------------------------------


def test_make_private_creates_policy(scratch_installation, cli_runner):
    result = _invoke(cli_runner, scratch_installation, "make-private", "chat")

    assert result.exit_code == 0
    assert _read_policy(scratch_installation, "chat") == {
        "default": DENY,
        "entries": set(),
    }


def test_make_private_noop_when_already_deny(
    scratch_installation,
    cli_runner,
):
    _seed_policy(
        scratch_installation,
        "chat",
        DENY,
        [_entry(ALLOW, everyone=True)],
    )

    result = _invoke(cli_runner, scratch_installation, "make-private", "chat")

    assert result.exit_code == 0
    # Existing default + ACL entries are left untouched.
    policy = _read_policy(scratch_installation, "chat")
    assert policy["default"] == DENY
    assert policy["entries"] == {(ALLOW, True, False, None)}


def test_make_private_existing_allow_requires_update(
    scratch_installation,
    cli_runner,
):
    _seed_policy(scratch_installation, "chat", ALLOW)

    result = _invoke(cli_runner, scratch_installation, "make-private", "chat")

    assert result.exit_code == 1
    # Left as ALLOW because '--update' was not supplied.
    assert _read_policy(scratch_installation, "chat")["default"] == ALLOW


def test_make_private_update_flips_allow_to_deny(
    scratch_installation,
    cli_runner,
):
    _seed_policy(
        scratch_installation,
        "chat",
        ALLOW,
        [_entry(ALLOW, everyone=True)],
    )

    result = _invoke(
        cli_runner,
        scratch_installation,
        "make-private",
        "chat",
        "--update",
    )

    assert result.exit_code == 0
    policy = _read_policy(scratch_installation, "chat")
    assert policy["default"] == DENY
    # ACL entries are preserved across the flip.
    assert policy["entries"] == {(ALLOW, True, False, None)}


# -- make-public ------------------------------------------------------------


def test_make_public_noop_when_no_policy(scratch_installation, cli_runner):
    result = _invoke(cli_runner, scratch_installation, "make-public", "chat")

    assert result.exit_code == 0
    # A room with no policy is already public-by-default; none is created.
    assert _read_policy(scratch_installation, "chat") is None


def test_make_public_noop_when_already_allow(
    scratch_installation,
    cli_runner,
):
    _seed_policy(scratch_installation, "chat", ALLOW)

    result = _invoke(cli_runner, scratch_installation, "make-public", "chat")

    assert result.exit_code == 0
    assert _read_policy(scratch_installation, "chat")["default"] == ALLOW


def test_make_public_existing_deny_requires_update(
    scratch_installation,
    cli_runner,
):
    _seed_policy(scratch_installation, "chat", DENY)

    result = _invoke(cli_runner, scratch_installation, "make-public", "chat")

    assert result.exit_code == 1
    assert _read_policy(scratch_installation, "chat")["default"] == DENY


def test_make_public_update_flips_deny_to_allow(
    scratch_installation,
    cli_runner,
):
    _seed_policy(
        scratch_installation,
        "chat",
        DENY,
        [_entry(DENY, everyone=True)],
    )

    result = _invoke(
        cli_runner,
        scratch_installation,
        "make-public",
        "chat",
        "--update",
    )

    assert result.exit_code == 0
    policy = _read_policy(scratch_installation, "chat")
    assert policy["default"] == ALLOW
    assert policy["entries"] == {(DENY, True, False, None)}


# -- clear-acl --------------------------------------------------------------


def test_clear_acl_noop_when_no_policy(scratch_installation, cli_runner):
    result = _invoke(cli_runner, scratch_installation, "clear-acl", "chat")

    assert result.exit_code == 0
    assert _read_policy(scratch_installation, "chat") is None


def test_clear_acl_removes_entries_preserving_policy(
    scratch_installation,
    cli_runner,
):
    _seed_policy(
        scratch_installation,
        "chat",
        DENY,
        [
            _entry(ALLOW, everyone=True),
            _entry(ALLOW, authenticated=True),
        ],
    )

    result = _invoke(cli_runner, scratch_installation, "clear-acl", "chat")

    assert result.exit_code == 0
    # Policy row (and its default) survives; only ACL entries are cleared.
    assert _read_policy(scratch_installation, "chat") == {
        "default": DENY,
        "entries": set(),
    }


# -- add-acl-entry ----------------------------------------------------------


def test_add_acl_entry_requires_existing_policy(
    scratch_installation,
    cli_runner,
):
    result = _invoke(
        cli_runner,
        scratch_installation,
        "add-acl-entry",
        "chat",
        "--allow",
        "--everyone",
    )

    assert result.exit_code == 1
    assert _read_policy(scratch_installation, "chat") is None


def test_add_acl_entry_replaces_matching_discriminators(
    scratch_installation,
    cli_runner,
):
    # One entry of each discriminator kind, so each replace branch fires.
    _seed_policy(
        scratch_installation,
        "chat",
        DENY,
        [
            _entry(ALLOW, everyone=True),
            _entry(ALLOW, authenticated=True),
            _entry(ALLOW, json_path=ALICE_EMAIL_JP),
        ],
    )

    # 'everyone' branch: replaces the existing everyone entry (ALLOW->DENY).
    res = _invoke(
        cli_runner,
        scratch_installation,
        "add-acl-entry",
        "chat",
        "--deny",
        "--everyone",
    )
    assert res.exit_code == 0

    # 'authenticated' branch.
    res = _invoke(
        cli_runner,
        scratch_installation,
        "add-acl-entry",
        "chat",
        "--allow",
        "--authenticated",
    )
    assert res.exit_code == 0

    # 'json_path' (via --email) branch.
    res = _invoke(
        cli_runner,
        scratch_installation,
        "add-acl-entry",
        "chat",
        "--allow",
        "--email",
        ALICE_EMAIL,
    )
    assert res.exit_code == 0

    policy = _read_policy(scratch_installation, "chat")
    # Each discriminator still appears exactly once (replaced, not dup'd).
    assert policy["entries"] == {
        (DENY, True, False, None),
        (ALLOW, False, True, None),
        (ALLOW, False, False, ALICE_EMAIL_JP),
    }


# -- delete-acl-entry -------------------------------------------------------


def test_delete_acl_entry_requires_existing_policy(
    scratch_installation,
    cli_runner,
):
    result = _invoke(
        cli_runner,
        scratch_installation,
        "delete-acl-entry",
        "chat",
        "--allow",
        "--everyone",
    )

    assert result.exit_code == 1


def test_delete_acl_entry_no_match_errors(scratch_installation, cli_runner):
    # The only entry has the opposite allow/deny, so nothing matches.
    _seed_policy(
        scratch_installation,
        "chat",
        DENY,
        [_entry(DENY, everyone=True)],
    )

    result = _invoke(
        cli_runner,
        scratch_installation,
        "delete-acl-entry",
        "chat",
        "--allow",
        "--everyone",
    )

    assert result.exit_code == 1
    # The non-matching entry is left in place.
    assert _read_policy(scratch_installation, "chat")["entries"] == {
        (DENY, True, False, None),
    }


def test_delete_acl_entry_removes_matching(scratch_installation, cli_runner):
    _seed_policy(
        scratch_installation,
        "chat",
        DENY,
        [
            _entry(ALLOW, everyone=True),
            _entry(ALLOW, authenticated=True),
            _entry(ALLOW, json_path=ALICE_EMAIL_JP),
            # Opposite allow/deny: skipped via the 'continue' branch.
            _entry(DENY, everyone=True),
        ],
    )

    for discriminator in (
        ("--everyone",),
        ("--authenticated",),
        ("--email", ALICE_EMAIL),
    ):
        res = _invoke(
            cli_runner,
            scratch_installation,
            "delete-acl-entry",
            "chat",
            "--allow",
            *discriminator,
        )
        assert res.exit_code == 0

    # Only the opposite-sense DENY entry that never matched remains.
    assert _read_policy(scratch_installation, "chat")["entries"] == {
        (DENY, True, False, None),
    }


def test_delete_acl_entry_invalid_json_path_requires_flag(
    scratch_installation,
    cli_runner,
):
    _seed_stale_acl_entry(scratch_installation, "chat", DENY, STALE_JP)

    # Without '--allow-invalid-json-path' the compile-validation of the
    # supplied --json-path rejects it before the database is touched.
    rejected = _invoke(
        cli_runner,
        scratch_installation,
        "delete-acl-entry",
        "chat",
        "--deny",
        "--json-path",
        STALE_JP,
    )
    assert rejected.exit_code == 1
    assert _read_policy(scratch_installation, "chat")["entries"] == {
        (DENY, False, False, STALE_JP),
    }

    # With the flag the stale entry can still be matched and removed.
    allowed = _invoke(
        cli_runner,
        scratch_installation,
        "delete-acl-entry",
        "chat",
        "--deny",
        "--json-path",
        STALE_JP,
        "--allow-invalid-json-path",
    )
    assert allowed.exit_code == 0
    assert _read_policy(scratch_installation, "chat")["entries"] == set()


# -- as-yaml / from-yaml ----------------------------------------------------


def test_as_yaml_to_stdout(scratch_installation, cli_runner):
    _seed_policy(
        scratch_installation,
        "chat",
        DENY,
        [_entry(ALLOW, json_path=ALICE_EMAIL_JP)],
    )

    result = _invoke(cli_runner, scratch_installation, "as-yaml", "chat")

    assert result.exit_code == 0
    dumped = yaml.safe_load(result.output)
    assert dumped["room_id"] == "chat"
    assert dumped["default_allow_deny"] == "DENY"
    assert dumped["acl_entries"][0]["email"] == ALICE_EMAIL


def test_as_yaml_allow_stale_to_file(
    scratch_installation,
    cli_runner,
    tmp_path,
):
    # A stale (unconfigured) room dumped to a file via '--allow-stale'.
    _seed_policy(scratch_installation, "ghost", ALLOW)
    out = tmp_path / "ghost.yaml"

    result = _invoke(
        cli_runner,
        scratch_installation,
        "as-yaml",
        "ghost",
        "--allow-stale",
        "-o",
        str(out),
    )

    assert result.exit_code == 0
    assert yaml.safe_load(out.read_text())["room_id"] == "ghost"


def test_as_yaml_then_from_yaml_populates_other_room(
    scratch_installation,
    cli_runner,
    tmp_path,
):
    # Build a fully-configured policy on 'chat' through the CLI ...
    assert (
        _invoke(
            cli_runner, scratch_installation, "make-private", "chat"
        ).exit_code
        == 0
    )
    assert (
        _invoke(
            cli_runner,
            scratch_installation,
            "add-acl-entry",
            "chat",
            "--allow",
            "--email",
            ALICE_EMAIL,
        ).exit_code
        == 0
    )
    assert (
        _invoke(
            cli_runner,
            scratch_installation,
            "add-acl-entry",
            "chat",
            "--deny",
            "--everyone",
        ).exit_code
        == 0
    )

    # ... dump it to YAML ...
    dump = tmp_path / "chat-policy.yaml"
    assert (
        _invoke(
            cli_runner,
            scratch_installation,
            "as-yaml",
            "chat",
            "-o",
            str(dump),
        ).exit_code
        == 0
    )

    # ... and use it to populate a *different* room, 'search'. The
    # explicit ROOM_ID overrides the 'room_id' recorded in the YAML.
    assert (
        _invoke(
            cli_runner,
            scratch_installation,
            "from-yaml",
            "search",
            "-i",
            str(dump),
        ).exit_code
        == 0
    )

    chat = _read_policy(scratch_installation, "chat")
    search = _read_policy(scratch_installation, "search")
    assert search["default"] == chat["default"]
    assert search["entries"] == chat["entries"]


def test_from_yaml_replaces_existing_policy(
    scratch_installation,
    cli_runner,
    tmp_path,
):
    # 'search' already has a policy; importing replaces it wholesale.
    _seed_policy(
        scratch_installation,
        "search",
        ALLOW,
        [_entry(ALLOW, everyone=True)],
    )
    doc = tmp_path / "policy.yaml"
    doc.write_text(
        yaml.safe_dump(
            {
                "room_id": "search",
                "default_allow_deny": "DENY",
                "acl_entries": [
                    {
                        "allow_deny": "ALLOW",
                        "everyone": False,
                        "authenticated": True,
                        "preferred_username": None,
                        "email": None,
                        "json_path": None,
                    },
                ],
            },
        )
    )

    result = _invoke(
        cli_runner,
        scratch_installation,
        "from-yaml",
        "search",
        "-i",
        str(doc),
    )

    assert result.exit_code == 0
    assert _read_policy(scratch_installation, "search") == {
        "default": DENY,
        "entries": {(ALLOW, False, True, None)},
    }


def test_from_yaml_stdin_null_removes_existing(
    scratch_installation,
    cli_runner,
):
    _seed_policy(
        scratch_installation,
        "chat",
        DENY,
        [_entry(ALLOW, everyone=True)],
    )

    # 'null' read from stdin removes the target room's policy entirely.
    result = _invoke(
        cli_runner,
        scratch_installation,
        "from-yaml",
        "chat",
        input="null\n",
    )

    assert result.exit_code == 0
    assert _read_policy(scratch_installation, "chat") is None


def test_from_yaml_null_without_room_id_errors(
    scratch_installation,
    cli_runner,
):
    # A 'null' document with no explicit ROOM_ID has no target room.
    result = _invoke(
        cli_runner,
        scratch_installation,
        "from-yaml",
        input="null\n",
    )

    assert result.exit_code == 1
