import asyncio
import datetime
import inspect
import logging
import random
import uuid

from sqlmodel import select
from sqlmodel import text

from soliplex.ingester.lib.config import get_settings
from soliplex.ingester.lib.models import DocumentBatch
from soliplex.ingester.lib.models import EventHandler
from soliplex.ingester.lib.models import LifeCycleEvent
from soliplex.ingester.lib.models import RunGroup
from soliplex.ingester.lib.models import RunStatus
from soliplex.ingester.lib.models import RunStep
from soliplex.ingester.lib.models import StepConfig
from soliplex.ingester.lib.models import WorkerCheckin
from soliplex.ingester.lib.models import WorkflowDefinition
from soliplex.ingester.lib.models import WorkflowRun
from soliplex.ingester.lib.models import WorkflowStepType
from soliplex.ingester.lib.models import get_session

from . import operations

logger = logging.getLogger(__name__)

_worker_id = None
_task_queue = None
_lock = asyncio.Lock()


class WorkflowException(Exception):
    pass


def do_state_stransition(
    start_status: RunStatus,
    end_status: RunStatus,
    retry: int,
    retries: int,
    step_worker_id: str,
) -> RunStatus:
    if start_status == end_status:
        return start_status
    my_worker_id = get_worker_id()
    if step_worker_id is not None and my_worker_id != step_worker_id:
        # step came from another worker
        if start_status == RunStatus.RUNNING:
            msg = f"running step already assigned to worker {step_worker_id}"
            raise WorkflowException(msg)
    allowed_transitions = [
        (RunStatus.PENDING, RunStatus.RUNNING),
        (RunStatus.RUNNING, RunStatus.COMPLETED),
        (RunStatus.RUNNING, RunStatus.ERROR),
        (RunStatus.ERROR, RunStatus.RUNNING),
    ]
    allowed = False
    for start, end in allowed_transitions:
        if start == start_status and end == end_status:
            allowed = True
            break
    if not allowed:
        msg = f"can't change from {start_status.value} to {end_status.value}"
        raise WorkflowException(msg)

    if end_status == RunStatus.ERROR and retry >= retries:
        logger.info(f"after {retry} retries step  failed")
        end_status = RunStatus.FAILED
    return end_status


async def set_step_status(
    run_step_id: int,
    status: RunStatus,
    message: str | None = None,
    meta: dict[str, str] | None = None,
    increase_retry: bool = False,
) -> RunStep:
    try:
        async with get_session() as session:
            q = select(RunStep).where(RunStep.id == run_step_id).with_for_update()
            timestamp = datetime.datetime.now()
            results = await session.exec(q)
            step = results.first()
            step.status = do_state_stransition(step.status, status, step.retry, step.retries, step.worker_id)
            step.status_date = timestamp
            step.status_message = message
            step.status_meta = meta
            step.worker_id = get_worker_id()

            if step.start_date is None and status == RunStatus.RUNNING:
                step.start_date = timestamp
            if step.completed_date is None and status == RunStatus.COMPLETED:
                step.completed_date = timestamp

            if increase_retry:
                if step.retry >= step.retries:
                    logger.warning(f"step {step.id} already failed {step.retry} times")
                step.retry += 1

            session.add(step)
            await session.flush()
            await operations.update_run_status(step.workflow_run_id, step.is_last_step, step.status, session)

            session.expunge(step)
            await session.commit()

            return step
    except WorkflowException:
        raise
    except Exception as e:
        logger.fatal(
            f"error setting step status {run_step_id} {status} {e} swallowing to keep going",
            exc_info=True,
        )


async def get_runnable_steps(top: int | None = None, batch_id: int | None = None) -> list[RunStep]:
    if top is None:
        top = 100
    async with get_session() as session:
        batch_filt = f" and r.batch_id={batch_id}" if batch_id is not None else ""
        q = text(f"""select * from runstep where (workflow_run_id,workflow_step_number)
        in(
        SELECT s.workflow_run_id,min(workflow_step_number) as min_step FROM runstep
                 s inner join workflowrun r on r.id=s.workflow_run_id
        where s.retry < s.retries and s.status not in
        ('{RunStatus.COMPLETED.value}' ,'{RunStatus.FAILED.value}','{RunStatus.RUNNING.value}')
        and r.status not in ('{RunStatus.COMPLETED.value}' ,'{RunStatus.FAILED.value}')

        {batch_filt}
        group by s.workflow_run_id)
        and status not in ('{RunStatus.RUNNING.value}','{RunStatus.FAILED.value}','{RunStatus.COMPLETED.value}')
        and workflow_run_id not in (select distinct workflow_run_id from runstep where status='{RunStatus.RUNNING.value}')
        order by priority desc,retry,created_date,workflow_step_number limit {top}""")

        rs = await session.exec(q)
        res = rs.all()
        if res:
            session.expunge_all()
            # sqlmodel didn't want to make objects so do manually
            ret = []
            for r in res:
                model_dict = dict(zip(r._fields, r, strict=True))
                model_dict["step_type"] = WorkflowStepType[model_dict["step_type"]]
                model_dict["status"] = RunStatus[model_dict["status"]]
                ret.append(RunStep.model_construct(**model_dict))
            return ret
        return []


def get_lifecycle_event(workflow_def: WorkflowDefinition, evt: LifeCycleEvent) -> list[EventHandler] | None:
    if workflow_def.lifecycle_events is not None:
        return workflow_def.lifecycle_events.get(evt)
    return None


async def handle_lifecycle_event(
    workflow_def: WorkflowDefinition,
    run_step: RunStep,
    workflow_run: WorkflowRun,
    run_group: RunGroup,
):
    if run_step.status == RunStatus.RUNNING:
        await run_lifecycle_event(
            workflow_def,
            run_group,
            workflow_run,
            LifeCycleEvent.STEP_START,
            run_step,
        )
        if run_step.workflow_step_number == 1:
            await run_lifecycle_event(
                workflow_def,
                run_group,
                workflow_run,
                LifeCycleEvent.ITEM_START,
                run_step,
            )
            stats = await operations.get_run_group_stats(run_group.id)
            if (
                stats[RunStatus.RUNNING] == 1
                and stats[RunStatus.COMPLETED] == 0
                and stats[RunStatus.FAILED] == 0
                and stats[RunStatus.ERROR] == 0
            ):
                await run_lifecycle_event(
                    workflow_def,
                    run_group,
                    workflow_run,
                    LifeCycleEvent.GROUP_START,
                    run_step,
                )
    if run_step.status == RunStatus.COMPLETED:
        await run_lifecycle_event(
            workflow_def,
            run_group,
            workflow_run,
            LifeCycleEvent.STEP_END,
            run_step,
        )
        if run_step.is_last_step:
            await run_lifecycle_event(
                workflow_def,
                run_group,
                workflow_run,
                LifeCycleEvent.ITEM_END,
                run_step,
            )
            stats = await operations.get_run_group_stats(run_group.id)
            if stats[RunStatus.RUNNING] == 0 and stats[RunStatus.PENDING] == 0 and stats[RunStatus.ERROR] == 0:
                await run_lifecycle_event(
                    workflow_def,
                    run_group,
                    workflow_run,
                    LifeCycleEvent.GROUP_END,
                    run_step,
                )


async def run_lifecycle_event(
    workflow_def: WorkflowDefinition,
    run_group: RunGroup,
    workflow_run: WorkflowRun,
    event: LifeCycleEvent,
    run_step: RunStep,
):
    evt_list = get_lifecycle_event(workflow_def, event)
    if evt_list is not None and len(evt_list) > 0:
        try:
            await operations.create_lifecycle_history(
                run_group.id,
                workflow_run.id,
                event,
                RunStatus.RUNNING,
                run_step.id,
            )
            step_config = await operations.get_step_config_by_id(run_step.step_config_id)
            for evt in evt_list:
                logger.info(f"executing lifecycle event {evt.name} for {workflow_def.name}")
                res = await build_coro(
                    evt,
                    run_step,
                    workflow_run,
                    workflow_def,
                    step_config,
                    None,
                    run_group,
                )
                if res is None or not isinstance(res, dict):
                    res = {}
                elif not isinstance(res, dict):
                    res = {"result": str(res)}
            await operations.update_lifecycle_history(
                run_group.id,
                workflow_run.id,
                event,
                RunStatus.COMPLETED,
                run_step.id,
                status_meta=res,
            )
        except Exception as e:
            logger.exception(f"step start {workflow_run.doc_id} failed", exc_info=e)
            try:
                await operations.update_lifecycle_history(
                    run_group.id,
                    workflow_run.id,
                    event,
                    RunStatus.FAILED,
                    run_step.id,
                    status_meta={"error": str(e)},
                    status_message=str(e),
                )
            except Exception:
                logger.exception("update lifecycle history failed", exc_info=e)


async def run_wf_step(run_step: RunStep, coro_id: int = None):
    lc = {"coro_id": coro_id, "worker_id": get_worker_id()}
    try:
        workflow_run = await operations.get_workflow_run(run_step.workflow_run_id)
        run_group = await operations.get_run_group(workflow_run.run_group_id)
        workflow_def = await operations.get_workflow_definition(workflow_run.workflow_definition_id)
        step_config = await operations.get_step_config_by_id(run_step.step_config_id)
        batch = await operations.get_batch(workflow_run.batch_id)

        logger.info(
            f"cid={coro_id} running step {run_step.workflow_step_number} ({run_step.workflow_step_name})"
            f" in workflow {workflow_def.name} priority={run_step.priority}"
            f" attempt={run_step.retry}/{run_step.retries}",
            extra=lc,
        )
        await handle_lifecycle_event(workflow_def, run_step, workflow_run, run_group)
        res = await build_step_coro(run_step, workflow_run, workflow_def, step_config, batch, run_group)
        if isinstance(res, str):
            logger.info(
                f"cid={coro_id} step {run_step.workflow_step_number} returned {res}",
                extra=lc,
            )
        else:
            res = str(res)

        upd_step = await set_step_status(
            run_step.id,
            status=RunStatus.COMPLETED,
            increase_retry=False,
            message="success",
            meta={"coro_id": coro_id},
        )

        await handle_lifecycle_event(workflow_def, upd_step, workflow_run, run_group)

    except Exception as e:
        logger.exception(
            f"error in step {run_step.workflow_step_number}",
            exc_info=e,
            extra=lc,
        )
        try:
            upd_step = await set_step_status(
                run_step.id,
                RunStatus.ERROR,
                f"exception: {e}",
                meta={"coro_id": coro_id},
            )
            await handle_lifecycle_event(workflow_def, upd_step, workflow_run, run_group)

        except Exception as e2:
            logger.exception(
                f"error setting step status to error {run_step.workflow_step_number}",
                exc_info=e2,
                extra=lc,
            )
        return RunStatus.FAILED
    else:
        return RunStatus.COMPLETED


def build_step_coro(
    run_step: RunStep,
    workflow_run: WorkflowRun,
    workflow_def: WorkflowDefinition,
    step_config: StepConfig,
    batch: DocumentBatch,
    run_group: RunGroup,
):
    """
    Build a coroutine from a workflow context"""
    workflow_handler = workflow_def.item_steps[step_config.step_type]
    return build_coro(
        workflow_handler,
        run_step,
        workflow_run,
        workflow_def,
        step_config,
        batch,
        run_group,
    )


def build_coro(
    handler: EventHandler,
    run_step: RunStep,
    workflow_run: WorkflowRun,
    workflow_def: WorkflowDefinition,
    step_config: StepConfig,
    batch: DocumentBatch,
    run_group: RunGroup,
    extra_args: dict | None = None,
):
    fn = handler.method
    sig = inspect.signature(fn)
    batch_source = None
    batch_id = None
    if batch is not None:
        batch_source = batch.source
        batch_id = batch.id

    ns = {
        "run_step": run_step,
        "workflow_run": workflow_run,
        "workflow_def": workflow_def,
        "step_config": step_config,
        "batch_id:": batch_id,
        "doc_hash": workflow_run.doc_id,
        "source": batch_source,
        "run_group": run_group,
    }

    ns.update(workflow_run.run_params)
    ns.update(handler.parameters)
    if extra_args is not None:
        ns.update(extra_args)
    call = {}
    for k in sig.parameters.keys():
        if k in ns:
            call[k] = ns[k]

    return fn(**call)


async def _worker_checkin():
    settings = get_settings()
    while True:
        await worker_checkin(get_worker_id())
        await asyncio.sleep(settings.worker_checkin_interval)


def get_worker_id():
    return _worker_id


async def start_worker(create_tasks=True):
    global _worker_id
    global _task_queue
    settings = get_settings()
    if _worker_id is not None:
        return
    _worker_id = str(uuid.uuid4())
    task_count = settings.worker_task_count
    _task_queue = asyncio.Queue(maxsize=task_count)
    if create_tasks:
        asyncio.create_task(_worker_checkin())
        asyncio.create_task(check_dead_workers())
        asyncio.create_task(queue_tasks())
        for i in range(task_count):
            asyncio.create_task(consume_tasks(i))
    logger.info(f"started worker {_worker_id} with {task_count} tasks")


async def consume_tasks(coro_id: int):
    global _task_queue
    lc = {"coro_id": coro_id, "worker_id": get_worker_id()}
    if _task_queue is None:
        logger.warning("worker not started")
        return

    while True:
        run_step = None
        task_num = await _task_queue.get()
        async with _lock:
            logger.debug(
                f"cid={coro_id} worker queue task get {task_num}",
                extra=lc,
            )
            avail_steps = await get_runnable_steps(top=1)
            if len(avail_steps) != 0:
                run_step = avail_steps[0]
                logger.info(
                    f"worker cid={coro_id} queue task  got run_id={run_step.workflow_run_id} "
                    + f"  {run_step.workflow_step_number} from queue {run_step.status}",
                    extra=lc,
                )

                updated_step = await set_step_status(
                    run_step.id,
                    RunStatus.RUNNING,
                    increase_retry=True,
                    meta={"coro_id": coro_id},
                )
                run_step = updated_step

        if run_step:
            logger.debug(
                f"worker cid={coro_id} running step " + f"{run_step.workflow_run_id} {run_step.workflow_step_number}",
                extra=lc,
            )

            status = await run_wf_step(run_step, coro_id)
            logger.debug(
                f"worker cid={coro_id} finished step" + f" {run_step.workflow_run_id} {run_step.workflow_step_number}",
                extra=lc,
            )
            if status == RunStatus.FAILED:
                await asyncio.sleep(2)


async def queue_tasks():
    global _task_queue
    settings = get_settings()
    if _task_queue is None:
        logger.warning("worker not started")
        return
    task_ct = 0
    while True:
        try:
            if _task_queue.qsize() >= settings.worker_task_count:
                await asyncio.sleep(1)
                continue
            await _task_queue.put(task_ct)
            logger.debug(f"queue task put {task_ct} curr={_task_queue.qsize()},'worker_id {get_worker_id()}'")
            task_ct += 1

        except Exception as e:
            logger.exception(
                "failed to queue task",
                exc_info=e,
                extra={"worker_id": get_worker_id()},
            )
            return


async def worker_checkin(worker_id: str):
    try:
        async with get_session() as session:
            checkin = datetime.datetime.now()
            logger.info(f"worker {worker_id} checkin {checkin}")
            q = select(WorkerCheckin).where(WorkerCheckin.id == worker_id)
            rs = await session.exec(q)
            res = rs.first()
            if res:
                res.last_checkin = checkin
                session.add(res)
            else:
                session.add(
                    WorkerCheckin(
                        id=worker_id,
                        last_checkin=checkin,
                        first_checkin=checkin,
                    )
                )
            await session.commit()
    except Exception as e:
        logger.exception(f"worker {worker_id} checkin failed", exc_info=e)


async def check_dead_workers():
    settings = get_settings()
    while True:
        try:
            checkin_interval = settings.worker_checkin_timeout
            await asyncio.sleep(checkin_interval)
            logger.info(f"checking for dead workers every {checkin_interval} seconds")
            # add a random delay to avoid herding
            last_checkin_time = datetime.datetime.now() - datetime.timedelta(
                seconds=checkin_interval + (random.randint(1, 20) / 10)
            )
            async with get_session() as session:
                q = select(WorkerCheckin).where(WorkerCheckin.last_checkin < last_checkin_time)
                results = await session.exec(q)
                results = results.all()
                for worker in results:
                    logger.info(
                        f"worker {worker.id} last checkin {worker.last_checkin}"
                        + f" dead for {datetime.datetime.now() - worker.last_checkin} - removing"
                    )
                    # remove the checkin
                    await session.delete(worker)
                    q2 = select(RunStep).where(RunStep.worker_id == worker.id).where(RunStep.status != RunStatus.COMPLETED)
                    step_results = await session.exec(q2)
                    step_results = step_results.all()
                    logger.info(f"removing {len(step_results)} steps from worker {worker.id}")
                    # find any steps that were running on this worker and free them up by setting back to pending
                    # and clearing worker id
                    for step in step_results:
                        step.worker_id = None
                        if step.status == RunStatus.RUNNING:
                            step.status = RunStatus.PENDING
                        session.add(step)

                await session.commit()
        except Exception as e:
            logger.exception(
                "error checking for dead workers",
                exc_info=e,
                extra={"worker_id": get_worker_id()},
            )
