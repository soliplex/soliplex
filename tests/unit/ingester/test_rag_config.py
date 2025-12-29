import logging

import pytest
from common import do_monkeypatch  # noqa
from common import mock_engine  # noqa

import soliplex.ingester.lib.wf.operations as wf_ops

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_find_config(monkeypatch, mock_engine):  # noqa: F811
    do_monkeypatch(monkeypatch, mock_engine)
    ids = await wf_ops.get_step_config_ids("test1")
    assert ids
    logger.info(f"ids={ids}")
    ids2 = await wf_ops.get_step_config_ids("test2")
    assert ids2
    assert (
        ids[wf_ops.WorkflowStepType.PARSE]
        == ids2[wf_ops.WorkflowStepType.PARSE]
    )
    assert (
        ids[wf_ops.WorkflowStepType.PARSE]
        != ids2[wf_ops.WorkflowStepType.CHUNK]
    )
    assert (
        ids[wf_ops.WorkflowStepType.CHUNK]
        != ids2[wf_ops.WorkflowStepType.CHUNK]
    )
