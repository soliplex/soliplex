"""Mint and validate service tokens

A service token lets a client (e.g., 'curl', or an operator's script)
authenticate to the Soliplex API without an OIDC login:  it is passed as
the bearer token, and carries the claims given when it was minted, plus
its expiry time.  The token is signed with the installation's
'URL_SAFE_TOKEN_SECRET', so the server must resolve that secret to the
same value as the CLI does:  the command refuses to mint a token signed
with a secret resolved from a 'random_chars' source.

'mint' writes the token to a file, or to stdout;  'validate' reads a token
from a file, or from stdin, and writes its claims to a file, or to stdout.
Everything else either command reports goes to stderr, so that a script can
capture the token, or the claims, alone.
"""

from __future__ import annotations

import datetime
import json
import os
import pathlib
import re
import sys
import typing

import typer
import yaml
from rich import console

from soliplex import authn
from soliplex import secrets
from soliplex import token_mint
from soliplex.cli import cli_util
from soliplex.cli import types
from soliplex.config import secrets as config_secrets

the_console = console.Console(stderr=True)

STDIN_INPUT = pathlib.Path("-")
STDOUT_OUTPUT = pathlib.Path("-")
YAML_SUFFIXES = (".yaml", ".yml")

SERVICE_TOKEN_HELP = "Mint and validate service tokens for API clients"

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


class ClaimsSourceConflict(typer.BadParameter):
    def __init__(self):
        super().__init__(
            "give exactly one of '--claims' or '--input'",
            param_hint="'--claims' / '--input'",
        )


class InvalidClaimsFile(typer.BadParameter):
    def __init__(self, path: pathlib.Path, file_format: str, reason: str):
        self.path = path
        self.file_format = file_format
        self.reason = reason
        super().__init__(
            f"invalid {file_format} ({reason}): {path}",
            param_hint="'-i' / '--input'",
        )


class ClaimsFileNotAnObject(typer.BadParameter):
    def __init__(self, path: pathlib.Path):
        self.path = path
        super().__init__(
            f"expected a mapping / object: {path}",
            param_hint="'-i' / '--input'",
        )


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


def load_claims_file(path: pathlib.Path) -> dict:
    """Return the claims in the file at 'path'

    The file holds YAML if its extension is one of 'YAML_SUFFIXES' (in
    any case), else JSON.

    Raises:

    - 'InvalidClaimsFile' if the file does not parse.
    - 'ClaimsFileNotAnObject' if the file parses, but not as a mapping.
    """
    text = path.read_text(encoding="utf-8")

    if path.suffix.lower() in YAML_SUFFIXES:
        try:
            claims = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise InvalidClaimsFile(path, "YAML", str(exc)) from None
    else:
        try:
            claims = json.loads(text)
        except json.JSONDecodeError as exc:
            raise InvalidClaimsFile(path, "JSON", exc.msg) from None

    if not isinstance(claims, dict):
        raise ClaimsFileNotAnObject(path)

    return claims


def drop_reserved_claims(claims: dict) -> tuple[dict, list[str]]:
    """Return 'claims' without any 'SERVICE_TOKEN_RESERVED_CLAIMS'

    Returns '(kept, dropped)':  'dropped' names the reserved claims
    which 'claims' held.
    """
    reserved = token_mint.SERVICE_TOKEN_RESERVED_CLAIMS
    dropped = [claim for claim in reserved if claim in claims]
    kept = {key: value for key, value in claims.items() if key not in reserved}
    return kept, dropped


claims_type = typing.Annotated[
    dict | None,
    typer.Option(
        "--claims",
        parser=parse_claims,
        help=(
            "Claims for the token, as a JSON object, e.g. "
            '\'{"preferred_username": "ops"}\'.  If it has no "sub", '
            'the token\'s "sub" is a random UUID.  Exclusive with '
            "'--input'."
        ),
    ),
]

claims_input_type = typing.Annotated[
    pathlib.Path | None,
    typer.Option(
        "-i",
        "--input",
        exists=True,
        dir_okay=False,
        readable=True,
        help=(
            "File from which the claims are read:  as YAML if its "
            "extension is '.yaml' or '.yml', else as JSON.  Any 'iat' or "
            "'exp' claims in it are dropped.  Exclusive with '--claims'."
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

input_type = typing.Annotated[
    pathlib.Path,
    typer.Option(
        "-i",
        "--input",
        exists=True,
        dir_okay=False,
        readable=True,
        allow_dash=True,
        help=(
            "File from which the token is read;  if '-' (the default), "
            "the token is read from stdin."
        ),
    ),
]

claims_output_type = typing.Annotated[
    pathlib.Path,
    typer.Option(
        "-o",
        "--output",
        help=(
            "File to which the claims are written:  as YAML if its "
            "extension is '.yaml' or '.yml', else as JSON.  If '-' (the "
            "default), the claims are written to stdout, as JSON."
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


def _resolve_stable_secret(
    secret_config: config_secrets.SecretConfig,
) -> str | None:
    """Return the secret's value, if resolved before any 'random_chars' source

    Tries the secret's sources in order, as the server does, stopping at
    the first 'random_chars' source.  Returns 'None' if none of the sources
    tried resolves the secret.
    """
    stable_sources = []

    for source in secret_config.sources:
        if source.kind == config_secrets.RandomCharsSecretSource.kind:
            break
        stable_sources.append(source)

    if not stable_sources:
        return None

    trial = config_secrets.SecretConfig(
        secret_name=secret_config.secret_name,
        sources=stable_sources,
    )

    try:
        return config_secrets.get_secret(trial)
    except secrets.SecretSourcesFailed:
        return None


def _get_stable_secret(installation_path: pathlib.Path) -> str:
    """Return the installation's stable service token secret

    Raises 'typer.Exit(1)' if the secret resolves only from its
    'random_chars' source.
    """
    the_installation = cli_util.get_installation(installation_path)
    secret_name = authn.SERVICE_TOKEN_SECRET_NAME
    secret = _resolve_stable_secret(
        the_installation._config.secrets_map[secret_name]
    )

    if secret is None:
        the_console.rule("No stable secret")
        the_console.print(
            f"'{secret_name}' resolves only from its 'random_chars' "
            "source, so the server would not verify the token:  configure "
            "it from an 'env_var', 'file_path', or 'subprocess' source."
        )
        raise typer.Exit(1)

    return secret


def _write_output(output: pathlib.Path, content: str, *, force: bool):
    """Write 'content' to a new file at 'output', readable only by its owner

    With 'force', an existing file at 'output' is replaced.

    Raises 'FileExistsError' if 'output' exists and 'force' is false.
    """
    if force:
        output.unlink(missing_ok=True)

    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)

    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        stream.write(content)


def _emit(output: pathlib.Path, content: str, *, force: bool):
    """Write 'content' to 'output', or to stdout if 'output' is '-'

    Raises 'typer.Exit(1)' if 'output' exists and 'force' is false.
    """
    if output == STDOUT_OUTPUT:
        typer.echo(content, nl=False)
        return

    try:
        _write_output(output, content, force=force)
    except FileExistsError:
        the_console.rule("Output file exists")
        the_console.print(f"Pass '--force' to replace {output}.")
        raise typer.Exit(1) from None


def _read_token(input_path: pathlib.Path) -> str:
    """Return the token read from 'input_path', or from stdin if it is '-'"""
    if input_path == STDIN_INPUT:
        text = sys.stdin.read()
    else:
        text = input_path.read_text(encoding="utf-8")

    return text.strip()


def _format_claims(
    claims: token_mint.ServiceTokenClaims,
    output: pathlib.Path,
) -> str:
    """Return 'claims' rendered as a document for 'output'

    YAML if the extension of 'output' is one of 'YAML_SUFFIXES' (in any
    case), else JSON.
    """
    if output.suffix.lower() in YAML_SUFFIXES:
        return yaml.safe_dump(
            claims,
            sort_keys=False,
            default_flow_style=False,
        )

    return json.dumps(claims, indent=2) + "\n"


def _print_summary(
    title: str,
    claims: token_mint.ServiceTokenClaims,
    output: pathlib.Path,
):
    expires = datetime.datetime.fromtimestamp(claims["exp"], datetime.UTC)

    the_console.rule(title)
    if output != STDOUT_OUTPUT:
        the_console.print(f"Written to: {output}")
    the_console.print(f"Subject:    {claims['sub']}")
    the_console.print(f"Expires:    {expires.isoformat()}")


@app.command("mint")
def mint_service_token(
    installation_path: types.installation_path_type,
    expires_in: expires_in_type,
    claims: claims_type = None,
    claims_input: claims_input_type = None,
    output: output_type = STDOUT_OUTPUT,
    force: force_type = False,
    quiet: quiet_type = False,
):
    """Mint a service token, and write it to a file or to stdout"""
    if (claims is None) == (claims_input is None):
        raise ClaimsSourceConflict()

    if claims_input is not None:
        claims, dropped = drop_reserved_claims(load_claims_file(claims_input))

        if dropped and not quiet:
            the_console.print(
                f"Dropped from {claims_input}: {', '.join(dropped)}"
            )

    secret = _get_stable_secret(installation_path)

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

    _emit(output, f"{token}\n", force=force)

    if quiet:
        return

    minted, _ = token_mint.load_service_token(secret, token)
    _print_summary("Service token minted", minted, output)


@app.command("validate")
def validate_service_token(
    installation_path: types.installation_path_type,
    input_path: input_type = str(STDIN_INPUT),
    output: claims_output_type = STDOUT_OUTPUT,
    force: force_type = False,
    quiet: quiet_type = False,
):
    """Validate a service token, and write its claims to a file or stdout"""
    secret = _get_stable_secret(installation_path)
    token = _read_token(input_path)

    claims, reason = token_mint.load_service_token(secret, token)

    if claims is None:
        the_console.rule("Invalid service token")
        the_console.print(reason)
        raise typer.Exit(1)

    _emit(output, _format_claims(claims, output), force=force)

    if quiet:
        return

    _print_summary("Service token valid", claims, output)
