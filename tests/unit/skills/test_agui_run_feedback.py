from unittest import mock

import pytest

from soliplex.skills import agui_run_feedback


@pytest.fixture
def rf_query() -> agui_run_feedback.RecentRunFeedbackQuery:
    pass


@pytest.mark.anyio
async def test__do_query():
    pass


@pytest.mark.anyio
@mock.patch("soliplex.skills.agui_run_feedback._do_query")
async def test_query_recent_feedback(do_query, rf_query):
    pass


def test_create_skill():
    pass
