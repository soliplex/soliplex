from __future__ import annotations

from unittest import mock

import pytest

from soliplex import authz
from soliplex import models
from soliplex.cli import cli_util
from soliplex.cli.audit import room_authz as audit_room_authz
from tests.unit.cli.audit import audit_helpers


@pytest.mark.anyio
@mock.patch("soliplex.cli.audit.room_authz.cli_util._room_authz_policy")
async def test__list_room_policies(authz_policy):
    # The helper is a pass-through; the return value emulates the
    # 'models.RoomPolicyUnchecked' shape 'list_room_policies' yields.
    policies = [
        {
            "room_id": "faux",
            "default_allow_deny": authz.AllowDeny.DENY,
            "acl_entries": [
                {
                    "allow_deny": authz.AllowDeny.ALLOW,
                    "everyone": False,
                    "authenticated": False,
                    "preferred_username": None,
                    "email": "alice@example.com",
                    "json_path": None,
                },
            ],
        },
    ]
    policy = mock.AsyncMock()
    policy.list_room_policies.return_value = policies
    authz_policy.return_value.__aenter__.return_value = policy

    found = await audit_room_authz._list_room_policies(
        mock.sentinel.installation
    )

    assert found == policies
    authz_policy.assert_called_once_with(
        mock.sentinel.installation,
        "audit room-authz",
        allow_ram=True,
        must_exist=True,
    )
    policy.list_room_policies.assert_awaited_once_with()


def test__room_policies_on_an_uncreated_database(the_installation, tmp_path):
    the_installation, db_path = audit_helpers.uncreated_installation(
        the_installation, tmp_path
    )

    found_policies, found_error = audit_room_authz._room_policies(
        the_installation
    )

    assert found_policies == []
    assert found_error is None
    # Reading is all an audit does: no schema was created.
    assert audit_helpers.tables(db_path) == set()


@pytest.mark.parametrize(
    "policies, exc, exp_policies, exp_error",
    [
        # A database nothing has created -- an in-memory one included --
        # holds no policies, and that is not a finding.
        (None, cli_util.DatabaseNotCreated("authz"), [], None),
        # Created, with no stored rows.
        ([], None, [], None),
        # Stored rows pass through in the order they are read.
        (["p1", "p2"], None, ["p1", "p2"], None),
        # A database the driver cannot reach: reported, not raised.
        (
            None,
            audit_helpers.AuthzDBError(),
            [],
            audit_helpers.EXP_AUTHZ_DB_ERROR,
        ),
    ],
)
@mock.patch("soliplex.cli.audit.room_authz._list_room_policies")
def test__room_policies(
    list_room_policies,
    the_installation,
    policies,
    exc,
    exp_policies,
    exp_error,
):
    # The helper is a pass-through, so opaque stand-ins stand in for the
    # 'models.RoomPolicyUnchecked' instances the policy yields.
    if exc is not None:
        list_room_policies.side_effect = exc
    else:
        list_room_policies.return_value = policies

    found_policies, found_error = audit_room_authz._room_policies(
        the_installation
    )

    assert found_policies == exp_policies
    assert found_error == exp_error
    list_room_policies.assert_called_once_with(the_installation)


@pytest.mark.parametrize(
    "configured_rooms, policy_specs, exp_groups",
    [
        # Empty configuration + empty DB.
        ([], [], {"default": [], "public": [], "private": [], "stale": []}),
        # Configured rooms but no DB rows -> all default.
        (
            ["alpha", "beta"],
            [],
            {
                "default": ["alpha", "beta"],
                "public": [],
                "private": [],
                "stale": [],
            },
        ),
        # Only DB rows for unconfigured rooms -> all stale.
        (
            [],
            [("old", "ALLOW"), ("removed", "DENY")],
            {
                "default": [],
                "public": [],
                "private": [],
                "stale": ["old", "removed"],
            },
        ),
        # Mixed: one row in each of the four buckets.
        (
            ["alpha", "beta", "gamma", "delta"],
            [
                ("beta", "ALLOW"),
                ("gamma", "DENY"),
                ("ghost", "DENY"),
            ],
            {
                "default": ["alpha", "delta"],
                "public": ["beta"],
                "private": ["gamma"],
                "stale": ["ghost"],
            },
        ),
    ],
)
def test__room_authz_groups(
    the_installation,
    configured_rooms,
    policy_specs,
    exp_groups,
):
    the_installation._config.room_configs = {
        rid: mock.Mock() for rid in configured_rooms
    }
    room_policies = [
        models.RoomPolicyUnchecked(
            room_id=room_id,
            default_allow_deny=(
                authz.AllowDeny.ALLOW
                if allow_deny == "ALLOW"
                else authz.AllowDeny.DENY
            ),
        )
        for room_id, allow_deny in policy_specs
    ]

    found = audit_room_authz._room_authz_groups(
        the_installation, room_policies
    )

    assert found == exp_groups


@pytest.mark.parametrize(
    "policy_specs, exp_invalid",
    [
        # No policies.
        ([], {}),
        # All entries valid.
        (
            [
                ("chat", [None, '$[?$.email == "alice@example.com"]']),
            ],
            {},
        ),
        # One invalid entry.
        (
            [
                ("chat", ["$[?missing_func($.email)]"]),
            ],
            {"chat": [("$[?missing_func($.email)]", "<error>")]},
        ),
        # Mix of valid and invalid across rooms.
        (
            [
                (
                    "chat",
                    [
                        '$[?$.email == "alice@example.com"]',
                        "$[?missing_func($.email)]",
                    ],
                ),
                ("search", [None]),
                ("ghost", ["$[?other_missing($.email)]"]),
            ],
            {
                "chat": [("$[?missing_func($.email)]", "<error>")],
                "ghost": [("$[?other_missing($.email)]", "<error>")],
            },
        ),
    ],
)
def test__invalid_acl_json_paths(policy_specs, exp_invalid):
    room_policies = [
        models.RoomPolicyUnchecked(
            room_id=room_id,
            acl_entries=[
                models.ACLEntryUnchecked(
                    allow_deny=authz.AllowDeny.DENY,
                    json_path=jp,
                )
                for jp in json_paths
            ],
        )
        for room_id, json_paths in policy_specs
    ]

    found = audit_room_authz._invalid_acl_json_paths(room_policies)

    # The error message is implementation-detail; normalize for compare.
    normalized = {
        room_id: [(jp, "<error>") for (jp, _err) in entries]
        for room_id, entries in found.items()
    }
    assert normalized == exp_invalid


# _audit_room_authz_section: ui only
# audit_room_authz: command
