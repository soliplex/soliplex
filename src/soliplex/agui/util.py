import datetime
import uuid

from ag_ui import core as agui_core

import soliplex.agui


def _make_uuid_str() -> str:
    return str(uuid.uuid4())


def _timestamp() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)  # noqa UP07


def check_run_input(
    lhs: agui_core.RunAgentInput,
    rhs: agui_core.RunAgentInput,
):
    """Check that a new RAI is compatible with existing RAI

    Raise if IDs do not match:  client's providing a new RAI for an
    existing run may not change these values.
    """
    if lhs is not None:
        if lhs.thread_id != rhs.thread_id:
            raise soliplex.agui.RunInputMismatch("thread_id")

        if lhs.run_id != rhs.run_id:
            raise soliplex.agui.RunInputMismatch("run_id")

        if lhs.parent_run_id != rhs.parent_run_id:
            raise soliplex.agui.RunInputMismatch("parent_run_id")
