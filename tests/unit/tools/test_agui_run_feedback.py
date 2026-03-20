import contextlib
import datetime
from unittest import mock

import pydantic_ai
import pytest
from ag_ui import core as agui_core

from soliplex import agui as agui_package
from soliplex.agui import persistence as agui_persistence
from soliplex.agui import schema as agui_schema
from soliplex.tools import agui_run_feedback as arf_tools
from tests.unit.agui import agui_constants

FRS = agui_package.FeedbackReviewStatus

NOW = datetime.datetime.now(datetime.UTC)
USER_NAME = "phreddy@example.com"
OTHER_USER_NAME = "bharney@example.com"
ROOM_ID = "test-room-id"
THREAD_ID = "test-thread-id"
RUN_ID = "test-run-id"
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
def ctx_w_deps():
    ctx = mock.Mock(spec_set=["deps"])
    ctx.deps = mock.Mock(
        spec_set=["state", "the_threads"],
        state={},
        the_threads=mock.create_autospec(agui_persistence.ThreadStorage),
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
            agui_package.RunFeedbackReviewEntry,
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
        agui_package.RunFeedback,
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
        agui_package.Thread,
        awaitable_attrs=mock.AsyncMock(),
    )
    thread.awaitable_attrs.user_name = _awaitable("user_name", USER_NAME)
    thread.awaitable_attrs.room_id = _awaitable("room_id", ROOM_ID)
    thread.awaitable_attrs.thread_id = _awaitable("thread_id", THREAD_ID)

    return thread


@pytest.fixture(params=[False, True])
def the_run(request, the_thread, the_run_feedback):
    if request.param:
        run = mock.create_autospec(
            agui_package.Run,
            awaitable_attrs=mock.AsyncMock(),
        )
        run.awaitable_attrs.run_id = _awaitable("run_id", RUN_ID)
        run.awaitable_attrs.thread = _awaitable("thread", the_thread)
        run.awaitable_attrs.run_feedback = _awaitable(
            "run_feedback", the_run_feedback
        )

        return run
    else:
        return None


@pytest.mark.anyio
async def test__do_query(
    the_run,
    the_thread,
    the_run_feedback,
    the_review_entries,
    ctx_w_deps,
):
    lrrf = ctx_w_deps.deps.the_threads.list_recent_run_feedback
    lrrf.return_value = [the_run] if the_run else []

    review_entries, exp_status = the_review_entries

    query = arf_tools.RecentRunFeedbackQuery()

    found = await arf_tools._do_query(ctx_w_deps, query)

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

    if not the_run:  # silence resource warnings for unused fixtures
        await the_thread.awaitable_attrs.user_name
        await the_thread.awaitable_attrs.room_id
        await the_thread.awaitable_attrs.thread_id

        await the_run_feedback.awaitable_attrs.feedback
        await the_run_feedback.awaitable_attrs.reason
        await the_run_feedback.awaitable_attrs.created
        await the_run_feedback.awaitable_attrs.review_history

        for review_entry in review_entries:
            await review_entry.awaitable_attrs.status
            await review_entry.awaitable_attrs.note


@pytest.fixture
def rf_query() -> arf_tools.RecentRunFeedbackQuery:
    return arf_tools.RecentRunFeedbackQuery(user_name=USER_NAME)


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
async def test_query_recent_feedback(do_query, ctx_w_deps, rf_query, w_state):
    query_result = arf_tools.RecentRunFeedbackEntries(
        opened=[
            arf_tools.RunFeedbackEntry(
                user_name=USER_NAME,
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
    )

    deps = ctx_w_deps.deps

    if w_state == "wo_query":
        deps.state[arf_tools.STATE_NAMESPACE] = arf_tools.RecentRunFeedback()
    elif w_state == "diff_query":
        deps.state[arf_tools.STATE_NAMESPACE] = arf_tools.RecentRunFeedback(
            query=arf_tools.RecentRunFeedbackQuery(user_name=OTHER_USER_NAME),
        )
    elif w_state == "same_query":
        deps.state[arf_tools.STATE_NAMESPACE] = arf_tools.RecentRunFeedback(
            query=rf_query.model_copy(),
            entries=query_result,
        )
    else:  # pragma: NO COVER
        pass

    found = await arf_tools.query_recent_feedback(ctx_w_deps, rf_query)

    assert isinstance(found, pydantic_ai.ToolReturn)
    deltas = found.metadata

    assert found.return_value == query_result
    assert deps.state[arf_tools.STATE_NAMESPACE] == exp_state

    do_query.assert_called_once_with(ctx_w_deps, rf_query)

    if w_state == "same_query":
        assert len(deltas) == 0
    else:
        assert len(deltas) == 1


@pytest.fixture
def run_feedback_entry():
    return arf_tools.RunFeedbackEntry(
        user_name=USER_NAME,
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
@mock.patch("soliplex.agui.parser.EventStreamParser")
async def test_get_feedback_run_info(
    esp,
    run_feedback_entry,
    ctx_w_deps,
):
    get_run = ctx_w_deps.deps.the_threads.get_run

    rai = agui_constants.FULL_RUN_AGENT_INPUT.model_copy()
    start_event = agui_core.events.RunStartedEvent(
        thread_id=THREAD_ID,
        run_id=RUN_ID,
    )
    response_start_event = agui_core.events.TextMessageStartEvent(
        message_id=RESPONSE_MESSAGE_ID,
    )
    response_content_event = agui_core.events.TextMessageContentEvent(
        message_id=RESPONSE_MESSAGE_ID,
        delta=RESPONSE_MESSAGE,
    )
    response_end_event = agui_core.events.TextMessageEndEvent(
        message_id=RESPONSE_MESSAGE_ID,
    )
    end_event = agui_core.events.RunFinishedEvent(
        thread_id=THREAD_ID,
        run_id=RUN_ID,
    )
    agui_events = [
        start_event,
        response_start_event,
        response_content_event,
        response_end_event,
        end_event,
    ]

    esp.return_value.messages = [
        agui_core.types.UserMessage(
            id=EARLIER_USER_PROMPT_MESSAGE_ID,
            content=EARLIER_USER_PROMPT,
        ),
        agui_core.types.AssistantMessage(
            id=EARLIER_RESPONSE_MESSAGE_ID,
            content=EARLIER_RESPONSE_MESSAGE,
        ),
        agui_core.types.UserMessage(
            id=USER_PROMPT_MESSAGE_ID,
            content=USER_PROMPT,
        ),
        agui_core.types.AssistantMessage(
            id=RESPONSE_MESSAGE_ID,
            content=RESPONSE_MESSAGE,
        ),
    ]

    db_events = []
    for agui_event in agui_events:
        db_event = mock.create_autospec(agui_schema.RunEvent)
        db_event.to_agui_model.return_value = agui_event
        db_events.append(db_event)

    run = mock.create_autospec(
        agui_package.Run,
        awaitable_attrs=mock.AsyncMock(),
    )
    run.awaitable_attrs.run_agent_input = _awaitable("run_agent_input", rai)
    run.awaitable_attrs.events = _awaitable("events", db_events)
    get_run.return_value = run

    entries = arf_tools.RecentRunFeedbackEntries(
        opened=[run_feedback_entry],
    )
    our_state = arf_tools.RecentRunFeedback(entries=entries)

    deps = ctx_w_deps.deps
    deps.state[arf_tools.STATE_NAMESPACE] = our_state

    found = await arf_tools.get_feedback_run_info(ctx_w_deps, RUN_ID)

    assert isinstance(found, arf_tools.RunFeedbackInfo)

    assert found.user_name == USER_NAME
    assert found.room_id == ROOM_ID
    assert found.thread_id == THREAD_ID
    assert found.run_id == RUN_ID
    assert found.user_prompt == USER_PROMPT
    assert found.agent_response == RESPONSE_MESSAGE

    for agui_event, esp_call in zip(
        agui_events,
        esp.return_value.call_args_list,
        strict=True,
    ):
        assert esp_call == mock.call(agui_event)


@pytest.mark.anyio
async def test__do_review_feedback(
    run_feedback_entry,
    ctx_w_deps,
):
    rvw_rf = ctx_w_deps.deps.the_threads.review_run_feedback

    await arf_tools._do_review_feedback(
        ctx_w_deps,
        run_feedback_entry,
        note=REVIEWED_NOTE,
    )

    rvw_rf.assert_called_once_with(
        note=REVIEWED_NOTE,
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_id=THREAD_ID,
        run_id=RUN_ID,
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "w_run_id, expectation",
    [
        (RUN_ID, contextlib.nullcontext()),
        (OTHER_RUN_ID, pytest.raises(arf_tools.UnknownFeedback)),
    ],
)
@mock.patch("soliplex.tools.agui_run_feedback._do_review_feedback")
async def test_review_recent_feedback(
    do_review,
    ctx_w_deps,
    run_feedback_entry,
    w_run_id,
    expectation,
):
    before_entries = arf_tools.RecentRunFeedbackEntries(
        opened=[run_feedback_entry],
    )
    before_state = arf_tools.RecentRunFeedback(entries=before_entries)

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
    exp_state = arf_tools.RecentRunFeedback(entries=exp_after_entries)

    deps = ctx_w_deps.deps
    deps.state[arf_tools.STATE_NAMESPACE] = before_state.model_copy()

    review = arf_tools.FeedbackReview(run_id=w_run_id, note=REVIEWED_NOTE)

    with expectation as expected:
        found = await arf_tools.review_recent_feedback(ctx_w_deps, review)

    after_state = deps.state[arf_tools.STATE_NAMESPACE]

    if expected is None:
        assert after_state == exp_state

        events = found.metadata

        (event,) = events
        assert len(event.delta) == 2

        d_remove = {
            "op": "remove",
            "path": f"/{arf_tools.STATE_NAMESPACE}/entries/opened/0",
        }
        assert d_remove in event.delta

        d_add = {
            "op": "add",
            "path": f"/{arf_tools.STATE_NAMESPACE}/entries/reviewed/0",
            "value": exp_after_entry.model_dump(mode="json"),
        }
        assert d_add in event.delta

        do_review.assert_called_once_with(
            ctx_w_deps,
            run_feedback_entry,
            note=REVIEWED_NOTE,
        )
    else:
        assert after_state == before_state
        do_review.assert_not_called()


@pytest.mark.anyio
async def test__do_resolve_feedback(
    run_feedback_entry,
    ctx_w_deps,
):
    rsv_rf = ctx_w_deps.deps.the_threads.resolve_run_feedback

    await arf_tools._do_resolve_feedback(
        ctx_w_deps,
        run_feedback_entry,
        note=RESOLVED_NOTE,
    )

    rsv_rf.assert_called_once_with(
        note=RESOLVED_NOTE,
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_id=THREAD_ID,
        run_id=RUN_ID,
    )


@pytest.mark.anyio
@pytest.mark.parametrize("w_reviewed", [False, True])
@pytest.mark.parametrize(
    "w_run_id, expectation",
    [
        (RUN_ID, contextlib.nullcontext()),
        (OTHER_RUN_ID, pytest.raises(arf_tools.UnknownFeedback)),
    ],
)
@mock.patch("soliplex.tools.agui_run_feedback._do_resolve_feedback")
async def test_resolve_recent_feedback(
    do_resolve,
    ctx_w_deps,
    run_feedback_entry,
    w_run_id,
    expectation,
    w_reviewed,
):
    if w_reviewed:
        before_entries = arf_tools.RecentRunFeedbackEntries(
            reviewed=[run_feedback_entry],
        )
    else:
        before_entries = arf_tools.RecentRunFeedbackEntries(
            opened=[run_feedback_entry],
        )
    before_state = arf_tools.RecentRunFeedback(entries=before_entries)

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
    exp_state = arf_tools.RecentRunFeedback(entries=exp_after_entries)

    deps = ctx_w_deps.deps
    deps.state[arf_tools.STATE_NAMESPACE] = before_state.model_copy()

    resolution = arf_tools.FeedbackResolution(
        run_id=w_run_id,
        note=RESOLVED_NOTE,
    )

    with expectation as expected:
        found = await arf_tools.resolve_recent_feedback(
            ctx_w_deps,
            resolution,
        )

    after_state = deps.state[arf_tools.STATE_NAMESPACE]

    if expected is None:
        assert isinstance(found, pydantic_ai.ToolReturn)

        assert found.return_value == exp_state.entries
        assert after_state == exp_state

        events = found.metadata
        (event,) = events
        assert len(event.delta) == 2

        d_remove = {
            "op": "remove",
            "path": (
                f"/{arf_tools.STATE_NAMESPACE}/entries/"
                f"{'reviewed' if w_reviewed else 'opened'}/0"
            ),
        }
        assert d_remove in event.delta

        d_add = {
            "op": "add",
            "path": f"/{arf_tools.STATE_NAMESPACE}/entries/resolved/0",
            "value": exp_after_entry.model_dump(mode="json"),
        }
        assert d_add in event.delta

        do_resolve.assert_called_once_with(
            ctx_w_deps,
            run_feedback_entry,
            note=RESOLVED_NOTE,
        )

    else:
        assert after_state == before_state
        do_resolve.assert_not_called()
