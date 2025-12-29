import logging

import pytest
from common import do_monkeypatch
from common import mock_engine  # noqa

import soliplex.ingester.lib.dal as dal
import soliplex.ingester.lib.models as models
from soliplex.ingester.lib.config import get_settings

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_operators(monkeypatch, mock_engine):  # noqa F811
    do_monkeypatch(monkeypatch, mock_engine)
    bytea = b"test"
    get_settings().file_store_target = "db"
    for st in models.ArtifactType:
        step_config = models.StepConfig(id=1, step_type=models.ARTIFACTS_TO_STEPS[st])
        logger.info(f" testing {st}")
        op = dal.get_storage_operator(st, step_config)
        assert op is not None
        await op.write("test", bytea)
        is_exist = await op.is_exist("test")
        assert is_exist
        read_bytea = await op.read("test")
        assert read_bytea == bytea
        lis = await op.list("/")
        logger.info(f"lis={lis} ")
        assert len(lis) == 1
        await op.delete("test")
        ex2 = await op.is_exist("test")
        assert not ex2
