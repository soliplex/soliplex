from __future__ import annotations

import typer

from soliplex import installation
from soliplex.cli import types
from soliplex.cli.audit import _common as audit_common
from soliplex.config import quizzes as config_quizzes


def _iter_quiz_configs(the_installation):
    for q_path in the_installation._config.quizzes_paths:
        for q_file in q_path.glob("*.json"):
            yield (
                q_path,
                q_file,
                config_quizzes.QuizConfig(
                    id="check",
                    question_file=str(q_file),
                ),
            )


def _invalid_quizzes(the_installation: installation.Installation) -> dict:
    errors = {}

    for q_path, q_file, q_config in _iter_quiz_configs(the_installation):
        try:
            q_config.get_questions()
        except Exception as exc:
            q_error = f"{exc}"
            quizzes_errors = errors.setdefault("quizzes", {})
            q_path_errors = quizzes_errors.setdefault(str(q_path), {})
            q_path_errors[q_file.name] = q_error

    return errors


def _audit_quizzes_section(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
) -> dict:  # pragma NO COVER UI ONLY
    """Print the quizzes section (rule header + per-file OK / Invalid)."""
    quiet = ctx.obj["quiet"]
    the_installation = audit_common._get_installation(ctx, installation_path)
    tc_line, tc_rule, tc_print, _ = audit_common._quiet_console_funcs(quiet)

    tc_line()
    tc_rule("Configured quizzes")
    tc_line()

    errors = _invalid_quizzes(the_installation)
    invalid_quizzes = errors.get("quizzes", {})

    seen_path = None
    for q_path, q_file, _q_config in _iter_quiz_configs(the_installation):
        if q_path != seen_path:
            tc_print(f"Quiz path: {q_path}")
            seen_path = q_path

        tc_print(f"- Question file: {q_file.name}")
        exc = invalid_quizzes.get(str(q_path), {}).get(q_file.name)

        if exc:
            tc_print(f"  Invalid quiz file: {exc}")
        else:
            tc_print("  OK")
        tc_line()

    return errors


def audit_quizzes(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
):  # pragma NO COVER command
    """List quizzes defined in the installation"""
    quiet = ctx.obj["quiet"]
    errors = _audit_quizzes_section(ctx, installation_path)
    audit_common._emit_errors(errors, quiet)
