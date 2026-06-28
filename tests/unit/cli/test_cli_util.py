from __future__ import annotations

import contextlib
from unittest import mock

import pytest
import typer

from soliplex import authz
from soliplex import installation
from soliplex.cli import cli_util
from soliplex.config import installation as config_installation

no_error_none = contextlib.nullcontext()

TESTCASE_ID = "testcase-id"

BARE_INSTALLATION_CONFIG = f"""
id: {TESTCASE_ID}
oidc_paths:
  -
"""

BAD_ENV_VAR = """
environment:
  - "NONESUCH_VAR"
"""


@pytest.fixture
def haiku_rag_yaml(tmp_path):
    yaml_file = tmp_path / "haiku.rag.yaml"
    yaml_file.write_text(f"id: {TESTCASE_ID}")

    return yaml_file


@pytest.fixture
def installation_yaml(tmp_path, haiku_rag_yaml):  # , oidc_config_yaml):
    yaml_file = tmp_path / "installation.yaml"
    yaml_file.write_text(BARE_INSTALLATION_CONFIG)

    return yaml_file


@pytest.mark.parametrize(
    "w_append_text, would_raise",
    [
        ("", False),
        (BAD_ENV_VAR, True),
    ],
)
@pytest.mark.parametrize("w_auditing", [None, False, True])
@pytest.mark.parametrize("w_dir", [False, True])
def test_get_installation(
    installation_yaml,
    w_dir,
    w_auditing,
    w_append_text,
    would_raise,
):
    installation_yaml.write_text(
        "\n".join([BARE_INSTALLATION_CONFIG, w_append_text])
    )
    w_auditing_kw = {}

    if w_auditing is not None:
        w_auditing_kw["auditing"] = w_auditing

    if not would_raise or w_auditing:
        expectation = no_error_none
    else:
        expectation = pytest.raises(config_installation.MissingEnvVars)

    if w_dir:
        installation_path = installation_yaml.parent
    else:
        installation_path = installation_yaml

    with expectation as expected:
        found = cli_util.get_installation(installation_path, **w_auditing_kw)

    if expected is None:
        assert isinstance(found, installation.Installation)


@pytest.mark.parametrize(
    "dburi, expectation",
    [
        ("pgsql:db.example.com@/dbname", no_error_none),
        (
            config_installation.SYNC_MEMORY_ENGINE_URL,
            pytest.raises(typer.Exit),
        ),
        (
            config_installation.ASYNC_MEMORY_ENGINE_URL,
            pytest.raises(typer.Exit),
        ),
    ],
)
@mock.patch("soliplex.cli.cli_util.the_console")
def test__check_ram_dburi(the_console, dburi, expectation):

    with expectation as expected:
        cli_util._check_ram_dburi(dburi, "test-command")

    if expected is not None:
        (return_code,) = expected.value.args
        assert return_code == 1
        the_console.rule.assert_called_once_with(
            "Authorization DB is RAM-based",
        )
        the_console.print.assert_called_once_with(
            "'test-command' is a no-op with a RAM-based database",
        )


@pytest.mark.anyio
async def test__admin_user_policy(tmp_path):
    db_path = tmp_path / "authz.sqlite"
    dburi = f"sqlite+aiosqlite:///{db_path}"
    json_path = authz.token_field_json_path("email", "alice@example.com")

    async with cli_util._admin_user_policy(dburi) as policy:
        await policy.add_admin_user_discriminator(json_path)
        found = await policy.list_admin_user_discriminators()

    assert found == [json_path]


@pytest.mark.anyio
async def test__room_authz_policy(tmp_path):
    db_path = tmp_path / "authz.sqlite"
    dburi = f"sqlite+aiosqlite:///{db_path}"

    async with cli_util._room_authz_policy(dburi) as policy:
        await policy.set_room_default("faux", authz.AllowDeny.DENY)
        found = await policy.list_room_policies()

    assert [p.room_id for p in found] == ["faux"]


def test__audit_claims_uses_env_actor(monkeypatch):
    monkeypatch.setenv("SOLIPLEX_AUDIT_ACTOR", "ops@example.com")

    claims = cli_util._audit_claims()

    assert claims == {"source": "cli", "actor": "ops@example.com"}


def test__audit_claims_falls_back_to_os_user(monkeypatch):
    monkeypatch.delenv("SOLIPLEX_AUDIT_ACTOR", raising=False)
    monkeypatch.setattr(cli_util.getpass, "getuser", lambda: "phreddy")

    claims = cli_util._audit_claims()

    assert claims == {"source": "cli", "actor": "phreddy"}


SUMMARY = "'--a', '--b', or '--c'"


@pytest.mark.parametrize(
    "w_discriminators",
    [
        [("--a", True), ("--b", False), ("--c", False)],
        [("--a", False), ("--b", True), ("--c", False)],
        [("--a", False), ("--b", False), ("--c", True)],
    ],
)
@mock.patch("soliplex.cli.cli_util.the_console")
def test__check_exactly_one_discriminator_accepts_one(
    the_console, w_discriminators
):
    cli_util._check_exactly_one_discriminator(w_discriminators, SUMMARY)

    the_console.rule.assert_not_called()
    the_console.print.assert_not_called()


@pytest.mark.parametrize(
    "w_discriminators, exp_selected",
    [
        # None set -> error reports '(none)'.
        (
            [("--a", False), ("--b", False), ("--c", False)],
            ["(none)"],
        ),
        # Two set.
        (
            [("--a", True), ("--b", True), ("--c", False)],
            ["--a", "--b"],
        ),
        # All set.
        (
            [("--a", True), ("--b", True), ("--c", True)],
            ["--a", "--b", "--c"],
        ),
    ],
)
@mock.patch("soliplex.cli.cli_util.the_console")
def test__check_exactly_one_discriminator_rejects_other_arities(
    the_console, w_discriminators, exp_selected
):
    with pytest.raises(typer.Exit) as excinfo:
        cli_util._check_exactly_one_discriminator(w_discriminators, SUMMARY)

    (return_code,) = excinfo.value.args
    assert return_code == 1

    the_console.rule.assert_called_once_with(
        "Exactly one discriminator required",
    )
    the_console.print.assert_called_once_with(
        f"Pass exactly one of {SUMMARY}. Got: {exp_selected}.",
    )


@pytest.mark.parametrize(
    "w_json_path, w_preferred_username, w_email, exp",
    [
        # No claim shortcut, no json_path -> None passes through.
        (None, None, None, None),
        # A literal json_path passes through unchanged.
        ("$.foo", None, None, "$.foo"),
        # 'preferred_username' is translated to the canonical form.
        (None, "alice", None, '$[?$.preferred_username == "alice"]'),
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
def test__resolve_json_path(w_json_path, w_preferred_username, w_email, exp):
    found = cli_util._resolve_json_path(
        mock.sentinel.the_installation,
        w_json_path,
        w_preferred_username,
        w_email,
    )

    assert found == exp


@mock.patch("soliplex.cli.cli_util.the_console")
def test__resolve_json_path_invalid_raises(the_console):
    bogus = "$[?this is not a query]"

    with pytest.raises(typer.Exit) as excinfo:
        cli_util._resolve_json_path(
            mock.sentinel.the_installation, bogus, None, None
        )

    (return_code,) = excinfo.value.args
    assert return_code == 1

    the_console.rule.assert_called_once_with("Invalid JSONPath")
    (print_args, _) = the_console.print.call_args
    (printed,) = print_args
    assert bogus in printed


def test__resolve_json_path_allow_invalid_skips_validation():
    bogus = "$[?stale_filter_func($.email)]"

    found = cli_util._resolve_json_path(
        mock.sentinel.the_installation,
        bogus,
        None,
        None,
        allow_invalid=True,
    )

    assert found == bogus


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
    with pytest.raises(authz.InvalidJSONPath):
        authz.validate_json_path(json_path)

    authz.register_jsonpath_function("filter_func", filter_func)

    found = cli_util._resolve_json_path(
        mock.sentinel.the_installation,
        json_path,
        None,
        None,
    )

    assert found == json_path
    assert patched_jsonpath_functions["filter_func"] is filter_func
