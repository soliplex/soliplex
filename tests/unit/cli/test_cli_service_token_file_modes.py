from __future__ import annotations

import stat

from soliplex.cli import service_token as cli_service_token
from tests import _platform

pytestmark = _platform.requires_posix_file_modes

TOKEN = "DEADBEEF"


def test__write_output_owner_only(tmp_path):
    output = tmp_path / "token"

    cli_service_token._write_output(output, TOKEN, force=False)

    assert stat.S_IMODE(output.stat().st_mode) == 0o600
