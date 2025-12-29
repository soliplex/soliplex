import logging

import pytest
from common import do_monkeypatch  # noqa
from common import mock_engine  # noqa

import soliplex.ingester.lib.operations as doc_ops

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_create_run_group(monkeypatch, mock_engine):  # noqa F811
    do_monkeypatch(monkeypatch, mock_engine)

    import data as data

    batch_id = await doc_ops.new_batch("pytest", "pytest")
    assert batch_id

    # rg = await wf_ops.create_run_group(workflow_definition_id="batch", batch_id=batch_id, param_id="default")
