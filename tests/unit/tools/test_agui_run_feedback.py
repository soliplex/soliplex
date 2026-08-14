import contextlib
import copy
import datetime
from unittest import mock

import jsonpatch
import pydantic_ai
import pytest
from ag_ui import core as agui_core

from soliplex import agui
from soliplex import models
from soliplex.agui import parser as agui_parser
from soliplex.agui import persistence as agui_persistence
from soliplex.agui import schema as agui_schema
from soliplex.tools import agui_run_feedback as arf_tools
from tests.unit.agui import agui_constants

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
        spec_set=["state", "the_threads", "user"],
        state={},
        the_threads=mock.create_autospec(agui_persistence.ThreadStorage),
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
async def test__do_query(
    the_run,
    the_thread,
    the_run_feedback,
    the_review_entries,
    ctx_w_deps,
    rf_query,
):
    lrrf = ctx_w_deps.deps.the_threads.list_recent_run_feedback
    lrrf.return_value = [the_run] if the_run else []

    review_entries, exp_status = the_review_entries

    found = await arf_tools._do_query(ctx_w_deps, rf_query)

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

    if not the_run:  # silence resource warnings for unused fixtures
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
async def test_query_recent_feedback(do_query, ctx_w_deps, rf_query, w_state):
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

    do_query.assert_called_once_with(ctx_w_deps, rf_query)

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


EMPTY_RUN_MESSAGES = []
ONLY_PROMPT_MESSAGES = [
    agui_core.types.UserMessage(
        id=USER_PROMPT_MESSAGE_ID,
        content=USER_PROMPT,
    ),
]
ONLY_RESPONSE_MESSAGES = [
    agui_core.types.AssistantMessage(
        id=RESPONSE_MESSAGE_ID,
        content=RESPONSE_MESSAGE,
    ),
]
SINGLE_RUN_MESSAGES = ONLY_PROMPT_MESSAGES + ONLY_RESPONSE_MESSAGES
EARLIER_MESSAGES = [
    agui_core.types.UserMessage(
        id=EARLIER_USER_PROMPT_MESSAGE_ID,
        content=EARLIER_USER_PROMPT,
    ),
    agui_core.types.AssistantMessage(
        id=EARLIER_RESPONSE_MESSAGE_ID,
        content=EARLIER_RESPONSE_MESSAGE,
    ),
]
MULTI_RUN_MESSAGES = EARLIER_MESSAGES + SINGLE_RUN_MESSAGES


@pytest.mark.anyio
@pytest.mark.parametrize(
    "messages, run_status, exp_prompt, exp_response",
    [
        # run which never started:  nothing recorded at all
        (EMPTY_RUN_MESSAGES, RS.INITIALIZED, None, None),
        # run which never finished:  no response *yet*
        (ONLY_PROMPT_MESSAGES, RS.RUNNING, USER_PROMPT, None),
        # run which errored before responding
        (ONLY_PROMPT_MESSAGES, RS.ERROR, USER_PROMPT, None),
        # run resumed to supply a tool result (e.g. an approval):  its
        # prompt belongs to an earlier run of the thread
        (ONLY_RESPONSE_MESSAGES, RS.FINISHED, None, RESPONSE_MESSAGE),
        # normal cases:  the *last* exchange of the run
        (SINGLE_RUN_MESSAGES, RS.FINISHED, USER_PROMPT, RESPONSE_MESSAGE),
        (MULTI_RUN_MESSAGES, RS.FINISHED, USER_PROMPT, RESPONSE_MESSAGE),
    ],
)
@mock.patch("soliplex.agui.parser.EventStreamParser")
async def test_get_feedback_run_info(
    esp,
    run_feedback_entry,
    ctx_w_deps,
    the_thread,
    messages,
    run_status,
    exp_prompt,
    exp_response,
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

    esp.return_value.messages = messages
    esp.return_value.run_status = run_status

    db_events = []
    for agui_event in agui_events:
        db_event = mock.create_autospec(agui_schema.RunEvent)
        db_event.to_agui_model.return_value = agui_event
        db_events.append(db_event)

    run = mock.create_autospec(
        agui.Run,
        awaitable_attrs=mock.AsyncMock(),
    )
    run.awaitable_attrs.thread = _awaitable("thread", the_thread)
    run.awaitable_attrs.run_agent_input = _awaitable("run_agent_input", rai)
    run.awaitable_attrs.events = _awaitable("events", db_events)
    get_run.return_value = run

    entries = arf_tools.RecentRunFeedbackEntries(
        opened=[run_feedback_entry],
    )
    our_state = arf_tools.RecentRunFeedback(entries=entries)

    deps = ctx_w_deps.deps
    deps.state[STATE_NAMESPACE] = our_state.model_dump(mode="json")

    found = await arf_tools.get_feedback_run_info(ctx_w_deps, RUN_ID)

    assert isinstance(found, arf_tools.RunFeedbackInfo)

    assert found.user_name == USER_NAME
    assert found.room_id == ROOM_ID
    assert found.thread_id == THREAD_ID
    assert found.run_id == RUN_ID
    assert found.user_prompt == exp_prompt
    assert found.agent_response == exp_response
    assert found.run_status == run_status.name
    assert found.run_status_note == arf_tools.RUN_STATUS_NOTES[run_status]

    for agui_event, esp_call in zip(
        agui_events,
        esp.return_value.call_args_list,
        strict=True,
    ):
        assert esp_call == mock.call(agui_event)

    # silence resource warnings for unused fixtures
    await the_thread.awaitable_attrs.user_name
    await the_thread.awaitable_attrs.room_id
    await the_thread.awaitable_attrs.thread_id


@pytest.mark.anyio
@pytest.mark.parametrize(
    "w_run_id, expectation",
    [
        (RUN_ID, contextlib.nullcontext()),
        (OTHER_RUN_ID, pytest.raises(arf_tools.UnknownFeedback)),
    ],
)
async def test_review_recent_feedback(
    ctx_w_deps,
    run_feedback_entry,
    w_run_id,
    expectation,
):
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

    rvw_rf = deps.the_threads.review_run_feedback

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

    else:
        assert after_feedback_state == before_feedback_state
        rvw_rf.assert_not_awaited()


@pytest.mark.anyio
@pytest.mark.parametrize("w_reviewed", [False, True])
@pytest.mark.parametrize(
    "w_run_id, expectation",
    [
        (RUN_ID, contextlib.nullcontext()),
        (OTHER_RUN_ID, pytest.raises(arf_tools.UnknownFeedback)),
    ],
)
async def test_resolve_recent_feedback(
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

    rsv_rf = ctx_w_deps.deps.the_threads.resolve_run_feedback
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

    else:
        assert after_feedback_state == before_feedback_state
        rsv_rf.assert_not_awaited()
