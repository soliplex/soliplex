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


ollama_url_option: list[str] = typer.Option(
    [],
    "-u",
    "--ollama-url",
    help=(
        "Restrict the pull to one or more Ollama API base URLs "
        "referenced by the installation (repeatable; defaults to "
        "scanning every Ollama URL the installation references)"
    ),
)


class UnknownOllamaURLs(Exception):
    """Raised when '--ollama-url' names URLs the installation does not
    reference.
    """

    def __init__(self, unknown_urls):
        self.unknown_urls = list(unknown_urls)
        super().__init__(
            "URL(s) not referenced by installation: "
            f"{', '.join(self.unknown_urls)}"
        )


def _filter_ollama_url_models(ollama_url_models, ollama_urls):
    """Restrict 'ollama_url_models' to 'ollama_urls' if any are supplied.

    Raises 'UnknownOllamaURLs' if any of 'ollama_urls' is not referenced
    by the installation.
    """
    if not ollama_urls:
        return ollama_url_models

    unknown = [url for url in ollama_urls if url not in ollama_url_models]

    if unknown:
        raise UnknownOllamaURLs(unknown)

    return {url: ollama_url_models[url] for url in ollama_urls}


@app.command("pull")
def pull_models(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
    ollama_urls: list[str] = ollama_url_option,
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
    all_ollama_url_models = all_provider_info["ollama"]

    try:
        ollama_url_models = _filter_ollama_url_models(
            all_ollama_url_models,
            ollama_urls,
        )
    except UnknownOllamaURLs as exc:
        the_console.rule(str(exc))
        configured = sorted(all_ollama_url_models)
        if configured:
            the_console.print(
                f"Configured Ollama URLs: {', '.join(configured)}",
            )
        else:
            the_console.print(
                "The installation references no Ollama URLs.",
            )
        raise typer.Exit(1) from exc

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
