from unittest import mock

import pytest

from soliplex import agui


@pytest.fixture
def the_threads():
    storage = mock.create_autospec(agui.ThreadStorage)
    # Left unstubbed, awaiting an 'AsyncMock' yields another 'AsyncMock'
    # whose '.get' returns a coroutine rather than a list of labels --
    # which fails somewhere well away from the cause. Every handler that
    # renders threads asks for these, so default it to a real mapping.
    storage.get_threads_labels.return_value = {}
    return storage
