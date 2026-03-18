import contextlib
import datetime
from unittest import mock

import pydantic_ai
import pytest

from soliplex import agui as agui_package
from soliplex.agui import persistence as agui_persistence
from soliplex.tools import agui_run_feedback as arf_tools

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
