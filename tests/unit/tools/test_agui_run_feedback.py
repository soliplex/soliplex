import contextlib
import copy
import datetime
from unittest import mock

import jsonpatch
import pydantic_ai
import pytest
from ag_ui import core as agui_core
from sqlalchemy.ext import asyncio as sqla_asyncio

from soliplex import agui
from soliplex import models
from soliplex.agui import parser as agui_parser
from soliplex.agui import persistence as agui_persistence
from soliplex.agui import schema as agui_schema
from soliplex.tools import agui_run_feedback as arf_tools

FRS = agui.FeedbackReviewStatus
RS = agui_parser.RunStatus
STATE_NAMESPACE = arf_tools.STATE_NAMESPACE

NOW = datetime.datetime.now(datetime.UTC)
SINCE = NOW - datetime.timedelta(days=1)
LIMIT = 7
USER_NAME = "phreddy"
EMAIL = "phreddy@example.com"
OTHER_USER_NAME = "bharney@example.com"
USER_NAME = "phreddy"
EMAIL = "phreddy@example.com"
OTHER_USER_NAME = "bharney"
OTHER_EMAIL = "bharney@example.com"
ROOM_ID = "test-room-id"
THREAD_ID = "test-thread-id"
RUN_ID = "test-run-id"
PARENT_RUN_ID = "test-parent-run-id"
AGUI_STATE = {"test-namespace": {"test-key": "test-value"}}
THUMBS_UP = "thumbs_up"
REASON = "test-feedback-reason"
REVIEWED_NOTE = "test-feedback-reviewed-note"
RESOLVED_NOTE = "test-feedback-resolved-note"
OTHER_RUN_ID = "test-other-run-id"

NOTES_BY_STATUS = {
    FRS.REVIEWED: REVIEWED_NOTE,
    FRS.RESOLVED: RESOLVED_NOTE,
}

EARLIER_USER_PROMPT_MESSAGE_ID = "message-1234"
EARLIER_USER_PROMPT = "test earlier user prompt"
EARLIER_RESPONSE_MESSAGE_ID = "message-2345"
EARLIER_RESPONSE_MESSAGE = "test earlier response message"
USER_PROMPT_MESSAGE_ID = "message-3456"
USER_PROMPT = "test user prompt"
RESPONSE_MESSAGE_ID = "message-4567"
RESPONSE_MESSAGE = "test response message"


@pytest.fixture
def deps_user():
    return mock.create_autospec(
        models.UserProfile,
        preferred_username=OTHER_USER_NAME,
        email=OTHER_EMAIL,
    )


@pytest.fixture
def ctx_w_deps(deps_user):
    ctx = mock.Mock(spec_set=["deps"])
    ctx.deps = mock.Mock(
        spec_set=["state", "thread_persistence_engine", "user"],
        state={},
        thread_persistence_engine=mock.create_autospec(
            sqla_asyncio.AsyncEngine,
        ),
        user=deps_user,
    )
    return ctx


def _awaitable(name, value):
    async def getter():
        return value

    getter_co = getter()
    getter_co.__qualname__ = f"_awaitable.locals.getter_{name}"
    return getter_co


@pytest.fixture(
    params=[[], [FRS.REVIEWED], [FRS.RESOLVED, FRS.REVIEWED]],
)
def the_review_entries(request):
    entries = []

    exp_status = request.param[0] if request.param else None

    for status in request.param:
        entry = mock.create_autospec(
            agui.RunFeedbackReviewEntry,
            awaitable_attrs=mock.AsyncMock(),
        )
        entry.awaitable_attrs.status = _awaitable("status", status)
        entry.awaitable_attrs.note = _awaitable(
            "note",
            NOTES_BY_STATUS[status],
        )
        entries.append(entry)

    return entries, exp_status


@pytest.fixture
def the_run_feedback(the_review_entries):
    review_history, _ = the_review_entries

    run_feedback = mock.create_autospec(
        agui.RunFeedback,
        awaitable_attrs=mock.AsyncMock(),
    )
    run_feedback.awaitable_attrs.feedback = _awaitable(
        "feedback",
        THUMBS_UP,
    )
    run_feedback.awaitable_attrs.reason = _awaitable("reason", REASON)
    run_feedback.awaitable_attrs.created = _awaitable("created", NOW)
    run_feedback.awaitable_attrs.review_history = _awaitable(
        "review_history",
        review_history,
    )

    return run_feedback


@pytest.fixture
def the_thread():
    thread = mock.create_autospec(
        agui.Thread,
        awaitable_attrs=mock.AsyncMock(),
    )
    thread.awaitable_attrs.user_name = _awaitable("user_name", USER_NAME)
    thread.awaitable_attrs.email = _awaitable("email", EMAIL)
    thread.awaitable_attrs.room_id = _awaitable("room_id", ROOM_ID)
    thread.awaitable_attrs.thread_id = _awaitable("thread_id", THREAD_ID)

    return thread


@pytest.fixture(params=[False, True])
def the_run(request, the_thread, the_run_feedback):
    if request.param:
        run = mock.create_autospec(
            agui.Run,
            awaitable_attrs=mock.AsyncMock(),
        )
        run.awaitable_attrs.run_id = _awaitable("run_id", RUN_ID)
        run.awaitable_attrs.parent_run_id = _awaitable(
            "parent_run_id",
            PARENT_RUN_ID,
        )
        run.awaitable_attrs.run_input = _awaitable(
            "run_input",
            {},
        )
        run.awaitable_attrs.thread = _awaitable("thread", the_thread)
        run.awaitable_attrs.run_feedback = _awaitable(
            "run_feedback", the_run_feedback
        )

        return run
    else:
        return None


@pytest.fixture(
    params=[
        {},
        {"user_name": USER_NAME},
        {"email": EMAIL},
        {"room_id": ROOM_ID},
        {"limit": LIMIT},
        {"since": SINCE},
    ],
)
def rf_query(request) -> arf_tools.RecentRunFeedbackQuery:
    return arf_tools.RecentRunFeedbackQuery(**request.param)


def test_runfeedbackentry_nullable_defaults():
    rfe = arf_tools.RunFeedbackEntry(
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_id=THREAD_ID,
        run_id=RUN_ID,
        created=NOW,
        feedback=THUMBS_UP,
    )

    assert rfe.email is None
    assert rfe.reason is None
    assert rfe.status is None
    assert rfe.note is None


def test_runfeedbackentry_from_dict_wo_nullable_defaults():
    dumped = dict(
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_id=THREAD_ID,
        run_id=RUN_ID,
        created=NOW,
        feedback=THUMBS_UP,
    )

    rfe = arf_tools.RunFeedbackEntry.model_validate(dumped)

    assert rfe.email is None
    assert rfe.reason is None
    assert rfe.status is None
    assert rfe.note is None


@pytest.mark.anyio
@mock.patch("soliplex.agui.persistence.ThreadStorage")
async def test__get_threads_storage(ts_klass, fake_async_session, ctx_w_deps):
    engine = ctx_w_deps.deps.thread_persistence_engine

    with mock.patch(
        "sqlalchemy.ext.asyncio.AsyncSession",
        new=fake_async_session.cls,
    ):
        async with arf_tools._get_threads_storage(ctx_w_deps) as the_threads:
            assert the_threads is ts_klass.return_value

    ts_klass.assert_called_once_with(fake_async_session.session)

    fake_async_session.cls.assert_called_once_with(bind=engine)


@pytest.mark.anyio
async def test__do_query(
    the_run,
    the_thread,
    the_run_feedback,
    the_review_entries,
    ctx_w_deps,
    rf_query,
):
    the_threads = mock.create_autospec(
        agui_persistence.ThreadStorage,
        instance=True,
    )
    lrrf = the_threads.list_recent_run_feedback
    lrrf.return_value = [the_run] if the_run else []

    review_entries, exp_status = the_review_entries

    found = await arf_tools._do_query(the_threads, rf_query)

    if exp_status == FRS.RESOLVED:
        if the_run:
            (entry,) = found.resolved
            assert entry.user_name == USER_NAME
        else:
            assert len(found.resolved) == 0

        assert len(found.reviewed) == 0
        assert len(found.opened) == 0

    elif exp_status == FRS.REVIEWED:
        if the_run:
            (entry,) = found.reviewed
            assert entry.user_name == USER_NAME
        else:
            assert len(found.reviewed) == 0

        assert len(found.resolved) == 0
        assert len(found.opened) == 0
    else:
        assert exp_status is None
        if the_run:
            (entry,) = found.opened
            assert entry.user_name == USER_NAME
        else:
            assert len(found.opened) == 0

        assert len(found.resolved) == 0
        assert len(found.reviewed) == 0

    lrrf.assert_called_once_with(**rf_query.as_kwargs)

    if the_run:  # silence resource warnings for unused fixtures
        await the_run.awaitable_attrs.parent_run_id
        await the_run.awaitable_attrs.run_input
    else:
        await the_thread.awaitable_attrs.user_name
        await the_thread.awaitable_attrs.email
        await the_thread.awaitable_attrs.room_id
        await the_thread.awaitable_attrs.thread_id

        await the_run_feedback.awaitable_attrs.feedback
        await the_run_feedback.awaitable_attrs.reason
        await the_run_feedback.awaitable_attrs.created
        await the_run_feedback.awaitable_attrs.review_history

        for review_entry in review_entries:
            await review_entry.awaitable_attrs.status
            await review_entry.awaitable_attrs.note


@pytest.mark.anyio
@pytest.mark.parametrize(
    "w_state",
    [
        None,
        "wo_query",
        "diff_query",
        "same_query",
    ],
)
@mock.patch("soliplex.tools.agui_run_feedback._do_query")
@mock.patch("soliplex.tools.agui_run_feedback._get_threads_storage")
async def test_query_recent_feedback(
    gts,
    do_query,
    ctx_w_deps,
    rf_query,
    w_state,
):
    the_threads = gts.return_value.__aenter__.return_value

    query_result = arf_tools.RecentRunFeedbackEntries(
        opened=[
            arf_tools.RunFeedbackEntry(
                user_name=USER_NAME,
                email=EMAIL,
                room_id=ROOM_ID,
                thread_id=THREAD_ID,
                run_id=RUN_ID,
                created=NOW,
                feedback=THUMBS_UP,
                reason=REASON,
                status=None,
                note=None,
            ),
        ]
    )
    do_query.return_value = query_result

    exp_state = arf_tools.RecentRunFeedback(
        query=rf_query,
        entries=query_result,
    ).model_dump(mode="json")

    deps = ctx_w_deps.deps

    if w_state == "wo_query":
        init_state = arf_tools.RecentRunFeedback()
    elif w_state == "diff_query":
        init_state = arf_tools.RecentRunFeedback(
            query=arf_tools.RecentRunFeedbackQuery(user_name=OTHER_USER_NAME),
        )
    elif w_state == "same_query":
        init_state = arf_tools.RecentRunFeedback(
            query=rf_query.model_copy(),
            entries=query_result,
        )
    else:
        init_state = None

    if init_state is not None:
        deps.state[STATE_NAMESPACE] = init_state.model_dump(
            mode="json",
        )

    start_agui_state = copy.deepcopy(deps.state)

    found = await arf_tools.query_recent_feedback(ctx_w_deps, rf_query)

    assert isinstance(found, pydantic_ai.ToolReturn)

    assert found.return_value == query_result
    assert deps.state[STATE_NAMESPACE] == exp_state

    do_query.assert_called_once_with(the_threads, rf_query)

    gts.assert_called_once_with(ctx_w_deps)

    deltas = found.metadata

    if w_state == "same_query":
        assert len(deltas) == 0
    else:
        (event,) = deltas
        assert (
            jsonpatch.apply_patch(start_agui_state, event.delta) == deps.state
        )


@pytest.fixture
def run_feedback_entry():
    return arf_tools.RunFeedbackEntry(
        user_name=USER_NAME,
        email=EMAIL,
        room_id=ROOM_ID,
        thread_id=THREAD_ID,
        run_id=RUN_ID,
        created=NOW,
        feedback=THUMBS_UP,
        reason=REASON,
        status=None,
        note=None,
    )


@pytest.mark.parametrize(
    "which, fwa_kw, expectation",
    [
        (None, {}, pytest.raises(arf_tools.UnknownFeedback)),
        (
            "resolved",
            {"from_which_attrs": ["opened", "reviewed"]},
            pytest.raises(arf_tools.UnknownFeedback),
        ),
        (
            "opened",
            {"from_which_attrs": ["opened", "reviewed"]},
            contextlib.nullcontext(),
        ),
        ("reviewed", {}, contextlib.nullcontext()),
    ],
)
def test__find_feedback_by_run_id(
    run_feedback_entry,
    which,
    fwa_kw,
    expectation,
):
    opened = [run_feedback_entry] if which == "opened" else []
    reviewed = [run_feedback_entry] if which == "reviewed" else []
    resolved = [run_feedback_entry] if which == "resolved" else []

    our_state = arf_tools.RecentRunFeedback(
        entries=arf_tools.RecentRunFeedbackEntries(
            opened=opened,
            reviewed=reviewed,
            resolved=resolved,
        ),
    )

    with expectation as expected:
        fb, whence = arf_tools._find_feedback_by_run_id(
            our_state,
            RUN_ID,
            **fwa_kw,
        )

    if expected is None:
        assert fb is run_feedback_entry
        assert whence is getattr(our_state.entries, which)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "w_run_id, expectation",
    [
        (RUN_ID, contextlib.nullcontext()),
        (OTHER_RUN_ID, pytest.raises(arf_tools.UnknownFeedback)),
    ],
)
@mock.patch("soliplex.tools.agui_run_feedback._get_threads_storage")
async def test_review_recent_feedback(
    gts,
    ctx_w_deps,
    run_feedback_entry,
    w_run_id,
    expectation,
):
    the_threads = gts.return_value.__aenter__.return_value
    deps = ctx_w_deps.deps

    before_entries = arf_tools.RecentRunFeedbackEntries(
        opened=[run_feedback_entry],
    )
    before_feedback_state = arf_tools.RecentRunFeedback(
        entries=before_entries,
    ).model_dump(mode="json")

    deps.state[STATE_NAMESPACE] = before_feedback_state
    start_agui_state = copy.deepcopy(deps.state)

    exp_after_entry = run_feedback_entry.model_copy(
        update={
            "status": FRS.REVIEWED,
            "note": REVIEWED_NOTE,
        },
    )
    exp_after_entries = before_entries.model_copy(
        update={
            "opened": [],
            "reviewed": [exp_after_entry],
            "resolved": [],
        },
    )
    exp_state = arf_tools.RecentRunFeedback(
        entries=exp_after_entries,
    ).model_dump(mode="json")

    review = arf_tools.FeedbackReview(run_id=w_run_id, note=REVIEWED_NOTE)

    with expectation as expected:
        found = await arf_tools.review_recent_feedback(ctx_w_deps, review)

    after_feedback_state = deps.state[STATE_NAMESPACE]

    rvw_rf = the_threads.review_run_feedback

    if expected is None:
        assert after_feedback_state == exp_state

        events = found.metadata

        (event,) = events
        assert len(event.delta) == 2

        d_remove = {
            "op": "remove",
            "path": f"/{STATE_NAMESPACE}/entries/opened/0",
        }
        assert d_remove in event.delta

        d_add = {
            "op": "add",
            "path": f"/{STATE_NAMESPACE}/entries/reviewed/0",
            "value": exp_after_entry.model_dump(mode="json"),
        }
        assert d_add in event.delta

        rvw_rf.assert_awaited_once_with(
            reviewer_user_name=OTHER_USER_NAME,
            reviewer_email=OTHER_EMAIL,
            note=REVIEWED_NOTE,
            user_name=USER_NAME,
            room_id=ROOM_ID,
            thread_id=THREAD_ID,
            run_id=RUN_ID,
        )

        deltas = found.metadata

        (event,) = deltas
        assert (
            jsonpatch.apply_patch(start_agui_state, event.delta) == deps.state
        )
        gts.assert_called_once_with(ctx_w_deps)

    else:
        assert after_feedback_state == before_feedback_state
        rvw_rf.assert_not_awaited()
        gts.assert_not_called()


@pytest.mark.anyio
@pytest.mark.parametrize("w_reviewed", [False, True])
@pytest.mark.parametrize(
    "w_run_id, expectation",
    [
        (RUN_ID, contextlib.nullcontext()),
        (OTHER_RUN_ID, pytest.raises(arf_tools.UnknownFeedback)),
    ],
)
@mock.patch("soliplex.tools.agui_run_feedback._get_threads_storage")
async def test_resolve_recent_feedback(
    gts,
    ctx_w_deps,
    run_feedback_entry,
    w_run_id,
    expectation,
    w_reviewed,
):
    the_threads = gts.return_value.__aenter__.return_value

    if w_reviewed:
        before_entries = arf_tools.RecentRunFeedbackEntries(
            reviewed=[run_feedback_entry],
        )
    else:
        before_entries = arf_tools.RecentRunFeedbackEntries(
            opened=[run_feedback_entry],
        )

    before_feedback_state = arf_tools.RecentRunFeedback(
        entries=before_entries,
    ).model_dump(mode="json")

    deps = ctx_w_deps.deps
    deps.state[STATE_NAMESPACE] = before_feedback_state
    start_agui_state = copy.deepcopy(deps.state)

    exp_after_entry = run_feedback_entry.model_copy(
        update={
            "status": FRS.RESOLVED,
            "note": RESOLVED_NOTE,
        },
    )
    exp_after_entries = before_entries.model_copy(
        update={
            "opened": [],
            "reviewed": [],
            "resolved": [exp_after_entry],
        },
    )
    exp_state = arf_tools.RecentRunFeedback(
        entries=exp_after_entries,
    )

    resolution = arf_tools.FeedbackResolution(
        run_id=w_run_id,
        note=RESOLVED_NOTE,
    )

    with expectation as expected:
        found = await arf_tools.resolve_recent_feedback(
            ctx_w_deps,
            resolution,
        )

    after_feedback_state = deps.state[STATE_NAMESPACE]

    rsv_rf = the_threads.resolve_run_feedback
    if expected is None:
        assert isinstance(found, pydantic_ai.ToolReturn)

        assert found.return_value == exp_state.entries
        assert after_feedback_state == exp_state.model_dump(mode="json")

        events = found.metadata
        (event,) = events
        assert len(event.delta) == 2

        d_remove = {
            "op": "remove",
            "path": (
                f"/{STATE_NAMESPACE}/entries/"
                f"{'reviewed' if w_reviewed else 'opened'}/0"
            ),
        }
        assert d_remove in event.delta

        d_add = {
            "op": "add",
            "path": f"/{STATE_NAMESPACE}/entries/resolved/0",
            "value": exp_after_entry.model_dump(mode="json"),
        }
        assert d_add in event.delta

        rsv_rf.assert_awaited_once_with(
            resolver_user_name=OTHER_USER_NAME,
            resolver_email=OTHER_EMAIL,
            note=RESOLVED_NOTE,
            user_name=USER_NAME,
            room_id=ROOM_ID,
            thread_id=THREAD_ID,
            run_id=RUN_ID,
        )

        deltas = found.metadata

        (event,) = deltas
        assert (
            jsonpatch.apply_patch(start_agui_state, event.delta) == deps.state
        )
        gts.assert_called_once_with(ctx_w_deps)

    else:
        assert after_feedback_state == before_feedback_state
        rsv_rf.assert_not_awaited()
        gts.assert_not_called()


IMAGE_CONTENT = agui_core.types.ImageInputContent(
    source=agui_core.types.InputContentUrlSource(
        type="url",
        value="https://example.com/image.png",
    ),
)
TEXT_CONTENT = agui_core.types.TextInputContent(text=USER_PROMPT)


TOOL_CALL_ID = "tool-call-1234"
TOOL_NAME = "search_documents"
TOOL_ARGUMENTS = '{"query": "test query"}'
TOOL_RESULT = "test tool result"
TOOL_ERROR = "test tool error"
TOOL_CALL = agui_core.types.ToolCall(
    id=TOOL_CALL_ID,
    function=agui_core.types.FunctionCall(
        name=TOOL_NAME,
        arguments=TOOL_ARGUMENTS,
    ),
)
EXP_TOOL_CALL = arf_tools.TranscriptToolCall(
    tool_call_id=TOOL_CALL_ID,
    name=TOOL_NAME,
    arguments=TOOL_ARGUMENTS,
)
LIMIT_TOOL_RESULT = "x" * arf_tools.TOOL_RESULT_LIMIT
LONG_TOOL_RESULT = "x" * (arf_tools.TOOL_RESULT_LIMIT + 5)
EXP_LONG_TOOL_RESULT = (
    "x" * arf_tools.TOOL_RESULT_LIMIT + "... [5 characters omitted]"
)


@pytest.mark.parametrize(
    "message, exp_kw",
    [
        (
            agui_core.types.UserMessage(
                id=USER_PROMPT_MESSAGE_ID,
                content=[TEXT_CONTENT, IMAGE_CONTENT],
            ),
            {"role": "user", "content": f"{USER_PROMPT}\n[image]"},
        ),
        (
            agui_core.types.AssistantMessage(
                id=USER_PROMPT_MESSAGE_ID,
                content=RESPONSE_MESSAGE,
            ),
            {"role": "assistant", "content": RESPONSE_MESSAGE},
        ),
        (
            agui_core.types.AssistantMessage(
                id=USER_PROMPT_MESSAGE_ID,
                tool_calls=[TOOL_CALL],
            ),
            {"role": "assistant", "tool_calls": [EXP_TOOL_CALL]},
        ),
        (
            agui_core.types.ToolMessage(
                id=USER_PROMPT_MESSAGE_ID,
                content=TOOL_RESULT,
                tool_call_id=TOOL_CALL_ID,
                error=TOOL_ERROR,
            ),
            {
                "role": "tool",
                "content": TOOL_RESULT,
                "tool_call_id": TOOL_CALL_ID,
                "error": TOOL_ERROR,
            },
        ),
        (
            agui_core.types.ToolMessage(
                id=USER_PROMPT_MESSAGE_ID,
                content=LONG_TOOL_RESULT,
                tool_call_id=TOOL_CALL_ID,
            ),
            {
                "role": "tool",
                "content": EXP_LONG_TOOL_RESULT,
                "tool_call_id": TOOL_CALL_ID,
            },
        ),
        # exactly at the limit:  not cut short
        (
            agui_core.types.ToolMessage(
                id=USER_PROMPT_MESSAGE_ID,
                content=LIMIT_TOOL_RESULT,
                tool_call_id=TOOL_CALL_ID,
            ),
            {
                "role": "tool",
                "content": LIMIT_TOOL_RESULT,
                "tool_call_id": TOOL_CALL_ID,
            },
        ),
        # only tool results are cut short
        (
            agui_core.types.AssistantMessage(
                id=USER_PROMPT_MESSAGE_ID,
                content=LONG_TOOL_RESULT,
            ),
            {"role": "assistant", "content": LONG_TOOL_RESULT},
        ),
    ],
)
def test__transcript_message(message, exp_kw):
    found = arf_tools._transcript_message(message)

    assert found == arf_tools.TranscriptMessage(
        message_id=USER_PROMPT_MESSAGE_ID,
        **exp_kw,
    )


class _AwaitableAttrs:
    """Stand in for an ORM object's 'awaitable_attrs'"""

    def __init__(self, **values):
        self._values = values

    def __getattr__(self, name):
        return _awaitable(name, self._values[name])


def _stored_input(run_id, state, messages):
    """Build a run's input as stored, which is what replay reads"""
    run_input = agui_core.RunAgentInput(
        thread_id=THREAD_ID,
        run_id=run_id,
        state=state,
        messages=messages,
        context=[],
        tools=[],
        forwarded_props=None,
    )
    return agui_schema.RunAgentInput(data=run_input.model_dump())


def _stored_run(run_id, run_input=None, events=(), run_feedback=None):
    """Build a run as stored;  an event given as a dict is its raw data"""
    return mock.Mock(
        spec_set=["awaitable_attrs"],
        awaitable_attrs=_AwaitableAttrs(
            run_id=run_id,
            parent_run_id=PARENT_RUN_IDS.get(run_id),
            created=CREATED[run_id],
            run_agent_input=run_input,
            events=[
                agui_schema.RunEvent(
                    data=e if isinstance(e, dict) else e.model_dump(),
                )
                for e in events
            ],
            run_feedback=run_feedback,
        ),
    )


def _response_events(run_id, message_id, content, *end_events):
    return [
        agui_core.events.RunStartedEvent(thread_id=THREAD_ID, run_id=run_id),
        agui_core.events.TextMessageStartEvent(message_id=message_id),
        agui_core.events.TextMessageContentEvent(
            message_id=message_id,
            delta=content,
        ),
        agui_core.events.TextMessageEndEvent(message_id=message_id),
        *end_events,
    ]


def _finished(run_id):
    return agui_core.events.RunFinishedEvent(
        thread_id=THREAD_ID, run_id=run_id
    )


ORPHAN_RUN_ID = "test-orphan-run-id"
ERRORED_RUN_ID = "test-errored-run-id"
REJECTED_RUN_ID = "test-rejected-run-id"
RESUMED_RUN_ID = "test-resumed-run-id"
NEVER_STARTED_RUN_ID = "test-never-started-run-id"

CREATED = {
    run_id: NOW - datetime.timedelta(minutes=5 * age)
    for age, run_id in enumerate(
        [
            NEVER_STARTED_RUN_ID,
            RUN_ID,
            RESUMED_RUN_ID,
            REJECTED_RUN_ID,
            ERRORED_RUN_ID,
            PARENT_RUN_ID,
            ORPHAN_RUN_ID,
        ]
    )
}
#   Each run continues the one before it, but for the first two.
PARENT_RUN_IDS = {
    ERRORED_RUN_ID: PARENT_RUN_ID,
    REJECTED_RUN_ID: ERRORED_RUN_ID,
    RESUMED_RUN_ID: REJECTED_RUN_ID,
    RUN_ID: RESUMED_RUN_ID,
    NEVER_STARTED_RUN_ID: RUN_ID,
}

EARLIER_AGUI_STATE = {"test-namespace": {"test-key": "earlier-value"}}
REJECTED_AGUI_STATE = {"test-namespace": {"test-key": "rejected-value"}}
THUMBS_DOWN = "thumbs_down"
REJECTED_STEP = "test-no-such-step"

#   Never shown in a transcript.
HIDDEN_ROLE_MESSAGES = [
    agui_core.types.SystemMessage(id="message-system", content="system"),
    agui_core.types.DeveloperMessage(
        id="message-developer",
        content="developer",
    ),
    agui_core.types.ReasoningMessage(
        id="message-reasoning",
        content="reasoning",
    ),
    agui_core.types.ActivityMessage(
        id="message-activity",
        activity_type="test-activity",
        content={"test-key": "test-value"},
    ),
]
EARLIER_PROMPT = agui_core.types.UserMessage(
    id=EARLIER_USER_PROMPT_MESSAGE_ID,
    content=[
        agui_core.types.TextInputContent(text=EARLIER_USER_PROMPT),
        IMAGE_CONTENT,
    ],
)
EXP_EARLIER_PROMPT = f"{EARLIER_USER_PROMPT}\n[image]"
EARLIER_TOOL_CALL = agui_core.types.AssistantMessage(
    id="message-tool-call",
    tool_calls=[TOOL_CALL],
)
EARLIER_TOOL_RESULT = agui_core.types.ToolMessage(
    id="message-tool-result",
    content=TOOL_RESULT,
    tool_call_id=TOOL_CALL_ID,
)
EARLIER_RESPONSE = agui_core.types.AssistantMessage(
    id=EARLIER_RESPONSE_MESSAGE_ID,
    content=EARLIER_RESPONSE_MESSAGE,
)
ERRORED_PROMPT = agui_core.types.UserMessage(
    id="message-errored-prompt",
    content="test errored prompt",
)
REJECTED_PROMPT = agui_core.types.UserMessage(
    id="message-rejected-prompt",
    content="test rejected prompt",
)
REJECTED_RESPONSE = agui_core.types.AssistantMessage(
    id="message-rejected-response",
    content="test rejected response",
)
#   A human-in-the-loop answer, resuming the thread without a prompt.
HITL_ANSWER = agui_core.types.ToolMessage(
    id="message-hitl-answer",
    content="test approval",
    tool_call_id="test-hitl-call",
)
RESUMED_RESPONSE_MESSAGE_ID = "message-resumed-response"
RESUMED_RESPONSE = agui_core.types.AssistantMessage(
    id=RESUMED_RESPONSE_MESSAGE_ID,
    content="test resumed response",
)
PROMPT = agui_core.types.UserMessage(
    id=USER_PROMPT_MESSAGE_ID,
    content=USER_PROMPT,
)

#   Each run's input repeats the thread's history, then adds its own prompt
#   (or a human-in-the-loop answer).
EARLIER_HISTORY = HIDDEN_ROLE_MESSAGES + [
    EARLIER_PROMPT,
    EARLIER_TOOL_CALL,
    EARLIER_TOOL_RESULT,
]
ERRORED_HISTORY = EARLIER_HISTORY + [EARLIER_RESPONSE, ERRORED_PROMPT]
REJECTED_HISTORY = ERRORED_HISTORY + [REJECTED_PROMPT]
RESUMED_HISTORY = REJECTED_HISTORY + [REJECTED_RESPONSE, HITL_ANSWER]
FEEDBACK_HISTORY = RESUMED_HISTORY + [RESUMED_RESPONSE, PROMPT]

#   Recorded against state the run did not have, so cannot be applied.
UNAPPLIABLE_STATE_DELTA = agui_core.events.StateDeltaEvent(
    delta=[{"op": "replace", "path": "/no-such-key/entries", "value": {}}],
)
#   The parser rejects finishing a step which never started.
REJECTED_EVENT = agui_core.events.StepFinishedEvent(step_name=REJECTED_STEP)
#   Matches no known event type, so cannot be read.
UNREADABLE_EVENT_DATA = {"type": "TEST_NO_SUCH_EVENT_TYPE"}


def _feedback_run_feedback():
    return mock.Mock(
        spec_set=["awaitable_attrs"],
        awaitable_attrs=_AwaitableAttrs(feedback=THUMBS_DOWN, reason=REASON),
    )


def _thread_runs():
    """Runs of a thread, as the frontend and agent record them"""

    return [
        # created with the thread, but never used
        _stored_run(ORPHAN_RUN_ID),
        _stored_run(
            PARENT_RUN_ID,
            _stored_input(PARENT_RUN_ID, EARLIER_AGUI_STATE, EARLIER_HISTORY),
            _response_events(
                PARENT_RUN_ID,
                EARLIER_RESPONSE_MESSAGE_ID,
                EARLIER_RESPONSE_MESSAGE,
                _finished(PARENT_RUN_ID),
            ),
        ),
        # errored before replying
        _stored_run(
            ERRORED_RUN_ID,
            _stored_input(ERRORED_RUN_ID, AGUI_STATE, ERRORED_HISTORY),
            [
                agui_core.events.RunStartedEvent(
                    thread_id=THREAD_ID,
                    run_id=ERRORED_RUN_ID,
                ),
                agui_core.events.RunErrorEvent(message="test error"),
            ],
        ),
        # recorded events which cannot all be replayed
        _stored_run(
            REJECTED_RUN_ID,
            _stored_input(REJECTED_RUN_ID, AGUI_STATE, REJECTED_HISTORY),
            [
                agui_core.events.RunStartedEvent(
                    thread_id=THREAD_ID,
                    run_id=REJECTED_RUN_ID,
                ),
                agui_core.events.StateSnapshotEvent(
                    snapshot=REJECTED_AGUI_STATE,
                ),
                UNAPPLIABLE_STATE_DELTA,
                REJECTED_EVENT,
                UNREADABLE_EVENT_DATA,
                agui_core.events.TextMessageStartEvent(
                    message_id=REJECTED_RESPONSE.id,
                ),
                agui_core.events.TextMessageContentEvent(
                    message_id=REJECTED_RESPONSE.id,
                    delta=REJECTED_RESPONSE.content,
                ),
                agui_core.events.TextMessageEndEvent(
                    message_id=REJECTED_RESPONSE.id,
                ),
                _finished(REJECTED_RUN_ID),
            ],
        ),
        _stored_run(
            RESUMED_RUN_ID,
            _stored_input(RESUMED_RUN_ID, AGUI_STATE, RESUMED_HISTORY),
            _response_events(
                RESUMED_RUN_ID,
                RESUMED_RESPONSE_MESSAGE_ID,
                RESUMED_RESPONSE.content,
                _finished(RESUMED_RUN_ID),
            ),
        ),
        _stored_run(
            RUN_ID,
            _stored_input(RUN_ID, AGUI_STATE, FEEDBACK_HISTORY),
            _response_events(
                RUN_ID,
                RESPONSE_MESSAGE_ID,
                RESPONSE_MESSAGE,
                UNAPPLIABLE_STATE_DELTA,
                agui_core.events.RunErrorEvent(message="test error"),
            ),
            run_feedback=_feedback_run_feedback(),
        ),
        # created, but its input never posted
        _stored_run(NEVER_STARTED_RUN_ID),
    ]


def _with_thread(gts, runs):
    the_threads = gts.return_value.__aenter__.return_value
    the_threads.get_thread.return_value = mock.Mock(
        spec_set=["awaitable_attrs"],
        awaitable_attrs=_AwaitableAttrs(email=EMAIL, runs=runs),
    )
    return the_threads


def _with_entry(ctx, entry, which="opened"):
    entries = arf_tools.RecentRunFeedbackEntries(**{which: [entry]})
    our_state = arf_tools.RecentRunFeedback(entries=entries)
    ctx.deps.state[STATE_NAMESPACE] = our_state.model_dump(mode="json")


NEVER_STARTED_NOTE = arf_tools.RUN_STATUS_NOTES[RS.INITIALIZED]
REJECTED_RUN_NOTE = "  ".join(
    [
        arf_tools.RUN_STATUS_NOTES[RS.FINISHED],
        arf_tools.INCOMPLETE_STATE_NOTE.format(count=1),
        arf_tools.SKIPPED_EVENTS_NOTE.format(count=2),
    ]
)
FEEDBACK_RUN_NOTE = "  ".join(
    [
        arf_tools.RUN_STATUS_NOTES[RS.ERROR],
        arf_tools.INCOMPLETE_STATE_NOTE.format(count=1),
    ]
)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "target, exp_prompt, exp_response, exp_status, exp_note, exp_state",
    [
        (ORPHAN_RUN_ID, None, None, "INITIALIZED", NEVER_STARTED_NOTE, {}),
        (
            PARENT_RUN_ID,
            EXP_EARLIER_PROMPT,
            EARLIER_RESPONSE_MESSAGE,
            "FINISHED",
            arf_tools.RUN_STATUS_NOTES[RS.FINISHED],
            EARLIER_AGUI_STATE,
        ),
        # not the earlier run's reply
        (
            ERRORED_RUN_ID,
            ERRORED_PROMPT.content,
            None,
            "ERROR",
            arf_tools.RUN_STATUS_NOTES[RS.ERROR],
            AGUI_STATE,
        ),
        # replayed past the events which could not be
        (
            REJECTED_RUN_ID,
            REJECTED_PROMPT.content,
            REJECTED_RESPONSE.content,
            "FINISHED",
            REJECTED_RUN_NOTE,
            REJECTED_AGUI_STATE,
        ),
        # its prompt is in an earlier run
        (
            RESUMED_RUN_ID,
            None,
            RESUMED_RESPONSE.content,
            "FINISHED",
            arf_tools.RUN_STATUS_NOTES[RS.FINISHED],
            AGUI_STATE,
        ),
        (
            RUN_ID,
            USER_PROMPT,
            RESPONSE_MESSAGE,
            "ERROR",
            FEEDBACK_RUN_NOTE,
            AGUI_STATE,
        ),
        (
            NEVER_STARTED_RUN_ID,
            None,
            None,
            "INITIALIZED",
            NEVER_STARTED_NOTE,
            {},
        ),
    ],
)
@mock.patch("soliplex.tools.agui_run_feedback._get_threads_storage")
async def test_get_feedback_run_info(
    gts,
    run_feedback_entry,
    ctx_w_deps,
    target,
    exp_prompt,
    exp_response,
    exp_status,
    exp_note,
    exp_state,
):
    the_threads = _with_thread(gts, _thread_runs())
    entry = run_feedback_entry.model_copy(update={"run_id": target})
    _with_entry(ctx_w_deps, entry)

    found = await arf_tools.get_feedback_run_info(ctx_w_deps, target)

    the_threads.get_thread.assert_awaited_once_with(
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_id=THREAD_ID,
    )

    assert found == arf_tools.RunFeedbackInfo(
        user_name=USER_NAME,
        email=EMAIL,
        room_id=ROOM_ID,
        thread_id=THREAD_ID,
        run_id=target,
        parent_run_id=PARENT_RUN_IDS.get(target),
        agui_state=exp_state,
        user_prompt=exp_prompt,
        agent_response=exp_response,
        run_status=exp_status,
        run_status_note=exp_note,
    )


@pytest.mark.anyio
@pytest.mark.parametrize("include_agui_state", [False, True])
@pytest.mark.parametrize("include_tool_results", [False, True])
@pytest.mark.parametrize("which", ["opened", "reviewed", "resolved"])
@mock.patch("soliplex.tools.agui_run_feedback._get_threads_storage")
async def test_get_feedback_thread_transcript(
    gts,
    run_feedback_entry,
    ctx_w_deps,
    which,
    include_tool_results,
    include_agui_state,
):
    the_threads = _with_thread(gts, _thread_runs())
    _with_entry(ctx_w_deps, run_feedback_entry, which)

    found = await arf_tools.get_feedback_thread_transcript(
        ctx_w_deps,
        RUN_ID,
        include_tool_results=include_tool_results,
        include_agui_state=include_agui_state,
    )

    the_threads.get_thread.assert_awaited_once_with(
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_id=THREAD_ID,
    )

    assert found.user_name == USER_NAME
    assert found.email == EMAIL
    assert found.room_id == ROOM_ID
    assert found.thread_id == THREAD_ID

    # from the last run with recorded input, not the never-started run
    if include_agui_state:
        assert found.agui_state == AGUI_STATE
        assert found.agui_state_run_id == RUN_ID
    else:
        assert found.agui_state is None
        assert found.agui_state_run_id is None

    def tool_results(*message_ids):
        return list(message_ids) if include_tool_results else []

    # each run holds only the messages first appearing in it
    exp_runs = [
        (ORPHAN_RUN_ID, "INITIALIZED", NEVER_STARTED_NOTE, [], None, None),
        (
            PARENT_RUN_ID,
            "FINISHED",
            arf_tools.RUN_STATUS_NOTES[RS.FINISHED],
            [
                EARLIER_PROMPT.id,
                EARLIER_TOOL_CALL.id,
                *tool_results(EARLIER_TOOL_RESULT.id),
                EARLIER_RESPONSE.id,
            ],
            None,
            None,
        ),
        (
            ERRORED_RUN_ID,
            "ERROR",
            arf_tools.RUN_STATUS_NOTES[RS.ERROR],
            [ERRORED_PROMPT.id],
            None,
            None,
        ),
        (
            REJECTED_RUN_ID,
            "FINISHED",
            REJECTED_RUN_NOTE,
            [REJECTED_PROMPT.id, REJECTED_RESPONSE.id],
            None,
            None,
        ),
        (
            RESUMED_RUN_ID,
            "FINISHED",
            arf_tools.RUN_STATUS_NOTES[RS.FINISHED],
            [*tool_results(HITL_ANSWER.id), RESUMED_RESPONSE.id],
            None,
            None,
        ),
        (
            RUN_ID,
            "ERROR",
            FEEDBACK_RUN_NOTE,
            [PROMPT.id, RESPONSE_MESSAGE_ID],
            THUMBS_DOWN,
            REASON,
        ),
        (
            NEVER_STARTED_RUN_ID,
            "INITIALIZED",
            NEVER_STARTED_NOTE,
            [],
            None,
            None,
        ),
    ]

    assert [(run.parent_run_id, run.created) for run in found.runs] == [
        (PARENT_RUN_IDS.get(run_id), CREATED[run_id])
        for run_id, *_ in exp_runs
    ]

    assert [
        (
            run.run_id,
            run.run_status,
            run.run_status_note,
            [message.message_id for message in run.messages],
            run.feedback,
            run.feedback_reason,
        )
        for run in found.runs
    ] == exp_runs

    _, earlier, *_, feedback_run, _ = found.runs
    assert earlier.messages[0].content == EXP_EARLIER_PROMPT
    assert earlier.messages[1].tool_calls == [EXP_TOOL_CALL]
    assert [message.content for message in feedback_run.messages] == [
        USER_PROMPT,
        RESPONSE_MESSAGE,
    ]


@pytest.mark.anyio
@mock.patch("soliplex.tools.agui_run_feedback._get_threads_storage")
async def test_get_feedback_thread_transcript_w_incomplete_last_input(
    gts,
    run_feedback_entry,
    ctx_w_deps,
):
    # through the run whose events cannot all be replayed
    _with_thread(gts, _thread_runs()[:4])
    entry = run_feedback_entry.model_copy(update={"run_id": PARENT_RUN_ID})
    _with_entry(ctx_w_deps, entry)

    found = await arf_tools.get_feedback_thread_transcript(
        ctx_w_deps,
        PARENT_RUN_ID,
        include_agui_state=True,
    )

    # the state replayed from its events, flagged by its note
    assert found.agui_state == REJECTED_AGUI_STATE
    assert found.agui_state_run_id == REJECTED_RUN_ID
    assert found.runs[-1].run_status_note == REJECTED_RUN_NOTE


@pytest.mark.anyio
@pytest.mark.parametrize(
    "tool",
    [
        arf_tools.get_feedback_run_info,
        arf_tools.get_feedback_thread_transcript,
    ],
)
@mock.patch("soliplex.tools.agui_run_feedback._get_threads_storage")
async def test_feedback_lookup_tools_w_unknown_feedback(
    gts,
    ctx_w_deps,
    run_feedback_entry,
    tool,
):
    _with_entry(ctx_w_deps, run_feedback_entry)

    with pytest.raises(arf_tools.UnknownFeedback):
        await tool(ctx_w_deps, OTHER_RUN_ID)

    gts.assert_not_called()


@pytest.mark.anyio
@pytest.mark.parametrize(
    "tool",
    [
        arf_tools.get_feedback_run_info,
        arf_tools.get_feedback_thread_transcript,
    ],
)
@mock.patch("soliplex.tools.agui_run_feedback._get_threads_storage")
async def test_feedback_lookup_tools_w_deleted_thread(
    gts,
    ctx_w_deps,
    run_feedback_entry,
    tool,
):
    the_threads = gts.return_value.__aenter__.return_value
    the_threads.get_thread.side_effect = agui.UnknownThread(
        USER_NAME,
        THREAD_ID,
    )
    _with_entry(ctx_w_deps, run_feedback_entry)

    # a retry asking the agent to query again, rather than a failed run
    with pytest.raises(arf_tools.UnknownFeedback) as exc_info:
        await tool(ctx_w_deps, RUN_ID)

    assert exc_info.value.run_id == RUN_ID


@pytest.mark.anyio
@mock.patch("soliplex.tools.agui_run_feedback._get_threads_storage")
async def test_get_feedback_run_info_w_run_not_in_thread(
    gts,
    ctx_w_deps,
    run_feedback_entry,
):
    _with_thread(gts, _thread_runs()[:1])
    _with_entry(ctx_w_deps, run_feedback_entry)

    with pytest.raises(arf_tools.UnknownFeedback):
        await arf_tools.get_feedback_run_info(ctx_w_deps, RUN_ID)


@pytest.mark.anyio
@mock.patch("soliplex.tools.agui_run_feedback._get_threads_storage")
async def test_get_feedback_run_info_reads_no_later_runs(
    gts,
    ctx_w_deps,
    run_feedback_entry,
):
    # reading any of its attributes raises
    later_run = mock.Mock(spec_set=[])
    _with_thread(gts, _thread_runs()[:2] + [later_run])
    entry = run_feedback_entry.model_copy(update={"run_id": PARENT_RUN_ID})
    _with_entry(ctx_w_deps, entry)

    found = await arf_tools.get_feedback_run_info(ctx_w_deps, PARENT_RUN_ID)

    assert found.agent_response == EARLIER_RESPONSE_MESSAGE
