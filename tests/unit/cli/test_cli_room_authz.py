from __future__ import annotations

from unittest import mock

import pytest
import typer

from soliplex import authz as authz_package
from soliplex import installation
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
                "preferred_username": None,
                "email": None,
            },
            "everyone",
        ),
        # ... even when other discriminators are also set.
        (
            {
                "everyone": True,
                "authenticated": True,
                "preferred_username": "alice",
                "email": "alice@example.com",
            },
            "everyone",
        ),
        # 'authenticated' is the second priority.
        (
            {
                "everyone": False,
                "authenticated": True,
                "preferred_username": None,
                "email": None,
            },
            "authenticated",
        ),
        # 'preferred_username' is the third priority.
        (
            {
                "everyone": False,
                "authenticated": False,
                "preferred_username": "alice",
                "email": None,
            },
            "preferred_username=alice",
        ),
        # 'email' is the fallback when only it is set.
        (
            {
                "everyone": False,
                "authenticated": False,
                "preferred_username": None,
                "email": "alice@example.com",
            },
            "email=alice@example.com",
        ),
        # No discriminator set is treated as invalid (defensive).
        (
            {
                "everyone": False,
                "authenticated": False,
                "preferred_username": None,
                "email": None,
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
