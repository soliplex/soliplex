"""A2UI surfaces over AG-UI

Wire conventions follow `@ag-ui/a2ui-middleware`, so renderers built for it
work against soliplex: a surface travels as an `a2ui-surface` activity, and
a user action comes back in `forwardedProps.a2uiAction.userAction`.
"""

from __future__ import annotations

import base64
import hashlib
import json
import typing

from ag_ui import core as agui_core

ACTIVITY_TYPE = "a2ui-surface"
OPERATIONS_KEY = "a2ui_operations"
BASIC_CATALOG_ID = (
    "https://a2ui.org/specification/v1_0/catalogs/basic/catalog.json"
)
USER_ACTION_PREFIX = "A2UI user action:\n"
# Clients recognise action messages by this name, and may hide them.
USER_ACTION_NAME_PREFIX = "a2ui_action_context_"


def surface_event(
    tool_call_id: str,
    operations: list[dict[str, typing.Any]],
) -> agui_core.ActivitySnapshotEvent:
    """Paint the A2UI operations of one tool call as a single activity"""
    return agui_core.ActivitySnapshotEvent(
        message_id=f"a2ui-surface-{tool_call_id}",
        activity_type=ACTIVITY_TYPE,
        content={OPERATIONS_KEY: operations},
        replace=True,
    )


def apply_user_action(
    run_input: agui_core.RunAgentInput,
) -> agui_core.RunAgentInput:
    """Append the run's A2UI user action, if any, as a user message"""
    forwarded_props = run_input.forwarded_props
    if not isinstance(forwarded_props, dict):
        return run_input

    a2ui_action = forwarded_props.get("a2uiAction")
    if not isinstance(a2ui_action, dict):
        return run_input

    user_action = a2ui_action.get("userAction")
    if not isinstance(user_action, dict):
        return run_input

    digest = hashlib.sha256(run_input.run_id.encode()).digest()
    name_suffix = base64.urlsafe_b64encode(digest).decode().rstrip("=")
    message = agui_core.UserMessage(
        id=f"a2ui-action-{run_input.run_id}",
        name=f"{USER_ACTION_NAME_PREFIX}{name_suffix}",
        content=USER_ACTION_PREFIX
        + json.dumps(user_action, separators=(",", ":")),
    )
    return run_input.model_copy(
        update={"messages": [*run_input.messages, message]},
    )
