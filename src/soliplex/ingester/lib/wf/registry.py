import logging
from pathlib import Path

import aiofiles
import yaml

from soliplex.ingester.lib.config import get_settings
from soliplex.ingester.lib.models import WorkflowDefinition
from soliplex.ingester.lib.models import WorkflowParams

logger = logging.getLogger(__name__)
_workflow_registry = None
_param_registry = None


async def load_workflow_definition(yaml_file: Path) -> WorkflowDefinition:
    async with aiofiles.open(yaml_file) as f:
        yaml_str = await f.read()
    loaded = yaml.safe_load(yaml_str)
    wf_loaded = WorkflowDefinition.model_validate(loaded)
    return wf_loaded


async def load_workflow_registry(
    force_reload: bool = False,
) -> dict[str, WorkflowDefinition]:
    global _workflow_registry
    if _workflow_registry is not None and not force_reload:
        return _workflow_registry
    settings = get_settings()
    reg = {}
    for p in Path(settings.workflow_dir).glob("*.yaml"):
        logger.debug(f"loading workflow {p}")
        wf = await load_workflow_definition(p)
        if wf.id in reg:
            msg = f"duplicate workflow id {wf.id}"
            raise ValueError(msg)
        reg[wf.id] = wf
    _workflow_registry = reg
    return reg


async def get_workflow_definition(
    wf_id: str | None = None,
) -> WorkflowDefinition:
    if wf_id is None:
        wf_id = get_default_wofklow_id()
    registry = await load_workflow_registry()
    if wf_id in registry:
        return registry[wf_id]
    else:
        load_workflow_registry(force_reload=True)
        if wf_id in registry:
            return registry[wf_id]
        raise KeyError(f"workflow {wf_id} not found")


def get_default_wofklow_id() -> str:
    settings = get_settings()
    return settings.default_workflow_id


def get_default_param_id() -> str:
    settings = get_settings()
    return settings.default_param_id


async def load_param_set(yaml_file: Path) -> WorkflowParams:
    async with aiofiles.open(yaml_file) as f:
        yaml_str = await f.read()
    loaded = yaml.safe_load(yaml_str)
    wf_loaded = WorkflowParams.model_validate(loaded)
    return wf_loaded


async def get_param_set(id: str | None = None) -> WorkflowParams:
    if id is None:
        id = get_default_param_id()
    registry = await load_param_registry()
    if id in registry:
        return registry[id]
    else:
        await load_param_registry(force_reload=True)
        if id in registry:
            return registry[id]
        raise KeyError(f"param set {id} not found")


async def load_param_registry(
    force_reload: bool = False,
) -> dict[str, WorkflowParams]:
    global _param_registry
    if _param_registry is not None and not force_reload:
        return _param_registry
    settings = get_settings()
    reg = {}
    for p in Path(settings.param_dir).glob("*.yaml"):
        logger.debug(f"loading param set {p}")
        wf = await load_param_set(p)
        if wf.id in reg:
            raise ValueError(f"duplicate param set id {wf.id}")
        reg[wf.id] = wf
    _param_registry = reg
    return reg
