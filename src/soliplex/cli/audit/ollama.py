from __future__ import annotations

import requests
import typer

from soliplex import installation
from soliplex import ollama
from soliplex.cli import types
from soliplex.cli.audit import _common as audit_common

_OLLAMA_PROBE_BY_ROLE = {
    installation.ProviderRole.CHAT: "chat_completion",
    installation.ProviderRole.EMBEDDING: "embeddings",
    installation.ProviderRole.RERANKING: None,  # no Ollama endpoint
}


def _unresponsive_ollama_models(rest_api, models) -> dict:
    """Return ``{model_name: error}`` for models that fail to respond.

    ``models`` maps each name (already present on the server) to the
    ``ProviderRole`` the installation gives it, and thus the endpoint used:

    - a chat model answers on ``/v1/chat/completions``
    - an embedding model answers on ``/v1/embeddings``.

    Probing either on the other's endpoint would report a healthy model
    as broken.

    Records the models raising a network error or non-2xx response; the
    result is empty when every model responds.
    """
    unresponsive: dict[str, str] = {}

    for model_name, role in sorted(models.items()):
        probe_name = _OLLAMA_PROBE_BY_ROLE.get(role)

        if probe_name is not None:
            # reranking, etc. cannot be probed on Ollama
            try:
                getattr(rest_api, probe_name)(model_name)
            except requests.RequestException as exc:
                unresponsive[model_name] = str(exc.args)

    return unresponsive


def _missing_ollama_models(
    the_installation: installation.Installation,
    *,
    check_responsive: bool = False,
) -> dict:
    """Return per-URL info about Ollama models on each server.

    Each value may carry ``{"unreachable": str}`` (the server refused
    the connection or returned an HTTP error), ``{"missing_models":
    [str, ...]}`` (the server is reachable but missing one or more
    models the installation references), and -- when ``check_responsive``
    is set -- ``{"unresponsive_models": {name: error}}`` (a model is
    installed but failed to answer a minimal request on the endpoint
    suiting its configured role).
    """
    ollama_url_models = the_installation.all_provider_info.get("ollama", {})
    per_url: dict[str, dict] = {}

    for url, required in ollama_url_models.items():
        if not required:
            continue

        rest_api = ollama.REST_API(url)

        try:
            response = rest_api.get_available_models()
        except requests.RequestException as exc:
            per_url[url] = {"unreachable": str(exc.args)}
            continue

        available = {entry["name"] for entry in response.get("models", ())}
        missing = sorted(required.keys() - available)

        url_info: dict = {}
        if missing:
            url_info["missing_models"] = missing

        if check_responsive:
            installed = {
                model_name: role
                for model_name, role in required.items()
                if model_name in available
            }
            unresponsive = _unresponsive_ollama_models(rest_api, installed)
            if unresponsive:
                url_info["unresponsive_models"] = unresponsive

        if url_info:
            per_url[url] = url_info

    if per_url:
        return {"ollama": per_url}
    return {}


def _audit_ollama_section(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
    *,
    check_responsive: bool = False,
) -> dict:  # pragma NO COVER UI ONLY
    """Print the Ollama section (rule header + per-URL availability check)."""
    quiet = ctx.obj["quiet"]
    the_installation = audit_common._get_installation(ctx, installation_path)
    tc_line, tc_rule, tc_print, _ = audit_common._quiet_console_funcs(quiet)

    tc_line()
    tc_rule("Configured Ollama URLs")
    tc_line()

    ollama_url_models = the_installation.all_provider_info.get("ollama", {})
    errors = _missing_ollama_models(
        the_installation,
        check_responsive=check_responsive,
    )
    per_url = errors.get("ollama", {})

    if not ollama_url_models:
        tc_print("No Ollama URLs referenced by the installation.")
        tc_line()
        return errors

    for url in sorted(ollama_url_models):
        tc_print(f"- {url}")
        url_errors = per_url.get(url, {})
        unreachable = url_errors.get("unreachable")
        missing = url_errors.get("missing_models")
        unresponsive = url_errors.get("unresponsive_models")
        if unreachable is not None:
            tc_print(f"  ERROR: {unreachable}")
        else:
            if missing:
                tc_print(f"  MISSING: {', '.join(missing)}")
                tc_print(
                    "  Run 'soliplex-cli ollama pull' to pull missing models.",
                )
            if unresponsive:
                tc_print(
                    f"  UNRESPONSIVE: {', '.join(sorted(unresponsive))}",
                )
                for model_name in sorted(unresponsive):
                    tc_print(f"    - {model_name}: {unresponsive[model_name]}")
            if not missing and not unresponsive:
                tc_print("  OK")
        tc_line()

    return errors


def audit_ollama(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
    check_responsive: bool = typer.Option(
        False,
        "-r",
        "--check-responsive",
        help=(
            "Also confirm each installed model answers a minimal "
            "request on the endpoint suiting its role (slower; "
            "contacts each model)"
        ),
    ),
):  # pragma NO COVER command
    """Compare configured Ollama models against each server's available set"""
    quiet = ctx.obj["quiet"]
    errors = _audit_ollama_section(
        ctx,
        installation_path,
        check_responsive=check_responsive,
    )
    audit_common._emit_errors(errors, quiet)
