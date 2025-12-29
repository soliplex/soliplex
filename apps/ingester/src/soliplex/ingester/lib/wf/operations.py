import datetime
import json
import logging

import yaml
from async_lru import alru_cache
from sqlalchemy import func
from sqlmodel import select
from sqlmodel import text
from sqlmodel import update

from soliplex.ingester.lib.dal import get_storage_operator
from soliplex.ingester.lib.models import ArtifactType
from soliplex.ingester.lib.models import ConfigSet
from soliplex.ingester.lib.models import ConfigSetItem
from soliplex.ingester.lib.models import LifeCycleEvent
from soliplex.ingester.lib.models import LifecycleHistory
from soliplex.ingester.lib.models import RunGroup
from soliplex.ingester.lib.models import RunStatus
from soliplex.ingester.lib.models import RunStep
from soliplex.ingester.lib.models import StepConfig
from soliplex.ingester.lib.models import WorkflowRun
from soliplex.ingester.lib.models import WorkflowRunWithSteps
from soliplex.ingester.lib.models import WorkflowStepType
from soliplex.ingester.lib.models import get_session
from soliplex.ingester.lib.operations import get_batch
from soliplex.ingester.lib.operations import get_document
from soliplex.ingester.lib.operations import get_documents_in_batch

from .registry import get_param_set
from .registry import get_workflow_definition

logger = logging.getLogger(__name__)


class NotFoundError(Exception):
    pass


async def create_workflow_runs_for_batch(
    batch_id: int,
    workflow_definition_id: str | None = None,
    priority: int = 0,
    param_id: str | None = None,
) -> tuple[RunGroup, list[WorkflowRun]]:
    """
    Creates a workflow run for each document in a batch

    """
    run_group = await create_run_group(
        workflow_definition_id=workflow_definition_id,
        batch_id=batch_id,
        param_id=param_id,
    )
    batch_documents = await get_documents_in_batch(batch_id)
    runs = []
    for doc in batch_documents:
        run, steps = await create_workflow_run(
            run_group=run_group,
            doc_id=doc.hash,
            priority=priority,
        )
        runs.append(run)
    return run_group, runs


@alru_cache(maxsize=1024)
async def get_step_config_ids(param_id: str) -> dict[WorkflowStepType, int]:
    """
    Returns a map of step type to step config ID for a given
    parameter set.  this config id is potentially shared across
    multiple parameter configurations if the parameters are the
    same up to that step (e.g. step 1 and 2 are identical
    but 3 is different then 1 and 2 get shared)
    """
    # TODO: if param sets become dynamic then this needs to be updated
    param_set = await get_param_set(param_id)
    js = param_set.model_dump_json()
    yaml_str = yaml.dump(yaml.safe_load(js))

    id_map = {}
    typelist = list(WorkflowStepType)
    async with get_session() as session:
        with session.no_autoflush:
            setq = select(ConfigSet).where(ConfigSet.yaml_contents == yaml_str)
            setrs = await session.exec(setq)
            exist_set = setrs.first()
            if exist_set:
                stepq = text(
                    f"""select stepconfig.* from stepconfig
                    inner join configsetitem
                    on configsetitem.config_id=stepconfig.id
                    where configsetitem.config_set_id={exist_set.id}"""
                )
                steprs = await session.exec(stepq)

                for step in steprs.all():
                    id_map[WorkflowStepType[step.step_type]] = step.id
                return id_map
            configset = ConfigSet(
                yaml_id=param_set.id,
                yaml_contents=yaml_str,
                created_date=datetime.datetime.now(),
            )
            session.add(configset)
            await session.flush()
            await session.refresh(configset)
            cuml_cfg = {}
            cuml_str = json.dumps(cuml_cfg, indent=4)
            for st in typelist:
                if st in param_set.config:
                    step_config = param_set.config[st]
                else:
                    step_config = {}
                cuml_cfg = cuml_cfg.copy()
                cuml_cfg.update({st.value: step_config})
                cuml_str = json.dumps(cuml_cfg, indent=4)
                existq = select(StepConfig).where(StepConfig.step_type == st).where(StepConfig.cuml_config_json == cuml_str)
                rs = await session.exec(existq)
                exist = rs.first()
                if exist:
                    id_map[st] = exist.id
                else:
                    step_config = StepConfig(
                        step_type=st,
                        config_json=step_config,
                        cuml_config_json=cuml_str,
                    )
                    session.add(step_config)
                    await session.flush()
                    await session.refresh(step_config)
                    id_map[st] = step_config.id
                step_id = id_map[st]
                set_id = configset.id
                logger.info(f"created step config {step_id} config_set={set_id}")
                setitem = ConfigSetItem(config_set_id=set_id, config_id=step_id)
                session.add(setitem)
                await session.flush()
            await session.commit()
    return id_map


async def get_run_groups_for_batch(batch_id: int | None) -> list[RunGroup]:
    async with get_session() as session:
        q = select(RunGroup)
        if batch_id is not None:
            q = q.where(RunGroup.batch_id == batch_id)
        q = q.order_by(RunGroup.created_date.desc())
        rs = await session.exec(q)
        groups = rs.all()
        [session.expunge(x) for x in groups]
        return groups


async def get_run_group(run_group_id: int) -> RunGroup:
    async with get_session() as session:
        q = select(RunGroup).where(RunGroup.id == run_group_id)
        rs = await session.exec(q)
        res = rs.first()
        if res:
            session.expunge(res)
            return res
        raise NotFoundError(f"run group {run_group_id} not found")


async def get_run_group_stats(run_group_id: int) -> dict[RunStatus:int]:
    async with get_session() as session:
        q = text(
            f"""select r.status,count(distinct workflow_run_id)
            from runstep r inner join workflowrun w
            on w.id=r.workflow_run_id
            where run_group_id={run_group_id}
            group by r.status"""
        )
        rs = await session.exec(q)
        res = rs.all()
        ret = {}
        for k in RunStatus:
            ret[k.value] = 0
        for row in res:
            ret[row[0]] = row[1]
        return ret


async def create_run_group(
    workflow_definition_id: str | None,
    batch_id: int | None = None,
    param_id: str | None = None,
    name: str | None = None,
) -> RunGroup:
    batch = await get_batch(batch_id)
    if batch is None:
        raise NotFoundError(f"Batch {batch_id} not found")

    # pull definitions from registry so defaults can be used and check if ids are invalid
    workflow_def = await get_workflow_definition(workflow_definition_id)
    param_set = await get_param_set(param_id)
    dt = datetime.datetime.now()

    async with get_session() as session:
        run_group = RunGroup(
            workflow_definition_id=workflow_def.id,
            batch_id=batch_id,
            name=name,
            param_definition_id=param_set.id,
            created_date=dt,
            start_date=dt,
        )

        session.add(run_group)

        await session.flush()
        await session.refresh(run_group)
        session.expunge(run_group)
        await session.commit()
        return run_group


async def create_lifecycle_history(
    run_group_id: int,
    workflow_run_id: int,
    event: LifeCycleEvent,
    status: RunStatus,
    step_id: int | None = None,
    status_message: str | None = None,
    status_meta: dict[str, str] | None = None,
):
    dt = datetime.datetime.now()
    async with get_session() as session:
        run_group_history = LifecycleHistory(
            run_group_id=run_group_id,
            workflow_run_id=workflow_run_id,
            step_id=step_id,
            event=event,
            status=status,
            status_date=dt,
            start_date=dt,
            status_message=status_message,
            status_meta=status_meta,
        )

        session.add(run_group_history)

        await session.flush()
        await session.refresh(run_group_history)
        session.expunge(run_group_history)
        await session.commit()
        return run_group_history


async def update_lifecycle_history(
    run_group_id: int,
    workflow_run_id: int,
    event: LifeCycleEvent,
    status: RunStatus,
    step_id: int | None = None,
    status_message: str | None = None,
    status_meta: dict[str, str] | None = None,
):
    dt = datetime.datetime.now()
    end_date = None
    if status == RunStatus.COMPLETED or status == RunStatus.FAILED:
        end_date = dt
    async with get_session() as session:
        q = (
            update(LifecycleHistory)
            .where(LifecycleHistory.run_group_id == run_group_id)
            .where(LifecycleHistory.workflow_run_id == workflow_run_id)
            .where(LifecycleHistory.step_id == step_id)
            .where(LifecycleHistory.lifecycle_event == event)
            .values(
                status=status,
                status_date=dt,
                status_message=status_message,
                status_meta=status_meta,
                end_date=end_date,
            )
        )
        await session.exec(q)
        await session.commit()


async def create_single_workflow_run(
    workflow_definiton_id: str,
    doc_id: str,
    priority: int = 0,
    param_id: str | None = None,
):
    doc = await get_document(doc_id)
    batch_id = doc.batch_id
    run_group = await create_run_group(
        workflow_definition_id=workflow_definiton_id,
        batch_id=batch_id,
        name=f"single run {doc_id} ",
        param_id=param_id,
    )
    return await create_workflow_run(run_group, doc_id, priority=priority)


async def create_workflow_run(
    run_group: RunGroup,
    doc_id: str,
    priority: int = 0,
) -> tuple[WorkflowRun, list[RunStep]]:
    """
    Creates a new workflow run.

    Args:
        workflow_definitinon_id (str | None): the ID of the workflow
            definition. if None, the default workflow will be used
        batch_id (int): the ID of the batch containing the document
        doc_id (str): the ID of the document being processed
        priority (int): the priority of the workflow run
        param_id (str | None): the ID of the parameter set

    Returns:
        A tuple containing the newly created workflow run and a list
        of newly created run steps
    """
    batch_id = run_group.batch_id
    workflow_definition_id = run_group.workflow_definition_id
    param_id = run_group.param_definition_id
    batch = await get_batch(batch_id)
    if batch is None:
        raise NotFoundError(f"Batch {batch_id} not found")
    workflow_def = await get_workflow_definition(workflow_definition_id)
    parameter_ids = await get_step_config_ids(param_id)
    created = datetime.datetime.now()
    args = {
        "param_id": param_id,
        "workflow_id": workflow_definition_id,
        "source": batch.source,
    }
    async with get_session() as session:
        workflow_run = WorkflowRun(
            run_group_id=run_group.id,
            workflow_definition_id=workflow_def.id,
            batch_id=batch_id,
            doc_id=doc_id,
            start_date=datetime.datetime.now(),
            priority=priority,
            created_date=created,
            run_params=args,
        )
        session.add(workflow_run)
        await session.flush()
        await session.refresh(workflow_run)

        new_steps = []
        idx = 0
        for step_type, evt_handler in workflow_def.item_steps.items():
            run_step = RunStep(
                workflow_run_id=workflow_run.id,
                workflow_step_number=idx + 1,
                workflow_step_name=evt_handler.name,
                retries=evt_handler.retries,
                priority=priority,
                created_date=created,
                status_date=created,
                step_type=step_type,
                step_config_id=parameter_ids[step_type],
                is_last_step=idx == len(workflow_def.item_steps) - 1,
            )
            session.add(run_step)
            new_steps.append(run_step)
            idx += 1
        await session.flush()
        session.expunge(workflow_run)
        [session.expunge(step) for step in new_steps]
        await session.commit()

        return workflow_run, new_steps


async def get_workflows(
    batch_id: int | None,
    include_steps: bool = False,
    page: int | None = None,
    rows_per_page: int | None = None,
) -> tuple[list[WorkflowRun] | list[WorkflowRunWithSteps], int]:
    """
    Get workflow runs, optionally with their associated steps.

    Args:
        batch_id: Optional batch ID filter
        include_steps: If True, include associated RunSteps for each workflow run
        page: Page number (1-indexed). If None, returns all rows.
        rows_per_page: Number of rows per page. If None, returns all rows.

    Returns:
        Tuple of (list of workflow runs, total count)
    """
    async with get_session() as session:
        # Build base query
        q = select(WorkflowRun)
        if batch_id is not None:
            q = q.where(WorkflowRun.batch_id == batch_id)

        # Add consistent ordering (newest first)
        q = q.order_by(WorkflowRun.created_date.desc())

        # Get total count before pagination
        count_q = select(func.count()).select_from(WorkflowRun)
        if batch_id is not None:
            count_q = count_q.where(WorkflowRun.batch_id == batch_id)
        count_rs = await session.exec(count_q)
        total = count_rs.one()

        # Apply pagination if parameters provided
        if page is not None and rows_per_page is not None:
            offset = (page - 1) * rows_per_page
            q = q.offset(offset).limit(rows_per_page)

        # Execute query
        rs = await session.exec(q)
        res = rs.all()
        [session.expunge(x) for x in res]

        if not include_steps:
            return res, total

        # Load steps for all workflow runs efficiently
        workflow_run_ids = [run.id for run in res]
        steps_by_run_id = await get_steps_for_workflow_runs(workflow_run_ids)

        # Combine workflow runs with their steps
        result = []
        for run in res:
            steps = steps_by_run_id.get(run.id, [])
            result.append(WorkflowRunWithSteps(workflow_run=run, steps=steps))

        return result, total


async def get_workflows_for_status(
    status: RunStatus,
    batch_id: int | None = None,
    page: int | None = None,
    rows_per_page: int | None = None,
) -> tuple[list[WorkflowRun], int]:
    """
    Get workflow runs filtered by status, optionally paginated.

    Args:
        status: Filter by run status
        batch_id: Optional batch ID filter
        page: Page number (1-indexed). If None, returns all rows.
        rows_per_page: Number of rows per page. If None, returns all rows.

    Returns:
        Tuple of (list of workflow runs, total count)
    """
    async with get_session() as session:
        # Build base query
        q = select(WorkflowRun).where(WorkflowRun.status == status)
        if batch_id is not None:
            q = q.where(WorkflowRun.batch_id == batch_id)

        # Add consistent ordering (newest first)
        q = q.order_by(WorkflowRun.created_date.desc())

        # Get total count before pagination
        count_q = select(func.count()).select_from(WorkflowRun).where(WorkflowRun.status == status)
        if batch_id is not None:
            count_q = count_q.where(WorkflowRun.batch_id == batch_id)

        count_result = await session.exec(count_q)
        total = count_result.one()

        # Apply pagination if requested
        if page is not None and rows_per_page is not None:
            offset = (page - 1) * rows_per_page
            q = q.offset(offset).limit(rows_per_page)

        # Execute query
        rs = await session.exec(q)
        res = rs.all()
        [session.expunge(x) for x in res]

        return res, total


async def get_workflow_run(id: int, get_steps=False) -> WorkflowRun:
    async with get_session() as session:
        q = select(WorkflowRun).where(WorkflowRun.id == id)
        rs = await session.exec(q)
        run = rs.first()

        if run:
            session.expunge(run)
            if get_steps:
                q = select(RunStep).where(RunStep.workflow_run_id == id)
                rs = await session.exec(q)
                rs = rs.all()
                [session.expunge(x) for x in rs]
                steps = rs
                return run, steps

            return run
        raise NotFoundError(f"workflow run {id} not found")


async def get_workflow_runs(batch_id: int) -> WorkflowRun:
    async with get_session() as session:
        q = select(WorkflowRun).where(WorkflowRun.batch_id == batch_id)
        rs = await session.exec(q)
        res = rs.first()
        if res:
            session.expunge(res)
            return res
        raise NotFoundError(f"workflow run {batch_id} not found")


async def get_run_step(run_step_id: int) -> RunStep:
    async with get_session() as session:
        q = select(RunStep).where(RunStep.id == run_step_id)
        rs = await session.exec(q)
        res = rs.first()
        if res:
            session.expunge(res)
            return res
        raise NotFoundError(f"run step {run_step_id} not found")


async def get_step_config_by_id(step_config_id: int) -> StepConfig:
    async with get_session() as session:
        q = select(StepConfig).where(StepConfig.id == step_config_id)
        rs = await session.exec(q)
        res = rs.first()
        if res:
            session.expunge(res)
            return res
        raise NotFoundError(f"step config {step_config_id} not found")


async def find_operator_for_workflow_run(
    workflow_run_id: int,
    step_type: WorkflowStepType,
    artifact_type: ArtifactType,
) -> StepConfig:
    step_config = await get_step_config_for_workflow_run(workflow_run_id, step_type)
    return get_storage_operator(artifact_type, step_config)


async def get_step_config_for_workflow_run(workflow_run_id: int, step_type: WorkflowStepType) -> StepConfig:
    async with get_session() as session:
        q = text(
            f"""select s.id from
            stepconfig s inner join runstep r
            on r.step_config_id=s.id
            where r.workflow_run_id={workflow_run_id}
            and r.step_type='{step_type.value.upper()}'"""
        )

        rs = await session.exec(q)
        res = rs.first()
        if res:
            # could probably convert directly but will figure out later
            q = select(StepConfig).where(StepConfig.id == res[0])
            rs = await session.exec(q)
            res = rs.first()
            session.expunge(res)

            return res
        raise NotFoundError(f"step config {step_type} not found")


async def update_run_status(workflow_run_id: int, is_last_step: bool, status: RunStatus, session):
    update_status = None
    if is_last_step and status == RunStatus.COMPLETED:
        update_status = RunStatus.COMPLETED
    elif status == RunStatus.FAILED:
        update_status = RunStatus.FAILED
    elif not is_last_step and status in (
        RunStatus.COMPLETED,
        RunStatus.RUNNING,
        RunStatus.ERROR,
    ):
        update_status = RunStatus.RUNNING
    logger.info(f"update run status {workflow_run_id} {update_status} {status}")
    if update_status is not None:
        q = select(WorkflowRun).where(WorkflowRun.id == workflow_run_id).with_for_update()
        results = await session.exec(q)
        wf = results.first()
        wf.status_date = datetime.datetime.now()
        wf.status = update_status
        if status == RunStatus.COMPLETED or status == RunStatus.FAILED:
            wf.completed_date = datetime.datetime.now()

        session.add(wf)
        return update_status
    return status


async def get_steps_for_batch(batch_id: int) -> list[RunStep]:
    async with get_session() as session:
        q = text(
            f"""select r.* from
               runstep r inner join workflowrun w
               on w.id=r.workflow_run_id
               where batch_id={batch_id}"""
        )
        rs = await session.exec(q)
        res = rs.all()
        if res:
            session.expunge_all()
            return res
        return []


async def get_steps_for_workflow_runs(workflow_run_ids: list[int]) -> dict[int, list[RunStep]]:
    """
    Load steps for multiple workflow runs efficiently.
    Returns dict mapping workflow_run_id -> list[RunStep]
    """
    if not workflow_run_ids:
        return {}

    async with get_session() as session:
        q = select(RunStep).where(RunStep.workflow_run_id.in_(workflow_run_ids))
        rs = await session.exec(q)
        all_steps = rs.all()
        [session.expunge(x) for x in all_steps]

        # Group steps by workflow_run_id
        steps_by_run_id: dict[int, list[RunStep]] = {}
        for step in all_steps:
            if step.workflow_run_id not in steps_by_run_id:
                steps_by_run_id[step.workflow_run_id] = []
            steps_by_run_id[step.workflow_run_id].append(step)

        return steps_by_run_id


async def get_run_steps(status: RunStatus) -> list[RunStep]:
    async with get_session() as session:
        q = select(RunStep).where(RunStep.status == status)
        rs = await session.exec(q)
        res = rs.all()
        [session.expunge(x) for x in res]
        return res


async def get_run_group_durations(run_group_id: int) -> list:
    async with get_session() as session:
        q = text(
            f"""
                 select step_type,count(1) as count,
                 round(max(duration),1) as longest,
                 round(min(duration),1) as shortest,
                 round(avg(duration),1) as average,
                 sum(pages) as pages,
                 round(sum(pages)/sum(duration),0) as pages_per_min,
                 sum(duration) as total_duration,
                 round(extract(epoch from max(completed_date)
                 -min(completed_date)),0) as wall_clock_time
                from
                (select step_type, extract ( epoch  from
                 r.completed_date-r.start_date) as duration,
                 r.start_date, r.completed_date,
                json_query(doc_meta::jsonb,'$.page_count')::int
                 as pages
                from runstep r inner join workflowrun w
                 on w.id=r.workflow_run_id
                inner join documentbatch b on b.id=w.batch_id
                inner join document d on d.hash=w.doc_id
                inner join rungroup rg on rg.id=w.run_group_id
                where rg.id={run_group_id} and r.status ='COMPLETED'
                ) group by step_type;
        """
        )
        rs = await session.exec(q)
        res = rs.all()
        return res


async def get_step_stats(run_group_id: int) -> list():
    async with get_session() as session:
        q = text(
            f"""select b.name,param_definition_id, step_type,
            r.status, count(1),
            sum(json_query(doc_meta::jsonb,'$.page_count')::int)
             as pages
        from runstep r inner join workflowrun w
         on w.id=r.workflow_run_id
        inner join documentbatch b on b.id=w.batch_id
        inner join document d on d.hash=w.doc_id
        inner join rungroup rg on rg.id=w.run_group_id
        where rg.id={run_group_id}
        group by b.name,param_definition_id, step_type,r.status
        order by b.name,step_type,r.status;"""
        )
        rs = await session.exec(q)
        res = rs.all()
        return res


async def reset_failed_steps(run_group_id: int):
    async with get_session() as session:
        q = text(
            f"""update runstep set status='PENDING',retry=0
            where workflow_run_id in
            (select id from workflowrun
             where run_group_id={run_group_id}
             and status='FAILED')"""
        )
        await session.exec(q)
        q = text(
            f"""update workflowrun set status='RUNNING'
            where run_group_id={run_group_id}
            and status='FAILED'"""
        )
        await session.exec(q)
