import base64
import hashlib
import json
import re

import pytest
from ag_ui import core as agui_core

from soliplex import a2ui

RUN_ID = "run-1"
OPERATIONS = [
    {
        "version": "1.0",
        "createSurface": {
            "surfaceId": "s1",
            "catalogId": a2ui.BASIC_CATALOG_ID,
        },
    },
    {
        "version": "1.0",
        "updateComponents": {
            "surfaceId": "s1",
            "components": [{"id": "root", "component": "Text", "text": "hi"}],
        },
    },
]
USER_ACTION = {
    "name": "submit",
    "surfaceId": "s1",
    "sourceComponentId": "submit_button",
    "timestamp": "2026-11-12T10:00:00.000Z",
    "context": {"name": "Ada"},
}


def _run_input(forwarded_props, messages=()):
    return agui_core.RunAgentInput(
        thread_id="thread-1",
        run_id=RUN_ID,
        state={},
        messages=list(messages),
        tools=[],
        context=[],
        forwarded_props=forwarded_props,
    )


def test_surface_event():
    event = a2ui.surface_event("call-1", OPERATIONS)

    assert event == agui_core.ActivitySnapshotEvent(
        message_id="a2ui-surface-call-1",
        activity_type="a2ui-surface",
        content={"a2ui_operations": OPERATIONS},
        replace=True,
    )


def test_apply_user_action_appends_user_message():
    earlier = agui_core.UserMessage(id="m1", content="hello")
    run_input = _run_input(
        {"a2uiAction": {"userAction": USER_ACTION}},
        messages=[earlier],
    )

    found = a2ui.apply_user_action(run_input)

    assert found.messages[0] == earlier
    (_, action_message) = found.messages
    assert action_message.role == "user"
    assert action_message.id == f"a2ui-action-{RUN_ID}"
    digest = hashlib.sha256(RUN_ID.encode()).digest()
    exp_suffix = base64.urlsafe_b64encode(digest).decode().rstrip("=")
    assert action_message.name == f"a2ui_action_context_{exp_suffix}"
    # The pattern '@ag-ui/a2ui-middleware' recognises action messages by.
    assert re.fullmatch(
        r"a2ui_action_context_[A-Za-z0-9_-]{43}", action_message.name
    )
    assert isinstance(action_message.content, str)
    prefix, payload = action_message.content.split("\n", 1)
    assert prefix == "A2UI user action:"
    assert json.loads(payload) == USER_ACTION
    assert run_input.messages == [earlier]


@pytest.mark.parametrize(
    "forwarded_props",
    [
        None,
        "not-a-mapping",
        {},
        {"a2uiAction": "not-a-mapping"},
        {"a2uiAction": {}},
        {"a2uiAction": {"userAction": "not-a-mapping"}},
    ],
)
def test_apply_user_action_without_action(forwarded_props):
    run_input = _run_input(forwarded_props)

    assert a2ui.apply_user_action(run_input) is run_input
