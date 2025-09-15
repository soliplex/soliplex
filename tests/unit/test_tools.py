import datetime
from unittest import mock

import pytest

from soliplex import tools


@pytest.mark.anyio
@mock.patch("soliplex.tools.datetime")
async def test_get_current_datetime(dt_module):
    NOW = datetime.datetime(2025, 8, 7, 11, 32, 41, tzinfo=datetime.UTC)
    now = dt_module.datetime.now
    now.return_value = NOW

    found = await tools.get_current_datetime()

    assert found == NOW.isoformat()

    now.assert_called_once_with(dt_module.UTC)
