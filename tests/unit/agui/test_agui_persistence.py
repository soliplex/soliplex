import datetime
from types import SimpleNamespace
from unittest import mock

import pytest
import pytest_asyncio
from ag_ui import core as agui_core
from sqlalchemy import exc as sqla_exc
from sqlalchemy.ext import asyncio as sqla_asyncio

from soliplex import agui
from soliplex.agui import persistence as agui_persistence
from soliplex.agui import schema as agui_schema
from soliplex.config import installation as config_installation
from tests.unit.agui import agui_constants

FeedbackReviewStatus = agui.FeedbackReviewStatus

NOW = datetime.datetime.now(datetime.UTC)

ROOM_ID = "test-room"
ROOM_ID_2 = "test-room-2"
USER_NAME = "phreddy"
EMAIL = "phreddy@example.com"
OTHER_USER_NAME = "wylma"
OTHER_EMAIL = "wylma@example.com"
T_OLD = datetime.datetime(2026, 1, 1, 10, 0, tzinfo=datetime.UTC)
T_MID = datetime.datetime(2026, 1, 1, 11, 0, tzinfo=datetime.UTC)
T_NEW = datetime.datetime(2026, 1, 1, 12, 0, tzinfo=datetime.UTC)
REVIEWER_USER_NAME = "bharney"
REVIEWER_EMAIL = "bharney@example.com"
RESOLVER_USER_NAME = "wylma"
RESOLVER_EMAIL = "wylma@example.com"


@pytest.fixture
def faux_sqlaa_session():
    return mock.create_autospec(
        sqla_asyncio.AsyncSession,
    )


@pytest.mark.anyio
async def test_threadstorage_session(faux_sqlaa_session):
    ts = agui_persistence.ThreadStorage(faux_sqlaa_session)

    async with ts.session as session:
        entered = session

    # The session property is a passthrough: it yields the caller-owned
    # session unchanged and never opens its own transaction. The session
    # owner owns the commit boundary.
    assert entered is faux_sqlaa_session
    faux_sqlaa_session.begin.assert_not_called()


@pytest_asyncio.fixture()
async def the_async_engine():
    engine = sqla_asyncio.create_async_engine(
        config_installation.ASYNC_MEMORY_ENGINE_URL,
    )
    async with engine.begin() as connection:
        await connection.run_sync(agui_schema.Base.metadata.create_all)

    yield engine

    await engine.dispose()


@pytest_asyncio.fixture()
async def the_async_session(the_async_engine):
    session = sqla_asyncio.AsyncSession(bind=the_async_engine)
    yield session
    await session.close()


async def _add_run(
    ts,
    session,
    *,
    user_name,
    email,
    room_id,
    created,
    finished=None,
    thread_id=None,
):
    """Create a run with explicit 'created'/'finished' timestamps.

    A new thread is created (with its initial run) unless 'thread_id' is
    given, in which case the run is added to that thread. Returns the
    thread_id so callers can stack more runs onto the same thread.
    """
    if thread_id is None:
        thread = await ts.new_thread(
            user_name=user_name,
            email=email,
            room_id=room_id,
        )
        thread_id = await thread.awaitable_attrs.thread_id
        (run,) = await thread.list_runs()
    else:
        run = await ts.new_run(
            user_name=user_name,
            room_id=room_id,
            thread_id=thread_id,
        )

    run.created = created
    run.finished = finished

    return thread_id


@pytest.mark.asyncio
async def test_threadstorage_thread_crud(the_async_session, unit_of_work):
    ts = agui_persistence.ThreadStorage(the_async_session)

    found = (await ts.list_user_threads(user_name=USER_NAME)).all()
    assert found == []

    found = (
        await ts.list_user_threads(user_name=USER_NAME, room_id=ROOM_ID)
    ).all()
    assert found == []

    with pytest.raises(agui.UnknownThread):
        await ts.get_thread(
            user_name=USER_NAME,
            room_id=ROOM_ID,
            thread_id="NONESUCH",
        )

    thread = await ts.new_thread(
        user_name=USER_NAME,
        email=EMAIL,
        room_id=ROOM_ID,
    )

    thread_id = await thread.awaitable_attrs.thread_id

    found = (await ts.list_user_threads(user_name=USER_NAME)).all()
    assert found == [thread]

    found = (
        await ts.list_user_threads(user_name=USER_NAME, room_id=ROOM_ID)
    ).all()
    assert found == [thread]

    with pytest.raises(agui.ThreadRoomMismatch):
        await ts.get_thread(
            user_name=USER_NAME,
            room_id="NONESUCH",
            thread_id=thread_id,
        )

    gotten = await ts.get_thread(
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_id=thread_id,
    )

    assert gotten is thread

    with pytest.raises(agui.ThreadRoomMismatch):
        await ts.update_thread_metadata(
            user_name=USER_NAME,
            thread_id=thread_id,
            room_id="NONESUCH",
            thread_metadata={
                "name": agui_constants.THREAD_NAME,
                "description": agui_constants.THREAD_DESCRIPTION,
            },
        )

    updated = await ts.update_thread_metadata(
        user_name=USER_NAME,
        thread_id=thread_id,
        room_id=ROOM_ID,
        thread_metadata={
            "name": agui_constants.THREAD_NAME,
            "description": agui_constants.THREAD_DESCRIPTION,
        },
    )

    assert updated is thread

    thread_meta = await updated.awaitable_attrs.thread_metadata

    assert thread_meta.name == agui_constants.THREAD_NAME
    assert thread_meta.description == agui_constants.THREAD_DESCRIPTION

    updated_again = await ts.update_thread_metadata(
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_id=thread_id,
        thread_metadata=agui_schema.ThreadMetadata(
            name=agui_constants.THREAD_NAME,
        ),
    )

    assert updated_again is thread

    thread_meta = await updated.awaitable_attrs.thread_metadata

    assert thread_meta.name == agui_constants.THREAD_NAME
    assert thread_meta.description is None

    async with unit_of_work():
        cleared = await ts.update_thread_metadata(
            user_name=USER_NAME,
            room_id=ROOM_ID,
            thread_id=thread_id,
            thread_metadata=None,
        )

    assert cleared is thread

    thread_meta = await updated.awaitable_attrs.thread_metadata
    assert thread_meta is None

    async with unit_of_work():
        cleared_again = await ts.update_thread_metadata(
            user_name=USER_NAME,
            room_id=ROOM_ID,
            thread_id=thread_id,
            thread_metadata=None,
        )

    assert cleared_again is thread

    thread_meta = await updated.awaitable_attrs.thread_metadata
    assert thread_meta is None

    with pytest.raises(agui.ThreadRoomMismatch):
        await ts.delete_thread(
            user_name=USER_NAME,
            room_id="NONESUCH",
            thread_id=thread_id,
        )

    await ts.delete_thread(
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_id=thread_id,
    )

    found = (await ts.list_user_threads(user_name=USER_NAME)).all()
    assert found == []

    found = (
        await ts.list_user_threads(user_name=USER_NAME, room_id=ROOM_ID)
    ).all()
    assert found == []

    w_md_dict = await ts.new_thread(
        user_name=USER_NAME,
        email=EMAIL,
        room_id=ROOM_ID,
        thread_metadata={
            "name": "w_md_dict",
            "description": "Created with metadata as a dict",
        },
    )

    await w_md_dict.awaitable_attrs.thread_id

    tmd = await w_md_dict.awaitable_attrs.thread_metadata
    assert tmd.name == "w_md_dict"
    assert tmd.description == "Created with metadata as a dict"

    w_md_obj = await ts.new_thread(
        user_name=USER_NAME,
        email=EMAIL,
        room_id=ROOM_ID,
        thread_metadata=agui_schema.ThreadMetadata(
            name="w_md_obj",
            description="Created with metadata as an object",
        ),
    )

    await w_md_obj.awaitable_attrs.thread_id

    tmd = await w_md_obj.awaitable_attrs.thread_metadata
    assert tmd.name == "w_md_obj"
    assert tmd.description == "Created with metadata as an object"


@pytest.mark.asyncio
async def test_threadstorage_thread_run_cru(the_async_session, unit_of_work):
    ts = agui_persistence.ThreadStorage(the_async_session)

    thread = await ts.new_thread(
        user_name=USER_NAME,
        email=EMAIL,
        room_id=ROOM_ID,
    )

    thread_id = await thread.awaitable_attrs.thread_id

    runs = await thread.list_runs()

    (initial_run,) = runs

    initial_run_id = await initial_run.awaitable_attrs.run_id

    assert await initial_run.awaitable_attrs.thread_id == thread_id
    assert await initial_run.awaitable_attrs.run_input is None

    assert initial_run in await thread.awaitable_attrs.runs

    found = await thread.list_runs()

    assert found == runs

    rai_added = await ts.add_run_input(
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_id=thread_id,
        run_id=initial_run_id,
        run_input=agui_constants.FULL_RUN_AGENT_INPUT,
    )

    assert rai_added is initial_run

    assert (
        await initial_run.awaitable_attrs.run_input
        == agui_constants.FULL_RUN_AGENT_INPUT
    )

    with pytest.raises(agui.RunAlreadyStarted):
        await ts.add_run_input(
            user_name=USER_NAME,
            room_id=ROOM_ID,
            thread_id=thread_id,
            run_id=initial_run_id,
            run_input=agui_constants.FULL_RUN_AGENT_INPUT,
        )

    gotten = await ts.get_run(
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_id=thread_id,
        run_id=initial_run_id,
    )

    assert gotten is initial_run

    with pytest.raises(agui.UnknownRun):
        await ts.get_run(
            user_name=USER_NAME,
            room_id=ROOM_ID,
            thread_id=thread_id,
            run_id="NONESUCH",
        )

    added = await ts.new_run(
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_id=thread_id,
        run_metadata={"label": "added"},
    )
    added_id = await added.awaitable_attrs.run_id

    updated = await ts.update_run_metadata(
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_id=thread_id,
        run_id=added_id,
        run_metadata={
            "label": agui_constants.RUN_LABEL,
        },
    )

    assert updated is added

    rmd = await updated.awaitable_attrs.run_metadata
    assert rmd.label == agui_constants.RUN_LABEL

    updated_again = await ts.update_run_metadata(
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_id=thread_id,
        run_id=added_id,
        run_metadata=agui_schema.RunMetadata(
            label=agui_constants.OTHER_RUN_LABEL,
        ),
    )

    assert updated_again is added

    rmd = await updated_again.awaitable_attrs.run_metadata
    assert rmd.label == agui_constants.OTHER_RUN_LABEL

    async with unit_of_work():
        cleared = await ts.update_run_metadata(
            user_name=USER_NAME,
            room_id=ROOM_ID,
            thread_id=thread_id,
            run_id=added_id,
            run_metadata=None,
        )

    assert cleared is added

    assert await cleared.awaitable_attrs.run_metadata is None

    async with unit_of_work():
        cleared_again = await ts.update_run_metadata(
            user_name=USER_NAME,
            room_id=ROOM_ID,
            thread_id=thread_id,
            run_id=added_id,
            run_metadata=None,
        )

    assert cleared_again is added

    assert await cleared_again.awaitable_attrs.run_metadata is None

    parent = await ts.new_run(
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_id=thread_id,
        run_metadata=agui_schema.RunMetadata(label="parent"),
    )

    parent_id = await parent.awaitable_attrs.run_id

    spare = await ts.new_run(
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_id=thread_id,
        run_metadata=agui_schema.RunMetadata(label="spare"),
        parent_run_id=parent_id,
    )
    await spare.awaitable_attrs.run_id

    rmd = await spare.awaitable_attrs.run_metadata
    assert rmd.label == "spare"

    assert await spare.awaitable_attrs.parent is parent

    wo_meta = await ts.new_run(
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_id=thread_id,
    )

    rmd = await wo_meta.awaitable_attrs.run_metadata
    assert rmd is None

    before = await ts.new_run(
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_id=thread_id,
    )

    before_id = await before.awaitable_attrs.run_id

    usage = await before.awaitable_attrs.run_usage
    assert usage is None

    await ts.save_run_usage(
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_id=thread_id,
        run_id=before_id,
        input_tokens=1,
        output_tokens=2,
        requests=3,
        tool_calls=4,
    )

    after = await ts.get_run(
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_id=thread_id,
        run_id=before_id,
    )

    after_usage = await after.awaitable_attrs.run_usage

    assert after_usage.input_tokens == 1
    assert after_usage.output_tokens == 2
    assert after_usage.requests == 3
    assert after_usage.tool_calls == 4


@pytest.mark.asyncio
async def test_threadstorage_thread_run_feedback(
    the_async_session, unit_of_work
):
    ts = agui_persistence.ThreadStorage(the_async_session)

    thread = await ts.new_thread(
        user_name=USER_NAME,
        email=EMAIL,
        room_id=ROOM_ID,
    )
    thread_id = await thread.awaitable_attrs.thread_id

    runs = await thread.list_runs()

    (initial_run,) = runs
    before_id = await initial_run.awaitable_attrs.run_id

    pre_feedback = await ts.get_run_feedback(
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_id=thread_id,
        run_id=before_id,
    )
    assert pre_feedback is None

    await ts.save_run_feedback(
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_id=thread_id,
        run_id=before_id,
        feedback="thumbs_up",
        reason="just because",
    )

    run_feedback = await ts.get_run_feedback(
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_id=thread_id,
        run_id=before_id,
    )

    assert await run_feedback.awaitable_attrs.feedback == "thumbs_up"
    assert await run_feedback.awaitable_attrs.reason == "just because"

    await ts.save_run_feedback(
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_id=thread_id,
        run_id=before_id,
        feedback="thumbs_down",
        reason="dithering",
    )

    moar_run_feedback = await ts.get_run_feedback(
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_id=thread_id,
        run_id=before_id,
    )

    assert await moar_run_feedback.awaitable_attrs.feedback == "thumbs_down"
    assert await moar_run_feedback.awaitable_attrs.reason == "dithering"

    added = await ts.new_run(
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_id=thread_id,
    )
    added_id = await added.awaitable_attrs.run_id

    await ts.save_run_feedback(
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_id=thread_id,
        run_id=added_id,
        feedback="thumbs_up",
        reason="fresh",
    )

    # Default query
    later, earlier = await ts.list_recent_run_feedback()

    later_fb = await later.awaitable_attrs.run_feedback
    assert await later_fb.awaitable_attrs.feedback == "thumbs_up"
    assert await later_fb.awaitable_attrs.reason == "fresh"

    earlier_fb = await earlier.awaitable_attrs.run_feedback
    assert await earlier_fb.awaitable_attrs.feedback == "thumbs_down"
    assert await earlier_fb.awaitable_attrs.reason == "dithering"

    # Query with 'since'
    when = await added.awaitable_attrs.created
    (only,) = await ts.list_recent_run_feedback(since=when)

    only_fb = await only.awaitable_attrs.run_feedback
    assert await only_fb.awaitable_attrs.feedback == "thumbs_up"
    assert await only_fb.awaitable_attrs.reason == "fresh"

    # Query with 'explicit limit'
    (lonely,) = await ts.list_recent_run_feedback(since=when)

    lonely_fb = await lonely.awaitable_attrs.run_feedback
    assert await lonely_fb.awaitable_attrs.feedback == "thumbs_up"
    assert await lonely_fb.awaitable_attrs.reason == "fresh"

    # Query with room_id
    rid_miss = await ts.list_recent_run_feedback(
        room_id="BOGUS",
    )
    assert rid_miss == []

    rid_later, rid_earlier = await ts.list_recent_run_feedback(
        room_id=ROOM_ID,
    )

    rid_later_fb = await rid_later.awaitable_attrs.run_feedback
    assert await rid_later_fb.awaitable_attrs.feedback == "thumbs_up"
    assert await rid_later_fb.awaitable_attrs.reason == "fresh"

    rid_earlier_fb = await rid_earlier.awaitable_attrs.run_feedback
    assert await rid_earlier_fb.awaitable_attrs.feedback == "thumbs_down"
    assert await rid_earlier_fb.awaitable_attrs.reason == "dithering"

    # Query with user_name
    uname_miss = await ts.list_recent_run_feedback(
        user_name="BOGUS",
    )
    assert uname_miss == []

    uname_later, uname_earlier = await ts.list_recent_run_feedback(
        user_name=USER_NAME,
    )

    uname_later_fb = await uname_later.awaitable_attrs.run_feedback
    assert await uname_later_fb.awaitable_attrs.feedback == "thumbs_up"
    assert await uname_later_fb.awaitable_attrs.reason == "fresh"

    uname_earlier_fb = await uname_earlier.awaitable_attrs.run_feedback
    assert await uname_earlier_fb.awaitable_attrs.feedback == "thumbs_down"
    assert await uname_earlier_fb.awaitable_attrs.reason == "dithering"

    # Query with email
    email_miss = await ts.list_recent_run_feedback(
        email="BOGUS",
    )
    assert email_miss == []

    email_later, email_earlier = await ts.list_recent_run_feedback(
        email=EMAIL,
    )

    email_later_fb = await email_later.awaitable_attrs.run_feedback
    assert await email_later_fb.awaitable_attrs.feedback == "thumbs_up"
    assert await email_later_fb.awaitable_attrs.reason == "fresh"

    email_earlier_fb = await email_earlier.awaitable_attrs.run_feedback
    assert await email_earlier_fb.awaitable_attrs.feedback == "thumbs_down"
    assert await email_earlier_fb.awaitable_attrs.reason == "dithering"

    # Query with thread_id
    tid_miss = await ts.list_recent_run_feedback(
        thread_id="BOGUS",
    )
    assert tid_miss == []

    tid_later, tid_earlier = await ts.list_recent_run_feedback(
        thread_id=thread_id,
    )

    tid_later_fb = await tid_later.awaitable_attrs.run_feedback
    assert await tid_later_fb.awaitable_attrs.feedback == "thumbs_up"
    assert await tid_later_fb.awaitable_attrs.reason == "fresh"

    tid_earlier_fb = await tid_earlier.awaitable_attrs.run_feedback
    assert await tid_earlier_fb.awaitable_attrs.feedback == "thumbs_down"
    assert await tid_earlier_fb.awaitable_attrs.reason == "dithering"

    await ts.save_run_feedback(
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_id=thread_id,
        run_id=before_id,
        feedback="thumbs_up",
        reason="vacillating",
    )

    # Test sorting by 'run_feedback.created'
    further_run_feedback = await ts.get_run_feedback(
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_id=thread_id,
        run_id=before_id,
    )

    assert await further_run_feedback.awaitable_attrs.feedback == "thumbs_up"
    assert await further_run_feedback.awaitable_attrs.reason == "vacillating"

    tid_later, tid_earlier = await ts.list_recent_run_feedback(
        thread_id=thread_id,
    )

    tid_later_fb = await tid_later.awaitable_attrs.run_feedback
    assert await tid_later_fb.awaitable_attrs.feedback == "thumbs_up"
    assert await tid_later_fb.awaitable_attrs.reason == "vacillating"

    tid_earlier_fb = await tid_earlier.awaitable_attrs.run_feedback
    assert await tid_earlier_fb.awaitable_attrs.feedback == "thumbs_up"
    assert await tid_earlier_fb.awaitable_attrs.reason == "fresh"

    # Feedback review workflow
    tid_later_hist = await tid_later_fb.awaitable_attrs.review_history
    assert tid_later_hist == []

    async with unit_of_work():
        await ts.review_run_feedback(
            reviewer_user_name=REVIEWER_USER_NAME,
            reviewer_email=REVIEWER_EMAIL,
            note="reviewing feedback",
            run_feedback=tid_later_fb,
        )

    tid_later_hist = await tid_later_fb.awaitable_attrs.review_history
    (tid_later_entry,) = tid_later_hist
    assert await tid_later_entry.awaitable_attrs.run_feedback is tid_later_fb
    assert await tid_later_entry.awaitable_attrs.status == (
        FeedbackReviewStatus.REVIEWED
    )
    assert await tid_later_entry.awaitable_attrs.note == "reviewing feedback"

    async with unit_of_work():
        await ts.resolve_run_feedback(
            resolver_user_name=RESOLVER_USER_NAME,
            resolver_email=RESOLVER_EMAIL,
            note="resolving feedback",
            run_feedback=tid_later_fb,
        )
    tid_later_hist = await tid_later_fb.awaitable_attrs.review_history

    # Check that review history is sorted in descending order
    (
        first_entry,
        *_,
    ) = tid_later_hist
    assert await first_entry.awaitable_attrs.run_feedback is tid_later_fb
    assert await first_entry.awaitable_attrs.status == (
        FeedbackReviewStatus.RESOLVED
    )
    assert await first_entry.awaitable_attrs.note == ("resolving feedback")

    (
        *_,
        last_entry,
    ) = tid_later_hist
    assert await last_entry.awaitable_attrs.run_feedback is tid_later_fb
    assert await last_entry.awaitable_attrs.status == (
        FeedbackReviewStatus.REVIEWED
    )
    assert await last_entry.awaitable_attrs.note == ("reviewing feedback")

    # Feedback review workflow using lookup
    async with unit_of_work():
        await ts.review_run_feedback(
            reviewer_user_name=REVIEWER_USER_NAME,
            reviewer_email=REVIEWER_EMAIL,
            note="reviewing feedback",
            user_name=USER_NAME,
            room_id=ROOM_ID,
            thread_id=thread_id,
            run_id=added_id,
        )

    tid_earlier_hist = await tid_earlier_fb.awaitable_attrs.review_history
    (tid_earlier_entry,) = tid_earlier_hist
    assert (
        await tid_earlier_entry.awaitable_attrs.run_feedback is tid_earlier_fb
    )
    assert await tid_earlier_entry.awaitable_attrs.status == (
        FeedbackReviewStatus.REVIEWED
    )
    assert await tid_earlier_entry.awaitable_attrs.note == "reviewing feedback"

    async with unit_of_work():
        await ts.resolve_run_feedback(
            resolver_user_name=RESOLVER_USER_NAME,
            resolver_email=RESOLVER_EMAIL,
            note="resolving feedback",
            run_feedback=tid_later_fb,
        )
    tid_later_hist = await tid_later_fb.awaitable_attrs.review_history

    (
        first_entry,
        *_,
    ) = tid_later_hist
    assert await first_entry.awaitable_attrs.run_feedback is tid_later_fb
    assert await first_entry.awaitable_attrs.status == (
        FeedbackReviewStatus.RESOLVED
    )
    assert await first_entry.awaitable_attrs.note == "resolving feedback"

    (
        *_,
        last_entry,
    ) = tid_later_hist
    assert await last_entry.awaitable_attrs.run_feedback is tid_later_fb
    assert await last_entry.awaitable_attrs.status == (
        FeedbackReviewStatus.REVIEWED
    )
    assert await last_entry.awaitable_attrs.note == "reviewing feedback"

    async with unit_of_work():
        await ts.resolve_run_feedback(
            resolver_user_name=RESOLVER_USER_NAME,
            resolver_email=RESOLVER_EMAIL,
            note="resolving feedback",
            user_name=USER_NAME,
            room_id=ROOM_ID,
            thread_id=thread_id,
            run_id=added_id,
        )

    tid_earlier_hist = await tid_earlier_fb.awaitable_attrs.review_history

    (
        first_entry,
        *_,
    ) = tid_earlier_hist
    assert await first_entry.awaitable_attrs.run_feedback is tid_earlier_fb
    assert await first_entry.awaitable_attrs.status == (
        FeedbackReviewStatus.RESOLVED
    )

    (
        *_,
        last_entry,
    ) = tid_earlier_hist
    assert await last_entry.awaitable_attrs.run_feedback is tid_earlier_fb
    assert await last_entry.awaitable_attrs.status == (
        FeedbackReviewStatus.REVIEWED
    )
    assert await last_entry.awaitable_attrs.note == "reviewing feedback"

    # Test lookup where no feedback found
    no_feedback = await ts.new_run(
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_id=thread_id,
    )
    no_feedback_id = await no_feedback.awaitable_attrs.run_id

    with pytest.raises(agui_persistence.NoFeedbackFound):
        await ts.review_run_feedback(
            reviewer_user_name=REVIEWER_USER_NAME,
            reviewer_email=REVIEWER_EMAIL,
            note="reviewing feedback",
            user_name=USER_NAME,
            room_id=ROOM_ID,
            thread_id=thread_id,
            run_id=no_feedback_id,
        )

    with pytest.raises(agui_persistence.NoFeedbackFound):
        await ts.resolve_run_feedback(
            resolver_user_name=RESOLVER_USER_NAME,
            resolver_email=RESOLVER_EMAIL,
            note="resolving feedback",
            user_name=USER_NAME,
            room_id=ROOM_ID,
            thread_id=thread_id,
            run_id=no_feedback_id,
        )

    # Query for reviewed status
    review_only = await ts.new_run(
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_id=thread_id,
    )
    review_only_id = await review_only.awaitable_attrs.run_id

    await ts.save_run_feedback(
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_id=thread_id,
        run_id=review_only_id,
        feedback="thumbs_up",
        reason="winning",
    )

    review_only_fb = await review_only.awaitable_attrs.run_feedback

    async with unit_of_work():
        await ts.review_run_feedback(
            reviewer_user_name=REVIEWER_USER_NAME,
            reviewer_email=REVIEWER_EMAIL,
            note="reviewing feedback; no resolve",
            run_feedback=review_only_fb,
        )

    resolve_only = await ts.new_run(
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_id=thread_id,
    )

    resolve_only_id = await resolve_only.awaitable_attrs.run_id

    await ts.save_run_feedback(
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_id=thread_id,
        run_id=resolve_only_id,
        feedback="thumbs_up",
        reason="winning",
    )

    resolve_only_fb = await resolve_only.awaitable_attrs.run_feedback

    async with unit_of_work():
        await ts.resolve_run_feedback(
            resolver_user_name=RESOLVER_USER_NAME,
            resolver_email=RESOLVER_EMAIL,
            note="resolving feedback; no view",
            run_feedback=resolve_only_fb,
        )

    w_reviewed = await ts.list_recent_run_feedback(
        status=agui.FeedbackReviewStatus.REVIEWED,
    )
    assert review_only in w_reviewed
    assert resolve_only not in w_reviewed

    # Query for resolved status
    w_resolved = await ts.list_recent_run_feedback(
        status=agui.FeedbackReviewStatus.RESOLVED,
    )
    assert review_only not in w_resolved
    assert resolve_only in w_resolved


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "w_agui_events",
    [[], agui_constants.TEST_AGUI_RUN_EVENTS],
)
@mock.patch("soliplex.agui.util._timestamp")
async def test_threadstorage_save_run_events(
    ts,
    the_async_session,
    w_agui_events,
    unit_of_work,
):
    ts.return_value = NOW

    ts = agui_persistence.ThreadStorage(the_async_session)

    thread = await ts.new_thread(
        user_name=USER_NAME,
        email=EMAIL,
        room_id=ROOM_ID,
    )

    thread_id = await thread.awaitable_attrs.thread_id

    (run,) = await thread.list_runs()

    run_id = await run.awaitable_attrs.run_id

    async with unit_of_work():
        found_events = await ts.save_run_events(
            user_name=USER_NAME,
            room_id=ROOM_ID,
            thread_id=thread_id,
            run_id=run_id,
            events=w_agui_events,
        )

    finished = await run.awaitable_attrs.finished
    assert finished == NOW.replace(tzinfo=None)  # sqlalchemy drops zone

    db_events = await run.list_events()

    for found_event, exp_event, db_event in zip(
        found_events,
        w_agui_events,
        db_events,
        strict=True,
    ):
        assert found_event == exp_event
        assert db_event == exp_event


@pytest.mark.asyncio
async def test_threadstorage_save_single_event(the_async_session):
    ts = agui_persistence.ThreadStorage(the_async_session)

    thread = await ts.new_thread(
        user_name=USER_NAME,
        email=EMAIL,
        room_id=ROOM_ID,
    )

    thread_id = await thread.awaitable_attrs.thread_id

    (run,) = await thread.list_runs()

    run_id = await run.awaitable_attrs.run_id

    event_0 = agui_constants.TEXT_MESSAGE_START_EVENT
    event_1 = agui_constants.TEXT_MESSAGE_CONTENT_EVENT

    await ts.save_single_event(
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_id=thread_id,
        run_id=run_id,
        event=event_0,
    )

    await ts.save_single_event(
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_id=thread_id,
        run_id=run_id,
        event=event_1,
    )

    # Verify events were persisted
    pairs = await ts.list_run_events_after(
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_id=thread_id,
        run_id=run_id,
        after_index=-1,
    )

    assert len(pairs) == 2
    assert pairs[0][0] == 0
    assert pairs[0][1] == event_0
    assert pairs[1][0] == 1
    assert pairs[1][1] == event_1

    # Query with after_index=0 should only return the second
    pairs_after = await ts.list_run_events_after(
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_id=thread_id,
        run_id=run_id,
        after_index=0,
    )

    assert len(pairs_after) == 1
    assert pairs_after[0][0] == 1
    assert pairs_after[0][1] == event_1


@pytest.mark.asyncio
@mock.patch("soliplex.agui.util._timestamp")
async def test_threadstorage_finish_run(
    ts_mock,
    the_async_session,
    unit_of_work,
):
    ts_mock.return_value = NOW

    ts = agui_persistence.ThreadStorage(the_async_session)

    thread = await ts.new_thread(
        user_name=USER_NAME,
        email=EMAIL,
        room_id=ROOM_ID,
    )

    thread_id = await thread.awaitable_attrs.thread_id

    (run,) = await thread.list_runs()

    run_id = await run.awaitable_attrs.run_id

    # Run not yet finished
    is_fin = await ts.is_run_finished(
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_id=thread_id,
        run_id=run_id,
    )
    assert is_fin is False

    # Mark it finished
    async with unit_of_work():
        await ts.finish_run(
            user_name=USER_NAME,
            room_id=ROOM_ID,
            thread_id=thread_id,
            run_id=run_id,
        )

    # Now it should be finished
    is_fin = await ts.is_run_finished(
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_id=thread_id,
        run_id=run_id,
    )
    assert is_fin is True

    finished = await run.awaitable_attrs.finished
    assert finished == NOW.replace(tzinfo=None)


@pytest.mark.asyncio
async def test_get_latest_state_unknown_thread(the_async_session):
    ts = agui_persistence.ThreadStorage(the_async_session)

    result = await ts.get_latest_state(
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_id="NONESUCH",
    )

    assert result is None


@pytest.mark.asyncio
async def test_get_latest_state_skips_runs_without_state(
    the_async_session, unit_of_work
):
    ts = agui_persistence.ThreadStorage(the_async_session)

    thread = await ts.new_thread(
        user_name=USER_NAME,
        email=EMAIL,
        room_id=ROOM_ID,
    )
    thread_id = await thread.awaitable_attrs.thread_id
    (cited_run,) = await thread.list_runs()

    # A run with no input at all, then the reopened thread's own run,
    # which carries no state of its own.
    await ts.new_run(
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_id=thread_id,
    )
    reopened_run = await ts.new_run(
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_id=thread_id,
    )

    assert (
        await ts.get_latest_state(
            user_name=USER_NAME,
            room_id=ROOM_ID,
            thread_id=thread_id,
        )
        is None
    )

    async with unit_of_work():
        await ts.add_run_input(
            user_name=USER_NAME,
            room_id=ROOM_ID,
            thread_id=thread_id,
            run_id=await cited_run.awaitable_attrs.run_id,
            run_input=agui_constants.FULL_RUN_AGENT_INPUT,
        )
        await ts.add_run_input(
            user_name=USER_NAME,
            room_id=ROOM_ID,
            thread_id=thread_id,
            run_id=await reopened_run.awaitable_attrs.run_id,
            run_input=agui_constants.EMPTY_RUN_AGENT_INPUT,
        )

    result = await ts.get_latest_state(
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_id=thread_id,
    )

    assert result == agui_constants.STATE


@pytest.mark.asyncio
async def test_get_latest_state_prefers_a_run_s_final_snapshot(
    the_async_session, unit_of_work
):
    """A run's own answer is in the state it ends with, not the one it began.

    A client returns the state it holds when it starts a run, so the
    input of the newest run is a turn behind: it lacks the evidence and
    citations of the answer that run went on to produce.
    """
    ts = agui_persistence.ThreadStorage(the_async_session)

    thread = await ts.new_thread(
        user_name=USER_NAME,
        email=EMAIL,
        room_id=ROOM_ID,
    )
    thread_id = await thread.awaitable_attrs.thread_id
    (run,) = await thread.list_runs()
    run_id = await run.awaitable_attrs.run_id

    ended_with = {"rag": {"evidence": {"question": 5}}}

    async with unit_of_work():
        await ts.add_run_input(
            user_name=USER_NAME,
            room_id=ROOM_ID,
            thread_id=thread_id,
            run_id=run_id,
            run_input=agui_constants.FULL_RUN_AGENT_INPUT,
        )
        await ts.save_single_event(
            user_name=USER_NAME,
            room_id=ROOM_ID,
            thread_id=thread_id,
            run_id=run_id,
            event=agui_core.StateSnapshotEvent(snapshot=ended_with),
        )
        # The snapshot is emitted just before the run finishes, so the
        # newest event is not the one carrying the state.
        await ts.save_single_event(
            user_name=USER_NAME,
            room_id=ROOM_ID,
            thread_id=thread_id,
            run_id=run_id,
            event=agui_core.RunFinishedEvent(
                thread_id=thread_id,
                run_id=run_id,
            ),
        )

    result = await ts.get_latest_state(
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_id=thread_id,
    )

    assert result == ended_with


@pytest.mark.asyncio
async def test_get_latest_state_returns_newest(
    the_async_session, unit_of_work
):
    ts = agui_persistence.ThreadStorage(the_async_session)

    thread = await ts.new_thread(
        user_name=USER_NAME,
        email=EMAIL,
        room_id=ROOM_ID,
    )
    thread_id = await thread.awaitable_attrs.thread_id
    (older_run,) = await thread.list_runs()

    newer_run = await ts.new_run(
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_id=thread_id,
    )

    newest_state = {"rag": {"citation_index": {"1": "doc-1"}}}

    async with unit_of_work():
        await ts.add_run_input(
            user_name=USER_NAME,
            room_id=ROOM_ID,
            thread_id=thread_id,
            run_id=await older_run.awaitable_attrs.run_id,
            run_input=agui_constants.FULL_RUN_AGENT_INPUT,
        )
        await ts.add_run_input(
            user_name=USER_NAME,
            room_id=ROOM_ID,
            thread_id=thread_id,
            run_id=await newer_run.awaitable_attrs.run_id,
            run_input=agui_constants.FULL_RUN_AGENT_INPUT.model_copy(
                update={"state": newest_state},
            ),
        )

    result = await ts.get_latest_state(
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_id=thread_id,
    )

    assert result == newest_state


def test_as_utc_naive_tags_utc():
    naive = datetime.datetime(2026, 1, 1, 12, 0)
    assert agui_persistence._as_utc(naive) == T_NEW


def test_as_utc_already_aware_unchanged():
    assert agui_persistence._as_utc(T_NEW) is T_NEW


@pytest.mark.asyncio
async def test_get_room_last_activity_empty(the_async_session):
    ts = agui_persistence.ThreadStorage(the_async_session)

    result = await ts.get_room_last_activity(
        user_name=USER_NAME,
        room_id=ROOM_ID,
    )

    assert result is None


@pytest.mark.asyncio
async def test_get_room_last_activity_coalesce_and_max(the_async_session):
    ts = agui_persistence.ThreadStorage(the_async_session)

    # A finished run whose 'finished' (T_NEW) is later than a newer
    # unfinished run's 'created' (T_MID): max(coalesce) must be T_NEW.
    thread_id = await _add_run(
        ts,
        the_async_session,
        user_name=USER_NAME,
        email=EMAIL,
        room_id=ROOM_ID,
        created=T_OLD,
        finished=T_NEW,
    )
    await _add_run(
        ts,
        the_async_session,
        user_name=USER_NAME,
        email=EMAIL,
        room_id=ROOM_ID,
        created=T_MID,
        finished=None,
        thread_id=thread_id,
    )

    result = await ts.get_room_last_activity(
        user_name=USER_NAME,
        room_id=ROOM_ID,
    )

    assert result == T_NEW
    assert result.tzinfo is not None


@pytest.mark.asyncio
async def test_get_room_last_activity_across_threads_uses_created(
    the_async_session,
):
    ts = agui_persistence.ThreadStorage(the_async_session)

    # Two separate threads in the same room: the room-wide max must
    # aggregate across threads, and coalesce must fall back to the
    # unfinished run's 'created' (T_NEW) over the finished run (T_MID).
    await _add_run(
        ts,
        the_async_session,
        user_name=USER_NAME,
        email=EMAIL,
        room_id=ROOM_ID,
        created=T_OLD,
        finished=T_MID,
    )
    await _add_run(
        ts,
        the_async_session,
        user_name=USER_NAME,
        email=EMAIL,
        room_id=ROOM_ID,
        created=T_NEW,
        finished=None,
    )

    result = await ts.get_room_last_activity(
        user_name=USER_NAME,
        room_id=ROOM_ID,
    )

    assert result == T_NEW


@pytest.mark.asyncio
async def test_get_room_last_activity_user_scoping(the_async_session):
    ts = agui_persistence.ThreadStorage(the_async_session)

    await _add_run(
        ts,
        the_async_session,
        user_name=USER_NAME,
        email=EMAIL,
        room_id=ROOM_ID,
        created=T_OLD,
    )
    # Another user's later run in the same room must not leak in.
    await _add_run(
        ts,
        the_async_session,
        user_name=OTHER_USER_NAME,
        email=OTHER_EMAIL,
        room_id=ROOM_ID,
        created=T_NEW,
    )

    result = await ts.get_room_last_activity(
        user_name=USER_NAME,
        room_id=ROOM_ID,
    )

    assert result == T_OLD


@pytest.mark.asyncio
async def test_get_room_last_activity_room_scoping(the_async_session):
    ts = agui_persistence.ThreadStorage(the_async_session)

    await _add_run(
        ts,
        the_async_session,
        user_name=USER_NAME,
        email=EMAIL,
        room_id=ROOM_ID,
        created=T_OLD,
    )
    await _add_run(
        ts,
        the_async_session,
        user_name=USER_NAME,
        email=EMAIL,
        room_id=ROOM_ID_2,
        created=T_NEW,
    )

    result = await ts.get_room_last_activity(
        user_name=USER_NAME,
        room_id=ROOM_ID,
    )

    assert result == T_OLD


@pytest.mark.asyncio
async def test_get_rooms_last_activity_empty(the_async_session):
    ts = agui_persistence.ThreadStorage(the_async_session)

    result = await ts.get_rooms_last_activity(user_name=USER_NAME)

    assert result == {}


@pytest.mark.asyncio
async def test_get_rooms_last_activity_grouping_and_scoping(the_async_session):
    ts = agui_persistence.ThreadStorage(the_async_session)

    # ROOM_ID: coalesce picks 'finished' (T_MID) over 'created' (T_OLD).
    await _add_run(
        ts,
        the_async_session,
        user_name=USER_NAME,
        email=EMAIL,
        room_id=ROOM_ID,
        created=T_OLD,
        finished=T_MID,
    )
    await _add_run(
        ts,
        the_async_session,
        user_name=USER_NAME,
        email=EMAIL,
        room_id=ROOM_ID_2,
        created=T_NEW,
    )
    # Another user's run must not appear in this user's map.
    await _add_run(
        ts,
        the_async_session,
        user_name=OTHER_USER_NAME,
        email=OTHER_EMAIL,
        room_id=ROOM_ID,
        created=T_NEW,
    )

    result = await ts.get_rooms_last_activity(user_name=USER_NAME)

    assert result == {ROOM_ID: T_MID, ROOM_ID_2: T_NEW}
    assert all(v.tzinfo is not None for v in result.values())


@pytest.mark.asyncio
async def test_get_threads_last_activity_empty(the_async_session):
    ts = agui_persistence.ThreadStorage(the_async_session)

    result = await ts.get_threads_last_activity(
        user_name=USER_NAME,
        room_id=ROOM_ID,
    )

    assert result == {}


@pytest.mark.asyncio
async def test_get_threads_last_activity_grouping_and_scoping(
    the_async_session,
):
    ts = agui_persistence.ThreadStorage(the_async_session)

    # Thread A: two runs; coalesce/max picks the later 'finished' (T_MID)
    # over either 'created' (T_OLD).
    thread_a = await _add_run(
        ts,
        the_async_session,
        user_name=USER_NAME,
        email=EMAIL,
        room_id=ROOM_ID,
        created=T_OLD,
        finished=T_MID,
    )
    await _add_run(
        ts,
        the_async_session,
        user_name=USER_NAME,
        email=EMAIL,
        room_id=ROOM_ID,
        created=T_OLD,
        thread_id=thread_a,
    )
    # Thread B: a single, newer run in the same room.
    thread_b = await _add_run(
        ts,
        the_async_session,
        user_name=USER_NAME,
        email=EMAIL,
        room_id=ROOM_ID,
        created=T_NEW,
    )
    # A thread in another room is scoped out.
    await _add_run(
        ts,
        the_async_session,
        user_name=USER_NAME,
        email=EMAIL,
        room_id=ROOM_ID_2,
        created=T_NEW,
    )
    # Another user's thread in ROOM_ID must not appear.
    await _add_run(
        ts,
        the_async_session,
        user_name=OTHER_USER_NAME,
        email=OTHER_EMAIL,
        room_id=ROOM_ID,
        created=T_NEW,
    )

    result = await ts.get_threads_last_activity(
        user_name=USER_NAME,
        room_id=ROOM_ID,
    )

    assert result == {thread_a: T_MID, thread_b: T_NEW}
    assert all(v.tzinfo is not None for v in result.values())


# -- drive_agui_turn -------------------------------------------------------


def _event(name):
    # 'type' just needs to differ from ACTIVITY_SNAPSHOT so the RAG auditor
    # treats it as an unrelated event and no-ops.
    return SimpleNamespace(type=name)


def _adapter(events):
    async def gen():
        for event in events:
            yield event

    return SimpleNamespace(run_stream=lambda **kwargs: gen())


@pytest.fixture
def identity_compact(monkeypatch):
    # Bypass compaction so the test controls the exact event sequence.
    monkeypatch.setattr(
        agui_persistence.agui, "compact_event_stream", lambda s: s
    )


@pytest.mark.anyio
async def test_drive_agui_turn_persists_and_yields(
    monkeypatch,
    identity_compact,
):
    events = [_event("A"), _event("B")]
    saved = []

    async def fake_save(engine, **kwargs):
        saved.append(kwargs["event"])

    monkeypatch.setattr(agui_persistence, "save_single_event", fake_save)
    collected = [
        event
        async for event in agui_persistence.drive_agui_turn(
            adapter=_adapter(events),
            engine=object(),
            user_name="u",
            room_id="r",
            thread_id="t",
            run_id="x",
        )
    ]

    assert collected == events
    assert saved == events


@pytest.mark.anyio
async def test_drive_agui_turn_adds_final_state(
    monkeypatch,
    identity_compact,
):
    deps = mock.Mock(state=agui_constants.STATE_SNAPTSHOT)
    expected = [
        agui_constants.STATE_SNAPSHOT_EVENT,
        agui_constants.BARE_RUN_FINISHED_EVENT,
    ]
    saved = []

    async def fake_save(engine, **kwargs):
        saved.append(kwargs["event"])

    monkeypatch.setattr(agui_persistence, "save_single_event", fake_save)

    collected = [
        event
        async for event in agui_persistence.drive_agui_turn(
            adapter=_adapter([agui_constants.BARE_RUN_FINISHED_EVENT]),
            engine=object(),
            user_name="u",
            room_id="r",
            thread_id="t",
            run_id="x",
            run_stream_kwargs={"deps": deps},
        )
    ]

    assert collected == expected
    # The snapshot must be persisted too:  replaying a stored run relies
    # on it to re-establish the authoritative state.
    assert saved == expected


@pytest.mark.anyio
async def test_drive_agui_turn_swallows_save_errors(
    monkeypatch,
    identity_compact,
):
    events = [_event("A")]

    async def boom(engine, **kwargs):
        raise sqla_exc.SQLAlchemyError("db down")  # noqa: TRY003

    monkeypatch.setattr(agui_persistence, "logfire", mock.Mock())
    monkeypatch.setattr(agui_persistence, "save_single_event", boom)
    collected = [
        event
        async for event in agui_persistence.drive_agui_turn(
            adapter=_adapter(events),
            engine=object(),
            user_name="u",
            room_id="r",
            thread_id="t",
            run_id="x",
        )
    ]

    assert collected == events
