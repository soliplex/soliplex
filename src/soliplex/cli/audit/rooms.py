from __future__ import annotations

import asyncio
import warnings

import typer
from haiku.rag import client as hr_client

from soliplex import installation
from soliplex import models
from soliplex.cli import types
from soliplex.cli.audit import _common as audit_common
from soliplex.cli.audit import interpolation as audit_interpolation
from soliplex.config import agui as config_agui
from soliplex.config import rag as config_rag


async def _async_count(rag):
    with warnings.catch_warnings():
        async with rag as rag_a:
            return await rag_a.count_documents()


def _count_rag_documents(rag: hr_client.HaikuRAG):
    """Return ``(display, error)`` for the RAG document count.

    On success, ``error`` is ``None``. On failure, ``error`` carries the
    exception message so the caller can record it in the audit report.
    """
    try:
        count = asyncio.run(_async_count(rag))
    except Exception as exc:
        return f"ERROR: {exc}", str(exc)

    return f"{count} documents", None


def _invalid_rooms(the_installation: installation.Installation) -> dict:
    errors: dict[str, str] = {}

    for room_config in the_installation._config.room_configs.values():
        try:
            models.Room.from_config(room_config)
        except Exception as exc:
            errors[room_config.id] = str(exc)

    if errors:
        return {"room": errors}
    return {}


def _iter_room_rag_candidates(room_config):
    """Yield ``(source_label, cfg)`` for each RAG-bearing sub-config."""
    if isinstance(room_config.agent_config, config_rag._RAGConfigBase):
        yield "agent", room_config.agent_config

    if room_config.skills is not None:
        for s_name, s_config in room_config.skills.skill_configs.items():
            if isinstance(s_config, config_rag._RAGConfigBase):
                yield f"skill:{s_name}", s_config

    for tool_config in room_config.tool_configs.values():
        if isinstance(tool_config, config_rag._RAGConfigBase):
            yield f"tool:{tool_config.tool_name}", tool_config


def _rag_db_probes(source, cfg):
    """Yield ``(label, cfg)`` for each database a config names.

    A probe checks a path this config places, so a config deferring
    placement to its haiku.rag config yields nothing: opening it for the
    document count is what checks it.  A candidate is only known to expose
    ``haiku_rag_config``, so one that cannot place a database at all yields
    itself and reports its own error from inside the caller's ``try``.
    """
    rag_databases = getattr(cfg, "rag_databases", None)

    if rag_databases:
        for entry in rag_databases:
            yield f"{source}#{entry.name}", entry
    elif getattr(cfg, "names_own_databases", True):
        yield source, cfg


def _invalid_room_agui_features(
    the_installation: installation.Installation,
) -> dict:
    feature_errors: dict[str, list[str]] = {}
    registry = config_agui.AGUI_FEATURES_BY_NAME

    for room_config in the_installation._config.room_configs.values():
        missing = [
            name
            for name in room_config.agui_feature_names
            if name not in registry
        ]
        if missing:
            feature_errors[room_config.id] = missing

    if feature_errors:
        return {"agui_features": feature_errors}
    return {}


def _invalid_room_rag_dbs(
    the_installation: installation.Installation,
) -> dict:
    rag_errors: dict[str, dict[str, str]] = {}

    for room_config in the_installation._config.room_configs.values():
        per_room: dict[str, str] = {}

        for source, cfg in _iter_room_rag_candidates(room_config):
            try:
                _ = cfg.haiku_rag_config  # property raises
            except Exception as exc:
                # A config that will not build says why; what it
                # names is unanswerable until that is fixed.
                per_room[source] = str(exc)
                continue

            for label, probe in _rag_db_probes(source, cfg):
                try:
                    _ = probe.rag_lancedb_path  # property raises
                except Exception as exc:
                    per_room[label] = str(exc)

        if per_room:
            rag_errors[room_config.id] = per_room

    if rag_errors:
        return {"rag": rag_errors}
    return {}


def _audit_rooms_section(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
) -> dict:  # pragma NO COVER UI ONLY
    """Print the rooms section (rule header + per-room RAG validity/counts)."""
    quiet = ctx.obj["quiet"]
    the_installation = audit_common._get_installation(ctx, installation_path)
    tc_line, tc_rule, tc_print, _ = audit_common._quiet_console_funcs(quiet)

    tc_line()
    tc_rule("Configured rooms")
    tc_line()

    errors: dict = {}

    invalid = _invalid_rooms(the_installation)
    errors |= invalid
    invalid_rooms = invalid.get("room", {})

    rag_invalid = _invalid_room_rag_dbs(the_installation)
    errors |= rag_invalid
    rag_invalid_rooms = rag_invalid.get("rag", {})

    feature_invalid = _invalid_room_agui_features(the_installation)
    errors |= feature_invalid
    feature_invalid_rooms = feature_invalid.get("agui_features", {})

    # Deliberately bypass auth check done by 'get_room_configs' here.
    available_rooms = the_installation._config.room_configs

    for room_config in available_rooms.values():
        tc_print(f"- [ {room_config.id} ] {room_config.name}: ")
        tc_print(f"  {room_config.description}")

        room_exc = invalid_rooms.get(room_config.id)
        if room_exc is not None:
            tc_print(f"  ERROR: {room_exc}")

        room_features = room_config.agui_feature_names
        if room_features:
            unregistered = set(feature_invalid_rooms.get(room_config.id, ()))
            tc_print()
            tc_print("   AG-UI features")
            for feature_name in room_features:
                flag = "UNREGISTERED" if feature_name in unregistered else "OK"
                tc_print(f"   - {feature_name:30}: {flag}")
            tc_print()

        per_room_rag = rag_invalid_rooms.get(room_config.id, {})
        candidates = list(_iter_room_rag_candidates(room_config))

        if candidates:
            tc_print()
            tc_print("   Haiku Rag DBs")
            for source, cfg in candidates:
                # A config that will not build is recorded under its own
                # source, which the per-database labels never match.
                if source in per_room_rag:
                    failed = (source, per_room_rag[source])
                else:
                    failed = next(
                        (
                            (label, per_room_rag[label])
                            for label, _ in _rag_db_probes(source, cfg)
                            if label in per_room_rag
                        ),
                        None,
                    )
                if failed is not None:
                    failed_label, exc = failed
                    tc_print(f"   - {failed_label:20}: ERROR: {exc}")
                else:
                    rag = hr_client.HaikuRAG(
                        config=cfg.haiku_rag_config,
                        read_only=True,
                    )
                    count_display, count_error = _count_rag_documents(rag)
                    if count_error is not None:
                        room_rag_errors = errors.setdefault(
                            "rag_count", {}
                        ).setdefault(room_config.id, {})
                        room_rag_errors[source] = count_error
                    tc_print(
                        f"   - {source:20}: "
                        f"{cfg.rag_db_audit_path:30} {count_display}"
                    )
                tc_print()
        tc_line()

    interpolation_errors = audit_interpolation._invalid_room_interpolations(
        the_installation
    )
    audit_interpolation._print_interpolation_findings(
        tc_print, interpolation_errors
    )

    return errors | interpolation_errors


def audit_rooms(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
):  # pragma NO COVER command
    """List rooms defined in the installation"""
    quiet = ctx.obj["quiet"]
    errors = _audit_rooms_section(ctx, installation_path)
    audit_common._emit_errors(errors, quiet)
