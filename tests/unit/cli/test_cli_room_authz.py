from __future__ import annotations

from unittest import mock

import pytest
import typer
import yaml

from soliplex import authz as authz_package
from soliplex import installation
from soliplex import models
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
def test__room_authz_callback(
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
        )

    assert ctx.obj == {"verbose": exp_effective}


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
    "w_attrs, exp_text",
    [
        # 'everyone' wins outright.
        (
            {
                "everyone": True,
                "authenticated": False,
                "json_path": None,
            },
            "everyone",
        ),
        # ... even when other discriminators are also set.
        (
            {
                "everyone": True,
                "authenticated": True,
                "json_path": "$.foo",
            },
            "everyone",
        ),
        # 'authenticated' is the second priority.
        (
            {
                "everyone": False,
                "authenticated": True,
                "json_path": None,
            },
            "authenticated",
        ),
        # A general-purpose query is shown verbatim.
        (
            {
                "everyone": False,
                "authenticated": False,
                "json_path": "$[?match($.foo, 'b.*z')]",
            },
            "json_path=$[?match($.foo, 'b.*z')]",
        ),
        # A converted 'preferred_username' query is humanized back.
        (
            {
                "everyone": False,
                "authenticated": False,
                "json_path": '$[?$.preferred_username == "alice"]',
            },
            "preferred_username=alice",
        ),
        # A converted 'email' query is humanized back.
        (
            {
                "everyone": False,
                "authenticated": False,
                "json_path": '$[?$.email == "alice@example.com"]',
            },
            "email=alice@example.com",
        ),
        # No discriminator set is treated as invalid (defensive).
        (
            {
                "everyone": False,
                "authenticated": False,
                "json_path": None,
            },
            "(invalid: no discriminator set)",
        ),
    ],
)
def test__describe_discriminator(w_attrs, exp_text):
    entry = mock.Mock(**w_attrs)

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
    session = mock.Mock()

    cli_room_authz._dump(ctx, session, "room-1")

    if exp_human:
        _human_dump_room_policy.assert_called_once_with(session, "room-1")
        _dump_room_policy.assert_not_called()
    else:
        _dump_room_policy.assert_called_once_with(session, "room-1")
        _human_dump_room_policy.assert_not_called()


@pytest.mark.parametrize(
    "w_dumped, exp_jsonable",
    [
        # No policy row -> passes through as None.
        (None, None),
        # Empty policy: default-DENY, no ACL entries.
        (
            {
                "room_id": "chat",
                "default_allow_deny": authz_package.AllowDeny.DENY,
                "acl_entries": [],
            },
            {
                "room_id": "chat",
                "default_allow_deny": "DENY",
                "acl_entries": [],
            },
        ),
        # Populated policy: both 'default_allow_deny' and each entry's
        # 'allow_deny' must be emitted as their bare member names, not
        # as the 'AllowDeny.<NAME>' default 'str()' form.
        (
            {
                "room_id": "chat",
                "default_allow_deny": authz_package.AllowDeny.ALLOW,
                "acl_entries": [
                    {
                        "allow_deny": authz_package.AllowDeny.ALLOW,
                        "everyone": False,
                        "authenticated": False,
                        "preferred_username": None,
                        "email": "alice@example.com",
                    },
                    {
                        "allow_deny": authz_package.AllowDeny.DENY,
                        "everyone": True,
                        "authenticated": False,
                        "preferred_username": None,
                        "email": None,
                    },
                ],
            },
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
                    },
                    {
                        "allow_deny": "DENY",
                        "everyone": True,
                        "authenticated": False,
                        "preferred_username": None,
                        "email": None,
                    },
                ],
            },
        ),
    ],
)
def test__room_policy_as_jsonable(w_dumped, exp_jsonable):
    if w_dumped is None:
        policy = None
    else:
        policy = mock.Mock()
        policy.as_model.model_dump.return_value = w_dumped

    found = cli_room_authz._room_policy_as_jsonable(policy)

    assert found == exp_jsonable


@pytest.mark.parametrize(
    "w_dumped, exp_loaded",
    [
        # No policy row -> dumps as 'null'.
        (None, None),
        # Populated policy: round-trips to the JSON-serializable shape,
        # with 'AllowDeny' values emitted as their member names.
        (
            {
                "room_id": "chat",
                "default_allow_deny": authz_package.AllowDeny.ALLOW,
                "acl_entries": [
                    {
                        "allow_deny": authz_package.AllowDeny.ALLOW,
                        "everyone": False,
                        "authenticated": False,
                        "preferred_username": None,
                        "email": None,
                        "json_path": '$[?$.email == "alice@example.com"]',
                    },
                ],
            },
            {
                "room_id": "chat",
                "default_allow_deny": "ALLOW",
                "acl_entries": [
                    {
                        "allow_deny": "ALLOW",
                        "everyone": False,
                        "authenticated": False,
                        "preferred_username": None,
                        "email": None,
                        "json_path": '$[?$.email == "alice@example.com"]',
                    },
                ],
            },
        ),
    ],
)
def test__room_policy_as_yaml(w_dumped, exp_loaded):
    if w_dumped is None:
        policy = None
    else:
        policy = mock.Mock()
        policy.as_model.model_dump.return_value = w_dumped

    found = cli_room_authz._room_policy_as_yaml(policy)

    assert yaml.safe_load(found) == exp_loaded


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
                default_allow_deny=authz_package.AllowDeny.DENY,
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
                default_allow_deny=authz_package.AllowDeny.ALLOW,
                acl_entries=[
                    models.ACLEntry(
                        allow_deny=authz_package.AllowDeny.ALLOW,
                        email="alice@example.com",
                    ),
                    models.ACLEntry(
                        allow_deny=authz_package.AllowDeny.DENY,
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
        (True, False, authz_package.AllowDeny.ALLOW),
        (False, True, authz_package.AllowDeny.DENY),
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


@pytest.mark.parametrize(
    "w_kwargs",
    [
        # Exactly one set: each branch in turn.
        {"everyone": True},
        {"authenticated": True},
        {"json_path": "$.foo"},
        {"preferred_username": "alice"},
        {"email": "alice@example.com"},
    ],
)
@mock.patch("soliplex.cli.room_authz.the_console")
def test__check_discriminator_accepts_exactly_one(the_console, w_kwargs):
    kwargs = {
        "everyone": False,
        "authenticated": False,
        "json_path": None,
        "preferred_username": None,
        "email": None,
        **w_kwargs,
    }

    cli_room_authz._check_discriminator(**kwargs)

    the_console.rule.assert_not_called()
    the_console.print.assert_not_called()


@pytest.mark.parametrize(
    "w_kwargs, exp_selected",
    [
        # None set -> error message reports '(none)'.
        ({}, ["(none)"]),
        # Two boolean flags collide.
        (
            {"everyone": True, "authenticated": True},
            ["--everyone", "--authenticated"],
        ),
        # A boolean flag collides with a value-bearing option.
        (
            {"everyone": True, "json_path": "$.foo"},
            ["--everyone", "--json-path"],
        ),
        # Two value-bearing options collide.
        (
            {"preferred_username": "alice", "email": "alice@example.com"},
            ["--preferred-username", "--email"],
        ),
        # All five set.
        (
            {
                "everyone": True,
                "authenticated": True,
                "json_path": "$.foo",
                "preferred_username": "alice",
                "email": "alice@example.com",
            },
            [
                "--everyone",
                "--authenticated",
                "--json-path",
                "--preferred-username",
                "--email",
            ],
        ),
    ],
)
@mock.patch("soliplex.cli.room_authz.the_console")
def test__check_discriminator_rejects_other_arities(
    the_console,
    w_kwargs,
    exp_selected,
):
    kwargs = {
        "everyone": False,
        "authenticated": False,
        "json_path": None,
        "preferred_username": None,
        "email": None,
        **w_kwargs,
    }

    with pytest.raises(typer.Exit) as excinfo:
        cli_room_authz._check_discriminator(**kwargs)

    (return_code,) = excinfo.value.args
    assert return_code == 1

    the_console.rule.assert_called_once_with(
        "Exactly one discriminator required",
    )
    the_console.print.assert_called_once_with(
        "Pass exactly one of '--everyone', '--authenticated', "
        "'--json-path', '--preferred-username', or '--email'. "
        f"Got: {exp_selected}.",
    )


@pytest.mark.parametrize(
    "w_json_path, w_preferred_username, w_email, exp",
    [
        # No claim shortcut, no json_path -> None passes through.
        (None, None, None, None),
        # A literal json_path passes through unchanged.
        ("$.foo", None, None, "$.foo"),
        # 'preferred_username' is translated to the canonical form.
        (
            None,
            "alice",
            None,
            '$[?$.preferred_username == "alice"]',
        ),
        # 'email' is translated to the canonical form.
        (
            None,
            None,
            "alice@example.com",
            '$[?$.email == "alice@example.com"]',
        ),
        # 'preferred_username' takes precedence over a literal json_path
        # (the caller should have ensured exclusivity already, but the
        # helper is documented to prefer the claim shortcut).
        ("$.ignored", "alice", None, '$[?$.preferred_username == "alice"]'),
        # ... and over 'email' for the same reason.
        (
            None,
            "alice",
            "alice@example.com",
            '$[?$.preferred_username == "alice"]',
        ),
    ],
)
def test__resolve_json_path(
    w_json_path,
    w_preferred_username,
    w_email,
    exp,
):
    # The first positional arg stands in for a loaded installation;
    # its only role is to enforce the call ordering at the call site.
    found = cli_room_authz._resolve_json_path(
        mock.sentinel.the_installation,
        w_json_path,
        w_preferred_username,
        w_email,
    )

    assert found == exp


@mock.patch("soliplex.cli.room_authz.the_console")
def test__resolve_json_path_invalid_raises(the_console):
    bogus = "$[?this is not a query]"

    with pytest.raises(typer.Exit) as excinfo:
        cli_room_authz._resolve_json_path(
            mock.sentinel.the_installation, bogus, None, None
        )

    (return_code,) = excinfo.value.args
    assert return_code == 1

    the_console.rule.assert_called_once_with("Invalid JSONPath")
    (print_args, _) = the_console.print.call_args
    (printed,) = print_args
    assert bogus in printed


def test__resolve_json_path_w_meta_config_filter_function(
    patched_jsonpath_functions,
):
    # Regression test for soliplex/soliplex#1017: a JSONPath query that
    # uses a filter function registered into the shared environment
    # (as 'InstallationConfigMeta.__post_init__' does for every
    # 'meta.jsonpath_functions' entry) must validate successfully when
    # '_resolve_json_path' runs after the installation has been loaded.
    def filter_func(value):  # pragma: NO COVER (registered, not called)
        return value

    json_path = "$[?filter_func($.email)]"

    # Sanity check: without the registration, the bare query fails to
    # compile (and would fall through to 'typer.Exit(1)').
    with pytest.raises(authz_package.InvalidJSONPath):
        authz_package.validate_json_path(json_path)

    authz_package.register_jsonpath_function("filter_func", filter_func)

    found = cli_room_authz._resolve_json_path(
        mock.sentinel.the_installation,
        json_path,
        None,
        None,
    )

    assert found == json_path
    assert patched_jsonpath_functions["filter_func"] is filter_func


@mock.patch("soliplex.cli.room_authz.cli_util._check_ram_dburi")
@mock.patch("soliplex.cli.room_authz.cli_util.get_installation")
def test__check_acl_entry_args(get_installation, _check_ram_dburi):
    the_installation = get_installation.return_value
    the_installation._config.room_configs = {"chat": mock.Mock()}
    the_installation.authorization_dburi_sync = "sqlite:///fake.sqlite"

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
        authz_package.AllowDeny.ALLOW,
        '$[?$.preferred_username == "alice"]',
    )

    get_installation.assert_called_once_with(mock.sentinel.installation_path)
    _check_ram_dburi.assert_called_once_with(
        "sqlite:///fake.sqlite",
        "room-authz add-acl-entry",
    )


# _human_dump_room_policy: ui only
# _dump_room_policy: ui only
# show_room_authz: command
# make_room_private: command
# make_room_public: command
# clear_room_acl: command
# add_acl_entry: command
# delete_acl_entry: command
# add_room_user: command (deprecated)
# clear_room_authz: command (deprecated)
