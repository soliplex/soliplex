from __future__ import annotations

from unittest import mock

import pytest

from soliplex.cli.audit import _common as audit_common


@pytest.mark.parametrize("w_quiet", [False, True])
@mock.patch("soliplex.cli.audit._common.the_console")
def test__quiet_console_funcs(the_console, w_quiet):
    f_line, f_rule, f_print, f_print_exception = (
        audit_common._quiet_console_funcs(w_quiet)
    )

    if w_quiet:
        assert f_line is audit_common._noop
        assert f_rule is audit_common._noop
        assert f_print is audit_common._noop
        assert f_print_exception is audit_common._noop
    else:
        assert f_line is the_console.line
        assert f_rule is the_console.rule
        assert f_print is the_console.print
        assert f_print_exception is the_console.print_exception


@pytest.mark.parametrize("w_quiet", [False, True])
@pytest.mark.parametrize("w_errors", [{}, {"foo": "bar"}])
@mock.patch("soliplex.cli.audit._common.the_console")
@mock.patch("sys.exit")
def test__emit_errors(
    sys_exit,
    the_console,
    w_errors,
    w_quiet,
):
    audit_common._emit_errors(w_errors, w_quiet)

    if w_errors and w_quiet:
        the_console.print_json.assert_called_once_with(data=w_errors)
    else:
        the_console.print_json.assert_not_called()

    if w_errors:
        sys_exit.assert_called_once_with(1)
    else:
        sys_exit.assert_not_called()


@pytest.mark.parametrize("w_already", [False, True])
@mock.patch("soliplex.cli.cli_util.get_installation")
def test__get_installation(
    get_installation,
    ctx,
    installation_path,
    w_already,
):
    already = object()

    if w_already:
        ctx.obj["the_installation"] = already

    found = audit_common._get_installation(ctx, installation_path)

    if w_already:
        assert found is already
        get_installation.assert_not_called()
    else:
        assert found is get_installation.return_value
        get_installation.assert_called_once_with(
            installation_path,
            auditing=True,
        )
