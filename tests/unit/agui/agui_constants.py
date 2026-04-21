import uuid

from ag_ui import core as agui_core

THREAD_UUID = str(uuid.uuid4())
THREAD_NAME = "Test Thread"
THREAD_DESCRIPTION = "This thread is for testing"

RUN_UUID = str(uuid.uuid4())
PARENT_RUN_ID = str(uuid.uuid4())
RUN_LABEL = "test-run-label"
OTHER_RUN_LABEL = "other-run-label"

USER_MESSAGE_ID = str(uuid.uuid4())
STATE = {
    "foo": "Bar",
}
USER_PROMPT = "Which way is up?"
USER_MESSAGE = agui_core.UserMessage(
    id=USER_MESSAGE_ID,
    content=USER_PROMPT,
)
CONTEXT_DESC = "This context is for testing"
CONTEXT_VALUE = "Test context"
CONTEXT = agui_core.Context(
    description=CONTEXT_DESC,
    value=CONTEXT_VALUE,
)
TOOL_NAME = "test-tool"
TOOL_DESC = "This tool is for testing"
TOOL = agui_core.Tool(
    name=TOOL_NAME,
    description=TOOL_DESC,
    parameters=None,
)
FORWRDED_PROPS = {
    "spam": "Qux",
}

EMPTY_RUN_AGENT_INPUT = agui_core.RunAgentInput(
    thread_id=THREAD_UUID,
    run_id=RUN_UUID,
    parent_run_id=None,
    state=None,
    messages=[],
    context=[],
    tools=[],
    forwarded_props=None,
)

FULL_RUN_AGENT_INPUT = agui_core.RunAgentInput(
    thread_id=THREAD_UUID,
    run_id=RUN_UUID,
    parent_run_id=PARENT_RUN_ID,
    state=STATE,
    messages=[USER_MESSAGE],
    context=[CONTEXT],
    tools=[TOOL],
    forwarded_props=FORWRDED_PROPS,
)

TEXT_MESSAGE_ID = str(uuid.uuid4())
TEXT_MESSAGE_DELTA = "delta - text"

TEXT_MESSAGE_START_EVENT = agui_core.TextMessageStartEvent(
    message_id=TEXT_MESSAGE_ID,
)

TEXT_MESSAGE_CONTENT_EVENT = agui_core.TextMessageContentEvent(
    message_id=TEXT_MESSAGE_ID,
    delta=TEXT_MESSAGE_DELTA,
)

TEXT_MESSAGE_END_EVENT = agui_core.TextMessageEndEvent(
    message_id=TEXT_MESSAGE_ID,
)

TEXT_MESSAGE_CHUNK_EVENT = agui_core.TextMessageChunkEvent(
    message_id=TEXT_MESSAGE_ID,
    delta=TEXT_MESSAGE_DELTA,
)

THINKING_TEXT_MESSAGE_ID = str(uuid.uuid4())
THINKING_TEXT_MESSAGE_DELTA = "delta - thinking"

THINKING_TEXT_MESSAGE_START_EVENT = agui_core.ThinkingTextMessageStartEvent(
    message_id=THINKING_TEXT_MESSAGE_ID,
)

THINKING_TEXT_MESSAGE_CONTENT_EVENT = (
    agui_core.ThinkingTextMessageContentEvent(
        message_id=THINKING_TEXT_MESSAGE_ID,
        delta=THINKING_TEXT_MESSAGE_DELTA,
    )
)

THINKING_TEXT_MESSAGE_END_EVENT = agui_core.ThinkingTextMessageEndEvent(
    message_id=THINKING_TEXT_MESSAGE_ID,
)

TOOL_CALL_ID = str(uuid.uuid4())
TOOL_CALL_NAME = "test-tool"
TOOL_CALL_ARGS_DELTA = "args delta"
TOOL_CALL_MESSAGE_ID = str(uuid.uuid4())
TOOL_CALL_RESULT_CONTENT = "tool result"

TOOL_CALL_START_EVENT = agui_core.ToolCallStartEvent(
    tool_call_id=TOOL_CALL_ID,
    tool_call_name=TOOL_CALL_NAME,
)

TOOL_CALL_ARGS_EVENT = agui_core.ToolCallArgsEvent(
    tool_call_id=TOOL_CALL_ID,
    delta=TOOL_CALL_ARGS_DELTA,
)

TOOL_CALL_END_EVENT = agui_core.ToolCallEndEvent(
    tool_call_id=TOOL_CALL_ID,
)

EMPTY_TOOL_CALL_CHUNK_EVENT = agui_core.ToolCallChunkEvent(
    tool_call_id=TOOL_CALL_ID,
)
TOOL_CALL_CHUNK_EVENT = agui_core.ToolCallChunkEvent(
    tool_call_id=TOOL_CALL_ID,
    tool_call_name=TOOL_CALL_NAME,
    parent_message_id=TOOL_CALL_MESSAGE_ID,
    delta=TOOL_CALL_ARGS_DELTA,
)

TOOL_CALL_RESULT_EVENT = agui_core.ToolCallResultEvent(
    message_id=TOOL_CALL_MESSAGE_ID,
    tool_call_id=TOOL_CALL_ID,
    content=TOOL_CALL_RESULT_CONTENT,
)

STATE_SNAPTSHOT = {"foo": "Bar", "baz": "Quz"}
STATE_DELTA = {"baz": "Spam"}
STATE_SNAPSHOT_EVENT = agui_core.StateSnapshotEvent(
    snapshot=STATE_SNAPTSHOT,
)

STATE_DELTA_EVENT = agui_core.StateDeltaEvent(
    delta=[STATE_DELTA],
)

DEVELOPER_MESSAGE_ID = str(uuid.uuid4())
DEVELOPER_MESSAGE_CONTENT = "this is a test"
DEVELOPER_MESSAGE_NAME = "phreddy"
DEVELOPER_MESSAGE = agui_core.DeveloperMessage(
    id=DEVELOPER_MESSAGE_ID,
    content=DEVELOPER_MESSAGE_CONTENT,
    name=DEVELOPER_MESSAGE_NAME,
)
EMPTY_MESSAGES_SNAPSHOT_EVENT = agui_core.MessagesSnapshotEvent(
    messages=[],
)
MESSAGES_SNAPSHOT_EVENT = agui_core.MessagesSnapshotEvent(
    messages=[DEVELOPER_MESSAGE],
)

ACTIVITY_MESSAGE_ID = str(uuid.uuid4())
ACTIVITY_TYPE = "test activity"
ACTIVITY_CONTENT = {"waaa": "Blaah"}
ACTIVITY_PATCH = {"waaa": "Oooph"}
ACTIVITY_SNAPSHOT_EVENT = agui_core.ActivitySnapshotEvent(
    message_id=ACTIVITY_MESSAGE_ID,
    activity_type=ACTIVITY_TYPE,
    content=ACTIVITY_CONTENT,
    replace=False,
)

ACTIVITY_DELTA_EVENT = agui_core.ActivityDeltaEvent(
    message_id=ACTIVITY_MESSAGE_ID,
    activity_type=ACTIVITY_TYPE,
    patch=[ACTIVITY_PATCH],
)

RAW_EVENT_EVENT = {"raw": "hide"}
RAW_SOURCE = "raw source"
NO_SOURCE_RAW_EVENT = agui_core.RawEvent(
    event=RAW_EVENT_EVENT,
)
RAW_EVENT = agui_core.RawEvent(
    event=RAW_EVENT_EVENT,
    source=RAW_SOURCE,
)

CUSTOM_NAME = "test-custom"
CUSTOM_VALUE = {"tailor": "made"}
CUSTOM_EVENT = agui_core.CustomEvent(
    name=CUSTOM_NAME,
    value=CUSTOM_VALUE,
)

BARE_RUN_STARTED_EVENT = agui_core.RunStartedEvent(
    thread_id=THREAD_UUID,
    run_id=RUN_UUID,
)

W_PARENT_RUN_ID_RUN_STARTED_EVENT = agui_core.RunStartedEvent(
    thread_id=THREAD_UUID,
    run_id=RUN_UUID,
    parent_run_id=PARENT_RUN_ID,
)

W_RAI_RUN_STARTED_EVENT = agui_core.RunStartedEvent(
    thread_id=THREAD_UUID,
    run_id=RUN_UUID,
    run_agent_input=FULL_RUN_AGENT_INPUT,
)

RUN_RESULT = "test run result"
BARE_RUN_FINISHED_EVENT = agui_core.RunFinishedEvent(
    thread_id=THREAD_UUID,
    run_id=RUN_UUID,
)
W_RESULT_RUN_FINISHED_EVENT = agui_core.RunFinishedEvent(
    thread_id=THREAD_UUID,
    run_id=RUN_UUID,
    result=RUN_RESULT,
)

RUN_ERROR_MESSAGE = "test error"
RUN_CODE = "999"
BARE_RUN_ERROR_EVENT = agui_core.RunErrorEvent(
    message=RUN_ERROR_MESSAGE,
)
W_CODE_RUN_ERROR_EVENT = agui_core.RunErrorEvent(
    message=RUN_ERROR_MESSAGE,
    code=RUN_CODE,
)

STEP_NAME = "test step"
STEP_STARTED_EVENT = agui_core.StepStartedEvent(
    step_name=STEP_NAME,
)

STEP_FINISHED_EVENT = agui_core.StepFinishedEvent(
    step_name=STEP_NAME,
)

TEST_AGUI_RUN_EVENTS = [
    BARE_RUN_STARTED_EVENT,
    STEP_STARTED_EVENT,
    ACTIVITY_SNAPSHOT_EVENT,
    ACTIVITY_DELTA_EVENT,
    STEP_FINISHED_EVENT,
    THINKING_TEXT_MESSAGE_START_EVENT,
    THINKING_TEXT_MESSAGE_CONTENT_EVENT,
    THINKING_TEXT_MESSAGE_END_EVENT,
    TOOL_CALL_START_EVENT,
    TOOL_CALL_ARGS_EVENT,
    TOOL_CALL_END_EVENT,
    TOOL_CALL_RESULT_EVENT,
    TEXT_MESSAGE_START_EVENT,
    TEXT_MESSAGE_CONTENT_EVENT,
    TEXT_MESSAGE_END_EVENT,
    W_RESULT_RUN_FINISHED_EVENT,
]
