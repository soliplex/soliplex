from __future__ import annotations

import requests
import typer

from soliplex import ollama
from soliplex.cli import cli_util
from soliplex.cli import types

app = typer.Typer(
    name="ollama",
    help="List / manage Ollama models for the installation",
)
the_console = cli_util.the_console


@app.command("pull")
def pull_models(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
    ollama_url: str = typer.Option(
        None,
        "-u",
        "--ollama-url",
        help=(
            "Ollama API base URL (defaults to 'OLLAMA_BASE_URL' from "
            "installation enviroment)"
        ),
    ),
    dry_run: bool = typer.Option(
        False,
        "-n",
        "--dry-run",
        help="Show which models would be pulled without actually pulling them",
    ),
):
    """Pull Ollama models referenced in the installation configuration"""

    def on_status(msg, is_error=False):
        style = "red" if is_error else None
        the_console.print(f"  {msg}", style=style)

    the_console.line()
    the_console.rule("Scanning for Ollama models")
    the_console.line()

    the_installation = cli_util.get_installation(installation_path)
    the_installation.resolve_environment()
    all_provider_info = the_installation.all_provider_info
    ollama_url_models = all_provider_info["ollama"]

    if ollama_url is not None:
        ollama_url_models = {
            ollama_url: ollama_url_models.get(ollama_url, set())
        }

    for url, model_names in ollama_url_models.items():
        if not model_names:
            the_console.rule(f"No Ollama models for URL: {url}")
            the_console.line()

        else:
            rest_api = ollama.REST_API(url)

            the_console.rule(f"Pulling Ollama models for URL: {url}")
            the_console.line()
            the_console.print(
                f"Found {len(model_names)} unique Ollama model(s)"
            )
            the_console.line()

            for model_name in sorted(model_names):
                the_console.print(f"  - {model_name}")

            if not dry_run:
                success_count = 0

                for model_name in sorted(model_names):
                    the_console.print(f"\nPulling: {model_name}")

                    try:
                        result = rest_api.pull_model(model_name, stream=False)
                        status_text = result["status"]
                    except requests.RequestException as exc:
                        on_status(str(exc.args), True)
                    except KeyError:
                        on_status("No status returned", True)
                    else:
                        on_status(status_text, False)
                        success_count += 1

                the_console.line()
                the_console.rule(
                    f"Pulled {success_count}/{len(model_names)} model(s) "
                    "successfully"
                )
                the_console.line()
