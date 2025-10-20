from importlib.metadata import version

import textual
import typer
from rich import console

from soliplex.tui import main

the_cli = typer.Typer(
    context_settings={
        "help_option_names": ["-h", "--help"],
    },
    #no_args_is_help=True,
)

the_console = console.Console()


def get_version():
    v = version("soliplex-tui")
    the_console.print(f"soliple-tui version {v}")
    raise typer.Exit()

def version_callback(value: bool):
    if value:
        get_version()



@the_cli.command()
def tui(
    version: bool = typer.Option(None, "--version", "-v"),
    soliplex_url: str = typer.Option("http://localhost:8000", "--url"),
    room_id: str = typer.Option("haiku", "-r", "--room-id"),
):
    tui_app = main.SoliplexTUI(soliplex_url, room_id)

    tui_app.run()
