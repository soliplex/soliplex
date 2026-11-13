from __future__ import annotations

import asyncio
import pathlib
import time
import warnings

import typer
from haiku.rag import client as hr_client

from soliplex import installation
from soliplex import models
from soliplex import util
from soliplex.cli import types
from soliplex.cli.audit import _common as audit_common
from soliplex.cli.audit import interpolation as audit_interpolation
from soliplex.cli.audit import non_local_paths as audit_non_local
from soliplex.config import agui as config_agui
from soliplex.config import quotas as config_quotas
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


def _invalid_rooms(
    the_installation: installation.Installation,
    non_local_prompt_ids: set,
) -> dict:
    """Check that each room config renders as a model

    Skips the rooms named in 'non_local_prompt_ids'.
    """
    errors: dict[str, str] = {}

    for room_config in the_installation._config.room_configs.values():
        if room_config.id in non_local_prompt_ids:
            continue

        try:
            models.Room.from_config(room_config)
        except Exception as exc:
            errors[room_config.id] = str(exc)

    if errors:
        return {"room": errors}
    return {}


def _mismatched_room_ids(
    the_installation: installation.Installation,
) -> dict:
    """Return a finding for each room whose ID is not its directory's name"""
    findings = {}

    for room_config in the_installation._config.room_configs.values():
        room_dir = room_config._config_path.parent

        if room_config.id != room_dir.name:
            findings[room_config.id] = {"directory": str(room_dir)}

    if findings:
        return {"rooms_id_mismatch": findings}

    return {}


# An internal upload file this old belongs to an upload which will never
# finish:  a live copy keeps its reservation's 'mtime' moving.  Generous,
# to cover clock skew between this host and the storage server.
ORPHANED_UPLOAD_AGE_SECONDS = 3600


def _scan_room_uploads(
    the_installation: installation.Installation,
) -> tuple[dict[str, util.UploadsScan], dict]:
    """Scan each room's uploads directory once:  '(scans, findings)'

    No scans when the installation configures no room uploads.  A room
    whose directory does not exist yet (a new room) scans as empty;  one
    which cannot be read is a 'room_upload_scan' finding.
    """
    uploads_path = the_installation.rooms_upload_path

    if uploads_path is None:
        return {}, {}

    scans = {}
    errors: dict[str, str] = {}

    for room_id in the_installation._config.room_configs:
        try:
            scans[room_id] = util.scan_uploads(
                pathlib.Path(uploads_path) / room_id,
            )
        except OSError as exc:
            errors[room_id] = str(exc)

    if errors:
        return scans, {"room_upload_scan": errors}

    return scans, {}


def _room_quota_reports(
    the_installation: installation.Installation,
    scans: dict[str, util.UploadsScan],
) -> tuple[dict, dict]:
    """Report each room's upload quota:  '(findings, reports)'

    A quota which will not resolve is a 'room_quotas' finding.  Usage over
    the quota is *not* a finding, only reported:  the quota is soft across
    server processes, and an overage in one room must not fail an audit
    run, say, to provision another.
    """
    errors: dict[str, str] = {}
    reports: dict[str, dict] = {}
    uploads_configured = the_installation.rooms_upload_path is not None

    for room_id, room_config in the_installation._config.room_configs.items():
        quotas = room_config.quotas

        try:
            quota_bytes = quotas.room_uploads_bytes
        except config_quotas.InvalidQuotasConfig as exc:
            errors[room_id] = str(exc)
            continue

        if quota_bytes is None:
            continue

        report = {
            "quota_bytes": quota_bytes,
            "env_name": quotas.room_uploads_bytes_env_name,
            "uploads_configured": uploads_configured,
        }
        scan = scans.get(room_id)

        if scan is not None:
            report["used_bytes"] = scan.stored_bytes
            report["over_bytes"] = max(scan.stored_bytes - quota_bytes, 0)

        reports[room_id] = report

    if errors:
        return {"room_quotas": errors}, reports

    return {}, reports


def _orphan_kind(name: str) -> str:
    if name.startswith(util.UPLOAD_RESERVATION_PREFIX):
        return "reservation"

    return "nfs"


def _room_orphan_reports(
    scans: dict[str, util.UploadsScan],
    *,
    now: float,
) -> dict[str, list[dict]]:
    """Report each room's orphaned internal upload files

    Only reported, never a finding, and never removed:  a replica cannot
    tell another's slow upload from an abandoned one except by age (see
    'ORPHANED_UPLOAD_AGE_SECONDS').
    """
    reports = {}

    for room_id, scan in scans.items():
        orphans = [
            {
                "name": hidden.name,
                "kind": _orphan_kind(hidden.name),
                "size_bytes": hidden.size_bytes,
                "age_seconds": int(now - hidden.mtime),
            }
            for hidden in scan.hidden
            if now - hidden.mtime > ORPHANED_UPLOAD_AGE_SECONDS
        ]

        if orphans:
            reports[room_id] = orphans

    return reports


def _print_room_quota_report(
    tc_print,
    quota_report: dict,
):  # pragma NO COVER UI ONLY
    quota_bytes = quota_report["quota_bytes"]
    env_name = quota_report["env_name"]
    source = f" (from env:{env_name})" if env_name else ""
    tc_print()

    if not quota_report["uploads_configured"]:
        tc_print(f"   Room uploads quota: {quota_bytes} bytes{source}")
        tc_print("   NOTE: the quota has no effect: no 'rooms_upload_path'")
        return

    used_bytes = quota_report["used_bytes"]
    pct = f"{used_bytes * 100 // quota_bytes}%" if quota_bytes else "-"
    tc_print(
        f"   Room uploads quota: {quota_bytes} bytes{source} "
        f"(used {used_bytes}, {pct})"
    )

    if quota_report["over_bytes"]:
        tc_print(
            "   NOTE: room uploads OVER QUOTA by "
            f"{quota_report['over_bytes']} bytes"
        )


def _print_room_orphan_report(
    tc_print,
    orphans: list[dict],
):  # pragma NO COVER UI ONLY
    orphan_bytes = sum(orphan["size_bytes"] for orphan in orphans)
    tc_print()
    tc_print(
        f"   NOTE: {len(orphans)} orphaned upload files, "
        f"{orphan_bytes} bytes (counted against any quota)"
    )

    for orphan in orphans:
        tc_print(
            f"   - {orphan['name']:40} {orphan['kind']:11} "
            f"{orphan['size_bytes']} bytes, {orphan['age_seconds']}s old"
        )


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

    reports = audit_non_local._non_local_path_reports(ctx, the_installation)
    errors |= audit_non_local._non_local_path_findings(
        reports, audit_non_local.ROOMS
    )
    non_local_rooms = reports[audit_non_local.ROOMS]

    invalid = _invalid_rooms(
        the_installation,
        audit_non_local._non_local_prompt_ids(reports, audit_non_local.ROOMS),
    )
    errors |= invalid
    invalid_rooms = invalid.get("room", {})

    rag_invalid = _invalid_room_rag_dbs(the_installation)
    errors |= rag_invalid
    rag_invalid_rooms = rag_invalid.get("rag", {})

    feature_invalid = _invalid_room_agui_features(the_installation)
    errors |= feature_invalid
    feature_invalid_rooms = feature_invalid.get("agui_features", {})

    mismatched = _mismatched_room_ids(the_installation)
    errors |= mismatched
    mismatched_rooms = mismatched.get("rooms_id_mismatch", {})

    upload_scans, scan_errors = _scan_room_uploads(the_installation)
    errors |= scan_errors
    scan_failed_rooms = scan_errors.get("room_upload_scan", {})
    quota_errors, quota_reports = _room_quota_reports(
        the_installation,
        upload_scans,
    )
    errors |= quota_errors
    quota_failed_rooms = quota_errors.get("room_quotas", {})
    orphan_reports = _room_orphan_reports(upload_scans, now=time.time())

    # Deliberately bypass auth check done by 'get_room_configs' here.
    available_rooms = the_installation._config.room_configs

    for room_config in available_rooms.values():
        tc_print(f"- [ {room_config.id} ] {room_config.name}: ")
        tc_print(f"  {room_config.description}")

        room_exc = invalid_rooms.get(room_config.id)
        if room_exc is not None:
            tc_print(f"  ERROR: {room_exc}")

        mismatch = mismatched_rooms.get(room_config.id)
        if mismatch is not None:
            tc_print(
                "  ERROR: room ID does not match its directory: "
                f"{mismatch['directory']}"
            )

        audit_non_local._print_non_local_path_findings(
            tc_print,
            non_local_rooms.get(room_config.id, {}),
            "  ",
        )

        quota_exc = quota_failed_rooms.get(room_config.id)
        if quota_exc is not None:
            tc_print(f"  ERROR: {quota_exc}")

        scan_exc = scan_failed_rooms.get(room_config.id)
        if scan_exc is not None:
            tc_print(f"  ERROR: room uploads cannot be read: {scan_exc}")

        quota_report = quota_reports.get(room_config.id)
        if quota_report is not None and (
            "used_bytes" in quota_report
            or not quota_report["uploads_configured"]
        ):
            _print_room_quota_report(tc_print, quota_report)

        orphans = orphan_reports.get(room_config.id)
        if orphans:
            _print_room_orphan_report(tc_print, orphans)

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
