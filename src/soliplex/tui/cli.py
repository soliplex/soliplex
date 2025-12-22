from importlib.metadata import version

import typer
from rich import console

from soliplex.tui import main

the_cli = typer.Typer(
    context_settings={
        "help_option_names": ["-h", "--help"],
    },
    # no_args_is_help=True,
)

the_console = console.Console()


def get_version():
    v = version("soliplex-tui")
    the_console.print(f"soliplex-tui version {v}")
    raise typer.Exit()


def version_callback(value: bool):
    if value:
        get_version()


BASE_URL = typer.Option(
    "http://127.0.0.1:8000",
    "--url",
    help="Base URL for Soliplex back-end",
)
ROOM = typer.Option("haiku", "-r", "--room", help="Room name for the agent")


@the_cli.command()
def tui(
    version: bool = typer.Option(None, "--version", "-v"),
    soliplex_url: str = BASE_URL,
    room_id: str = ROOM,
):
    tui_app = main.SoliplexTUI(soliplex_url, room_id)

    tui_app.run()
