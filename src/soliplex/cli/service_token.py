"""Mint service tokens

A service token lets a client (e.g., 'curl', or an operator's script)
authenticate to the Soliplex API without an OIDC login:  it is passed as
the bearer token, and carries the claims given when it was minted, plus
its expiry time.  The token is signed with the installation's
'URL_SAFE_TOKEN_SECRET', so the server must resolve that secret to the
same value as the CLI does.

The token is written to a file, or to stdout;  everything else the command
reports goes to stderr, so that a script can capture the token alone.
"""

from __future__ import annotations

import datetime
import json
import os
import pathlib
import re
import typing

import typer
from rich import console

from soliplex import authn
from soliplex import token_mint
from soliplex.cli import cli_util
from soliplex.cli import types

the_console = console.Console(stderr=True)

STDOUT_OUTPUT = pathlib.Path("-")

SERVICE_TOKEN_HELP = "Mint service tokens for API clients"

app = typer.Typer(
    name="service-token",
    help=SERVICE_TOKEN_HELP,
    no_args_is_help=True,
)

DURATION_UNITS = {
    "s": 1,
    "m": 60,
    "h": 60 * 60,
    "d": 24 * 60 * 60,
    "w": 7 * 24 * 60 * 60,
}
_DURATION_RE = re.compile(r"(?P<count>\d+)(?P<unit>[smhdw])")


class InvalidDuration(typer.BadParameter):
    def __init__(self, value: str):
        self.value = value
        units = ", ".join(DURATION_UNITS)
        super().__init__(
            f"expected an integer followed by one of {units}: {value!r}"
        )


class InvalidClaimsJSON(typer.BadParameter):
    def __init__(self, value: str, reason: str):
        self.value = value
        self.reason = reason
        super().__init__(f"invalid JSON ({reason}): {value!r}")


class ClaimsNotAnObject(typer.BadParameter):
    def __init__(self, value: str):
        self.value = value
        super().__init__(f"expected a JSON object: {value!r}")


def parse_duration(value: str) -> int:
    """Return the number of seconds in 'value', e.g. '15m' or '90d'

    Raises 'InvalidDuration' unless 'value' is an integer followed by
    one of the units in 'DURATION_UNITS'.
    """
    match = _DURATION_RE.fullmatch(value)

    if match is None:
        raise InvalidDuration(value)

    return int(match.group("count")) * DURATION_UNITS[match.group("unit")]


def parse_claims(value: str) -> dict:
    """Return the JSON object in 'value'

    Raises:

    - 'InvalidClaimsJSON' if 'value' is not valid JSON.
    - 'ClaimsNotAnObject' if 'value' is JSON, but not an object.
    """
    try:
        claims = json.loads(value)
    except json.JSONDecodeError as exc:
        raise InvalidClaimsJSON(value, exc.msg) from None

    if not isinstance(claims, dict):
        raise ClaimsNotAnObject(value)

    return claims


claims_type = typing.Annotated[
    dict,
    typer.Option(
        "--claims",
        parser=parse_claims,
        help=(
            "Claims for the token, as a JSON object, e.g. "
            '\'{"preferred_username": "ops"}\'.  If it has no "sub", '
            'the token\'s "sub" is a random UUID.'
        ),
    ),
]

expires_in_type = typing.Annotated[
    int,
    typer.Option(
        "--expires-in",
        parser=parse_duration,
        help=(
            "Lifetime of the token:  an integer followed by a unit, one of "
            "'s', 'm', 'h', 'd', or 'w', e.g. '15m' or '90d'."
        ),
    ),
]

output_type = typing.Annotated[
    pathlib.Path,
    typer.Option(
        "-o",
        "--output",
        help=(
            "File to which the token is written;  if '-' (the default), "
            "the token is written to stdout."
        ),
    ),
]

force_type = typing.Annotated[
    bool,
    typer.Option(
        "--force",
        help="Replace the output file, if it exists",
    ),
]

quiet_type = typing.Annotated[
    bool,
    typer.Option(
        "-q",
        "--quiet",
        help="Report only errors",
    ),
]


def _write_token(output: pathlib.Path, token: str, *, force: bool):
    """Write 'token' to a new file at 'output', readable only by its owner

    With 'force', an existing file at 'output' is replaced.

    Raises 'FileExistsError' if 'output' exists and 'force' is false.
    """
    if force:
        output.unlink(missing_ok=True)

    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)

    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        stream.write(f"{token}\n")


@app.command("mint")
def mint_service_token(
    installation_path: types.installation_path_type,
    claims: claims_type,
    expires_in: expires_in_type,
    output: output_type = STDOUT_OUTPUT,
    force: force_type = False,
    quiet: quiet_type = False,
):
    """Mint a service token, and write it to a file or to stdout"""
    the_installation = cli_util.get_installation(installation_path)
    secret = the_installation.get_secret(authn.SERVICE_TOKEN_SECRET_NAME)

    try:
        token = token_mint.mint_service_token(
            secret,
            claims,
            expires_in=expires_in,
        )
    except token_mint.ServiceTokenError as exc:
        the_console.rule("Invalid service token")
        the_console.print(str(exc))
        raise typer.Exit(1) from None

    if output == STDOUT_OUTPUT:
        typer.echo(token)
    else:
        try:
            _write_token(output, token, force=force)
        except FileExistsError:
            the_console.rule("Output file exists")
            the_console.print(f"Pass '--force' to replace {output}.")
            raise typer.Exit(1) from None

    if quiet:
        return

    minted, _ = token_mint.load_service_token(secret, token)
    expires = datetime.datetime.fromtimestamp(minted["exp"], datetime.UTC)

    the_console.rule("Service token minted")
    if output != STDOUT_OUTPUT:
        the_console.print(f"Written to: {output}")
    the_console.print(f"Subject:    {minted['sub']}")
    the_console.print(f"Expires:    {expires.isoformat()}")
