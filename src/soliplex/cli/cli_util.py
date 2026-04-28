from __future__ import annotations

import pathlib

import typer
from rich import console

from soliplex import installation
from soliplex.config import installation as config_installation

the_console = console.Console()


def get_installation(
    installation_path: pathlib.Path,
    auditing: bool = False,
) -> installation.Installation:

    if installation_path.is_dir():
        installation_path = installation_path / "installation.yaml"
    i_config = config_installation.load_installation(installation_path)

    try:
        i_config.reload_configurations()
    except config_installation.MissingEnvVars:
        if not auditing:
            raise

    return installation.Installation(i_config)


def _check_ram_dburi(dburi: str, command: str):
    if dburi == config_installation.SYNC_MEMORY_ENGINE_URL:
        the_console.rule("Authorization DB is RAM-based")
        the_console.print(f"'{command}' is a no-op with a RAM-based database")
        raise typer.Exit(1)
