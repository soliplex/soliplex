import logging

import pytest
import yaml
from common import do_monkeypatch
from common import mock_engine  # noqa

import soliplex.ingester.lib.wf.operations as wf_ops
import soliplex.ingester.lib.wf.registry as wf_registry
from soliplex.ingester.lib.models import EventHandler
from soliplex.ingester.lib.models import WorkflowDefinition
from soliplex.ingester.lib.models import WorkflowStepType

logger = logging.getLogger(__name__)


def xtest_create_config():
    parse = EventHandler(
        name="parse",
        step_type="PARSE",
        method="soliplex.ingester.lib.workflow.parse_document",
        parameters={},
    )
    chunk = EventHandler(
        name="parse",
        step_type="CHUNK",
        method="soliplex.ingester.lib.workflow.chunk_document",
        parameters={},
    )
    embed = EventHandler(
        name="parse",
        step_type="EMBED",
        method="soliplex.ingester.lib.workflow.embed_document",
        parameters={},
    )
    store = EventHandler(
        name="parse",
        step_type="STORE",
        method="soliplex.ingester.lib.workflow.save_to_rag",
        parameters={},
    )

    batch_start = EventHandler(
        name="batch_start",
        method="soliplex.ingester.lib.config.get_settings",
        parameters={},
    )
    lifecycle = EventHandler(batch_start=[batch_start])
    cfg = WorkflowDefinition(
        id="test",
        name="test",
        meta={},
        item_steps=[parse, chunk, embed, store],
        life_cycle_events=lifecycle,
    )

    assert cfg
    dicts = cfg.model_dump_json()
    with open("tests/files/test_config.yaml", "w") as f:
        f.write(yaml.dump(yaml.safe_load(dicts)))


@pytest.mark.asyncio
async def test_get_workflow_def():
    wf_loaded = await wf_registry.get_workflow_definition("batch")
    assert wf_loaded


@pytest.mark.asyncio
async def test_load_params():
    wf_loaded = await wf_registry.get_param_set("default")
    assert wf_loaded


def test_make_config():
    steps = {
        "parse": EventHandler(
            name="parse",
            method="soliplex.ingester.lib.workflow.parse_document",
            parameters={},
        ),
        "chunk": EventHandler(
            name="chunk",
            method="soliplex.ingester.lib.workflow.chunk_document",
            parameters={},
        ),
        "embed": EventHandler(
            name="embed",
            method="soliplex.ingester.lib.workflow.embed_document",
            parameters={},
        ),
        "store": EventHandler(
            name="store",
            method="soliplex.ingester.lib.workflow.save_to_rag",
            parameters={},
        ),
    }
    wc = WorkflowDefinition(id="test", name="test", meta={}, item_steps=steps, lifecycle_events={})
    js = wc.model_dump_json()
    yaml.dump(yaml.safe_load(js))


@pytest.mark.asyncio
async def test_get_step_param_ids(monkeypatch, mock_engine):  # noqa F811
    do_monkeypatch(monkeypatch, mock_engine)

    pset1 = await wf_registry.get_param_set("test1")
    pset2 = await wf_registry.get_param_set("test2")
    pset3 = await wf_registry.get_param_set("test3")
    assert pset1 is not None
    assert pset2 is not None
    assert pset3 is not None

    ids1 = await wf_ops.get_step_config_ids("test1")
    assert ids1
    ids2 = await wf_ops.get_step_config_ids("test2")
    assert ids2
    ids3 = await wf_ops.get_step_config_ids("test3")
    assert ids3
    logger.info(f"ids1={ids1}")
    logger.info(f"ids1={ids2}")
    logger.info(f"ids1={ids3}")
    assert ids1[WorkflowStepType.PARSE] == ids2[WorkflowStepType.PARSE]
    assert ids1[WorkflowStepType.CHUNK] != ids2[WorkflowStepType.CHUNK]
    assert ids1[WorkflowStepType.EMBED] != ids2[WorkflowStepType.EMBED]
    assert ids1[WorkflowStepType.PARSE] == ids3[WorkflowStepType.PARSE]  # same config for parse
    assert (
        ids1[WorkflowStepType.EMBED] != ids3[WorkflowStepType.EMBED]
    )  # 3 skips  chunk but parse and embed are identical this means embed needs to be different for 3
