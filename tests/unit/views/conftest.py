from unittest import mock

import pytest

from soliplex import agui


@pytest.fixture
def the_threads():
    return mock.create_autospec(agui.ThreadStorage)
