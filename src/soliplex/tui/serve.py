import typer
from textual_serve import server as server_module

the_cli = typer.Typer(
    context_settings={
        "help_option_names": ["-h", "--help"],
    },
    # no_args_is_help=True,
    add_completion=False,
)


BACKEND_URL = typer.Option(
    "http://127.0.0.1:8000",
    "--backend-url",
    help="Base URL for Soliplex back-end",
)

HOST = typer.Option(
    "127.0.0.1",
    "--host",
    help="Hostname on which the server runs",
)

PORT = typer.Option(
    8002,
    "--port",
    help="Port on which the server runs",
)

PUBLIC_URL = typer.Option(
    None,
    "--public-url",
    help=(
        "Publically-reachable URL of the served HTML "
        "(defaults to 'http://{host}:{port}')"
    ),
)


@the_cli.command()
def app(
    soliplex_url: str = BACKEND_URL,
    host: str = HOST,
    port: int = PORT,
    public_url: str = PUBLIC_URL,
):
    """soliplex TUI server"""
    server = server_module.Server(
        f"soliplex-tui --url {soliplex_url}",
        host=host,
        port=port,
        public_url=public_url,
    )
    server.serve()


if __name__ == "__main__":
    the_cli()
