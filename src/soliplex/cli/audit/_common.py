from __future__ import annotations

import sys
import warnings

import typer

from soliplex import installation
from soliplex.cli import cli_util
from soliplex.cli import types

the_console = cli_util.the_console


def _noop(*args, **kwargs):  # pragma: NO COVER
    return None


def _quiet_console_funcs(quiet):
    """Return ``(line, rule, print, print_exception)`` callables.

    When ``quiet`` is true the returned callables are no-ops, suppressing
    human-focused output.
    """
    if quiet:
        return _noop, _noop, _noop, _noop
    return (
        the_console.line,
        the_console.rule,
        the_console.print,
        the_console.print_exception,
    )


def _emit_errors(errors, quiet):
    """Emit a JSON error report (in quiet mode) and exit ``1`` if any."""
    if errors:
        if quiet:
            the_console.print_json(data=errors)
        sys.exit(1)


def _get_installation(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
) -> installation.Installation:
    """Load the installation once per invocation, caching on ``ctx.obj``.

    Every warning raised while loading is recorded under
    ``ctx.obj["config_warnings"]``.
    """
    cached = ctx.obj.get("the_installation")
    if cached is None:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            cached = cli_util.get_installation(
                installation_path, auditing=True
            )
        ctx.obj["the_installation"] = cached
        ctx.obj["config_warnings"] = caught
    return cached
