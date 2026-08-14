import datetime
import uuid
from types import SimpleNamespace
from unittest import mock

import pytest
import pytest_asyncio
from sqlalchemy import exc as sqla_exc
from sqlalchemy.ext import asyncio as sqla_asyncio

from soliplex import agui
from soliplex.agui import persistence as agui_persistence
from soliplex.agui import schema as agui_schema
from soliplex.agui import util as agui_util
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
TEST_THREAD_ID_UUID = uuid.uuid4()
TEST_THREAD_ID_STR = str(TEST_THREAD_ID_UUID)
TEST_RUN_ID_UUID = uuid.uuid4()
TEST_RUN_ID_STR = str(TEST_RUN_ID_UUID)


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

    before_usage = await ts.get_run_usage(
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_id=thread_id,
        run_id=before_id,
    )
    assert before_usage is None

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

    after_usage = await ts.get_run_usage(
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_id=thread_id,
        run_id=before_id,
    )

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


class Boom(sqla_exc.SQLAlchemyError):
    def __init__(self):
        super().__init__("db down")


@pytest.mark.anyio
async def test_drive_agui_turn_swallows_save_errors(
    monkeypatch,
    identity_compact,
):
    events = [_event("A")]

    async def boom(engine, **kwargs):
        raise Boom()

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


@pytest.mark.asyncio
@pytest.mark.parametrize("w_usage", [False, True])
@mock.patch("soliplex.agui.persistence.ThreadStorage")
async def test_capture_usage_after_stream(
    t_storage, w_usage, fake_async_session
):
    w_session = fake_async_session.session
    the_threads = t_storage.return_value
    the_threads.save_run_usage = mock.AsyncMock(spec_set=())
    sqla_engine = object()
    usage = mock.create_autospec(
        agui.RunUsage,
        input_tokens=1,
        output_tokens=2,
        requests=3,
        tool_calls=4,
    )
    if w_usage:
        final = mock.Mock(spec_set=["usage", "model_name"])
        final.usage = mock.Mock(
            spec_set=["input_tokens", "output_tokens"],
            input_tokens=99,
            output_tokens=7,
        )
        final.model_name = "gpt-4o-2024-11-20"
        result = mock.Mock(spec_set=["usage", "all_messages"])
        result.usage = usage
        result.all_messages = mock.Mock(return_value=[final])
    else:
        result = object()

    with mock.patch(
        "soliplex.views.agui.sqla_asyncio.AsyncSession",
        new=fake_async_session.cls,
    ):
        await agui_persistence.capture_usage_after_stream(
            result,
            sqla_engine=sqla_engine,
            user_name=USER_NAME,
            room_id=ROOM_ID,
            thread_id=TEST_THREAD_ID_STR,
            run_id=TEST_RUN_ID_STR,
        )

    if w_usage:
        the_threads.save_run_usage.assert_awaited_once_with(
            user_name=USER_NAME,
            room_id=ROOM_ID,
            thread_id=TEST_THREAD_ID_STR,
            run_id=TEST_RUN_ID_STR,
            input_tokens=1,
            output_tokens=2,
            requests=3,
            tool_calls=4,
            final_input_tokens=99,
            resolved_model_name="gpt-4o-2024-11-20",
            final_output_tokens=7,
        )
        t_storage.assert_called_once_with(w_session)
        fake_async_session.cls.assert_called_once_with(bind=sqla_engine)
    else:
        the_threads.save_run_usage.assert_not_awaited()
        t_storage.assert_not_called()
        fake_async_session.cls.assert_not_called()


@pytest.mark.asyncio
@mock.patch("soliplex.agui.persistence.ThreadStorage")
async def test_save_single_event_helper(t_storage, fake_async_session):
    w_session = fake_async_session.session
    the_threads = t_storage.return_value
    the_threads.save_single_event = mock.AsyncMock(spec_set=())
    sqla_engine = object()
    event = object()

    with mock.patch(
        "soliplex.views.agui.sqla_asyncio.AsyncSession",
        new=fake_async_session.cls,
    ):
        await agui_persistence.save_single_event(
            sqla_engine,
            user_name=USER_NAME,
            room_id=ROOM_ID,
            thread_id=TEST_THREAD_ID_STR,
            run_id=TEST_RUN_ID_STR,
            event=event,
        )

    the_threads.save_single_event.assert_called_once_with(
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_id=TEST_THREAD_ID_STR,
        run_id=TEST_RUN_ID_STR,
        event=event,
    )

    t_storage.assert_called_once_with(w_session)
    fake_async_session.cls.assert_called_once_with(bind=sqla_engine)


@pytest.mark.asyncio
@mock.patch("soliplex.agui.persistence.ThreadStorage")
async def test_finish_run_helper(t_storage, fake_async_session):
    w_session = fake_async_session.session
    the_threads = t_storage.return_value
    the_threads.finish_run = mock.AsyncMock(spec_set=())
    sqla_engine = object()

    with mock.patch(
        "soliplex.views.agui.sqla_asyncio.AsyncSession",
        new=fake_async_session.cls,
    ):
        await agui_persistence.finish_run(
            sqla_engine,
            user_name=USER_NAME,
            room_id=ROOM_ID,
            thread_id=TEST_THREAD_ID_STR,
            run_id=TEST_RUN_ID_STR,
        )

    the_threads.finish_run.assert_called_once_with(
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_id=TEST_THREAD_ID_STR,
        run_id=TEST_RUN_ID_STR,
    )

    t_storage.assert_called_once_with(w_session)
    fake_async_session.cls.assert_called_once_with(bind=sqla_engine)


@pytest.mark.parametrize(
    "messages, expected",
    [
        pytest.param([], (None, None, None), id="no-messages"),
        pytest.param(
            [mock.Mock(spec_set=["usage"], usage=None)],
            (None, None, None),
            id="request-without-usage",
        ),
    ],
)
def test_final_request_usage_without_a_model_response(messages, expected):
    """A run that never reached the model has no window measurement."""
    result = mock.Mock(spec_set=["all_messages"])
    result.all_messages = mock.Mock(return_value=messages)

    assert agui_persistence._final_request_usage(result) == expected


def test_final_request_usage_takes_the_last_response():
    """'input_tokens' on the run is cumulative; the last request is not.

    A tool loop makes several requests, and only the final one describes
    the context the model actually received at the end -- and its output
    is the reply the next request will carry on top of that.
    """
    first = mock.Mock(spec_set=["usage", "model_name"])
    first.usage = mock.Mock(
        spec_set=["input_tokens", "output_tokens"],
        input_tokens=10,
        output_tokens=3,
    )
    first.model_name = "gpt-4o-mini"

    last = mock.Mock(spec_set=["usage", "model_name"])
    last.usage = mock.Mock(
        spec_set=["input_tokens", "output_tokens"],
        input_tokens=800,
        output_tokens=120,
    )
    last.model_name = "gpt-4o-2024-11-20"

    result = mock.Mock(spec_set=["all_messages"])
    result.all_messages = mock.Mock(return_value=[first, last])

    found = agui_persistence._final_request_usage(result)

    assert found == (800, 120, "gpt-4o-2024-11-20")


async def _thread_at(
    session, *, created, room_id=ROOM_ID, user_name=USER_NAME
):
    """Create a thread with no runs, whose creation time is 'created'.

    Built directly rather than through 'new_thread', which always starts
    a thread with a run stamped 'now'.
    """
    thread = agui_schema.Thread(
        user_name=user_name,
        email=EMAIL,
        room_id=room_id,
        created=created,
    )
    session.add(thread)
    await session.flush()
    return thread.thread_id


async def _run_at(ts, thread_id, *, created, finished, room_id=ROOM_ID):
    run = await ts.new_run(
        user_name=USER_NAME,
        room_id=room_id,
        thread_id=thread_id,
    )
    run.created = created
    run.finished = finished


async def _page(ts, *, room_ids=(ROOM_ID,), limit=50, after=None):
    """Return ([(thread_id, last_activity)], next position) for a page."""
    rows, position = await ts.list_user_threads_page(
        user_name=USER_NAME,
        room_ids=list(room_ids),
        limit=limit,
        after=after,
    )
    return [
        (a_thread.thread_id, last_activity) for a_thread, last_activity in rows
    ], position


async def _named_thread(ts, *, room_id, name, user_name=USER_NAME):
    """Create a thread carrying 'name' as its metadata name."""
    thread = await ts.new_thread(
        user_name=user_name,
        email=EMAIL,
        room_id=room_id,
        thread_metadata={"name": name},
    )
    return await thread.awaitable_attrs.thread_id


async def _page_names(
    ts,
    *,
    room_ids,
    limit=50,
    after=None,
    label_ids=None,
    name_query=None,
):
    """Return (room_id, name) pairs for one page, and the next position."""
    rows, position = await ts.list_user_threads_page(
        user_name=USER_NAME,
        room_ids=room_ids,
        limit=limit,
        after=after,
        label_ids=label_ids,
        name_query=name_query,
    )
    pairs = []
    for a_thread, _last_activity in rows:
        meta = await a_thread.awaitable_attrs.thread_metadata
        pairs.append((a_thread.room_id, None if meta is None else meta.name))
    return pairs, position


@pytest.mark.asyncio
async def test_list_user_threads_page_no_rooms_short_circuits(
    the_async_session,
):
    ts = agui_persistence.ThreadStorage(the_async_session)

    # An empty room set means "the user may see nothing", which must not
    # degrade into an unfiltered listing.
    found, position = await _page(ts, room_ids=[])

    assert found == []
    assert position is None


@pytest.mark.asyncio
async def test_list_user_threads_page_orders_by_thread_activity(
    the_async_session,
    unit_of_work,
):
    ts = agui_persistence.ThreadStorage(the_async_session)

    async with unit_of_work():
        # Created first but active last: activity, not creation, leads.
        revived = await _thread_at(
            the_async_session, created=T_OLD, room_id=ROOM_ID
        )
        # No runs at all: its creation time stands in for activity.
        idle = await _thread_at(
            the_async_session, created=T_MID, room_id=ROOM_ID_2
        )
        # Shares a room with 'revived' but not its activity: a busy room
        # must not drag its stale threads up with it.
        stale = await _thread_at(
            the_async_session, created=T_OLD, room_id=ROOM_ID
        )

        # An unfinished run counts from its start, a finished one from
        # its finish; the later of the two wins.
        await _run_at(ts, revived, created=T_OLD, finished=T_NEW)
        await _run_at(ts, revived, created=T_MID, finished=None)
        await _run_at(ts, stale, created=T_OLD, finished=None)

    found, position = await _page(ts, room_ids=[ROOM_ID, ROOM_ID_2])

    assert found == [(revived, T_NEW), (idle, T_MID), (stale, T_OLD)]
    assert position is None


@pytest.mark.asyncio
async def test_list_user_threads_page_pages_by_position(
    the_async_session,
    unit_of_work,
):
    ts = agui_persistence.ThreadStorage(the_async_session)

    async with unit_of_work():
        # Every thread shares one activity time, so only the thread_id
        # tie-break can keep the pages apart.
        for _ in range(5):
            await _thread_at(the_async_session, created=T_MID)

    first, after_first = await _page(ts, limit=2)
    second, after_second = await _page(ts, limit=2, after=after_first)
    third, after_third = await _page(ts, limit=2, after=after_second)

    assert len(first) == len(second) == 2
    assert len(third) == 1
    assert after_first == agui.ThreadPagePosition(
        last_activity=T_MID,
        thread_id=first[-1][0],
    )
    assert after_third is None

    # Neither skips nor repeats a thread.
    seen = [thread_id for thread_id, _ in first + second + third]
    assert seen == sorted(seen, reverse=True)
    assert len(set(seen)) == 5


@pytest.mark.asyncio
async def test_list_user_threads_page_is_stable_under_new_activity(
    the_async_session,
    unit_of_work,
):
    ts = agui_persistence.ThreadStorage(the_async_session)

    async with unit_of_work():
        newest = await _thread_at(the_async_session, created=T_NEW)
        middle = await _thread_at(the_async_session, created=T_MID)
        oldest = await _thread_at(the_async_session, created=T_OLD)

    first, after_first = await _page(ts, limit=1)
    assert first == [(newest, T_NEW)]

    # Between pages, a thread from the first page gets a new run and
    # another thread is started: both sort ahead of the position, so
    # the next page neither repeats one nor skips the threads past it.
    later = T_NEW + datetime.timedelta(hours=1)
    async with unit_of_work():
        await _run_at(ts, newest, created=later, finished=later)
        await _thread_at(the_async_session, created=later)

    rest, position = await _page(ts, after=after_first)

    assert rest == [(middle, T_MID), (oldest, T_OLD)]
    assert position is None


@pytest.mark.asyncio
async def test_list_user_threads_page_excludes_unlisted_rooms(
    the_async_session,
    unit_of_work,
):
    ts = agui_persistence.ThreadStorage(the_async_session)

    async with unit_of_work():
        visible = await _thread_at(
            the_async_session, created=T_OLD, room_id=ROOM_ID
        )
        await _thread_at(the_async_session, created=T_NEW, room_id=ROOM_ID_2)

    found, _ = await _page(ts, room_ids=[ROOM_ID])

    # A room absent from 'room_ids' contributes nothing -- this is the
    # cross-room authorization boundary.
    assert [thread_id for thread_id, _ in found] == [visible]


@pytest.mark.asyncio
async def test_list_user_threads_page_scopes_to_the_user(
    the_async_session,
    unit_of_work,
):
    ts = agui_persistence.ThreadStorage(the_async_session)

    async with unit_of_work():
        mine = await _thread_at(the_async_session, created=T_OLD)
        theirs = await _thread_at(
            the_async_session,
            created=T_NEW,
            user_name=OTHER_USER_NAME,
        )
        # Their activity must not leak into the ordering of mine.
        await ts.new_run(
            user_name=OTHER_USER_NAME,
            room_id=ROOM_ID,
            thread_id=theirs,
        )

    found, _ = await _page(ts)

    assert [thread_id for thread_id, _ in found] == [mine]


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("plain", "plain"),
        ("100%", "100\\%"),
        ("a_b", "a\\_b"),
        ("back\\slash", "back\\\\slash"),
        ("%_\\", "\\%\\_\\\\"),
    ],
    ids=["plain", "percent", "underscore", "backslash", "all_three"],
)
def test__like_escape(raw, expected):
    assert agui_persistence._like_escape(raw) == expected


def test__name_key_folds_case():
    assert agui_persistence._name_key("Urgent") == "urgent"


async def _label_id(ts, name, color=None):
    """Create a label and return its ID.

    The ID rather than the instance: a commit expires the instance, and
    reading an expired attribute outside the session's greenlet raises
    'MissingGreenlet' rather than quietly reloading.
    """
    label = await ts.create_label(name=name, color=color)
    return label.id_


async def _label_rows(ts):
    """Return (id, name, name_key, color) for the catalogue, in order."""
    return [
        (label.id_, label.name, label.name_key, label.color)
        for label in await ts.list_labels()
    ]


async def _labelled(ts, *, room_id, name, label_ids):
    """Create a named thread carrying 'label_ids'."""
    thread_id = await _named_thread(ts, room_id=room_id, name=name)
    await ts.set_thread_labels(
        user_name=USER_NAME,
        room_id=room_id,
        thread_id=thread_id,
        label_ids=label_ids,
    )
    return thread_id


@pytest.mark.asyncio
async def test_create_label_folds_its_name_and_derives_a_color(
    the_async_session,
    unit_of_work,
):
    ts = agui_persistence.ThreadStorage(the_async_session)

    async with unit_of_work():
        label_id = await _label_id(ts, "Urgent")

    # The color derives from the row's own key, so it survives a delete
    # elsewhere in the catalogue rather than shifting with a count.
    assert await _label_rows(ts) == [
        (label_id, "Urgent", "urgent", agui_util.hue_rotated_hex(label_id))
    ]


@pytest.mark.asyncio
async def test_create_label_keeps_an_explicit_color(
    the_async_session,
    unit_of_work,
):
    ts = agui_persistence.ThreadStorage(the_async_session)

    async with unit_of_work():
        label_id = await _label_id(ts, "Urgent", color="#ABCDEF")

    assert await _label_rows(ts) == [(label_id, "Urgent", "urgent", "#ABCDEF")]


@pytest.mark.asyncio
async def test_create_label_rejects_a_name_taken_in_another_case(
    the_async_session,
    unit_of_work,
):
    ts = agui_persistence.ThreadStorage(the_async_session)

    async with unit_of_work():
        await _label_id(ts, "Urgent")

    # Raised before the insert, so the caller gets a 409 rather than a
    # transaction poisoned by the unique constraint.
    with pytest.raises(agui.DuplicateLabel):
        await ts.create_label(name="URGENT")


@pytest.mark.asyncio
async def test_list_labels_orders_by_folded_name(
    the_async_session,
    unit_of_work,
):
    ts = agui_persistence.ThreadStorage(the_async_session)

    async with unit_of_work():
        for name in ("zebra", "Alpha", "mango"):
            await _label_id(ts, name)

    labels = await ts.list_labels()

    assert [label.name for label in labels] == ["Alpha", "mango", "zebra"]


@pytest.mark.asyncio
async def test_update_label_renames_and_recolors(
    the_async_session,
    unit_of_work,
):
    ts = agui_persistence.ThreadStorage(the_async_session)

    async with unit_of_work():
        label_id = await _label_id(ts, "Urgent")

    async with unit_of_work():
        await ts.update_label(
            label_id=label_id,
            name="Blocked",
            color="#ABCDEF",
        )

    assert await _label_rows(ts) == [
        (label_id, "Blocked", "blocked", "#ABCDEF")
    ]


@pytest.mark.asyncio
async def test_update_label_leaves_omitted_fields_alone(
    the_async_session,
    unit_of_work,
):
    ts = agui_persistence.ThreadStorage(the_async_session)

    async with unit_of_work():
        label_id = await _label_id(ts, "Urgent", color="#ABCDEF")

    async with unit_of_work():
        await ts.update_label(label_id=label_id, name="Blocked")

    # Recoloring and renaming are independent: renaming must not reset
    # the swatch an administrator chose.
    assert await _label_rows(ts) == [
        (label_id, "Blocked", "blocked", "#ABCDEF")
    ]


@pytest.mark.asyncio
async def test_update_label_recolors_without_renaming(
    the_async_session,
    unit_of_work,
):
    ts = agui_persistence.ThreadStorage(the_async_session)

    async with unit_of_work():
        label_id = await _label_id(ts, "Urgent")

    async with unit_of_work():
        await ts.update_label(label_id=label_id, color="#ABCDEF")

    # The colour picker in the management tab sends no name, so this is
    # the ordinary edit -- not an edge case.
    assert await _label_rows(ts) == [(label_id, "Urgent", "urgent", "#ABCDEF")]


@pytest.mark.asyncio
async def test_update_label_lets_a_label_keep_its_own_name(
    the_async_session,
    unit_of_work,
):
    ts = agui_persistence.ThreadStorage(the_async_session)

    async with unit_of_work():
        label_id = await _label_id(ts, "Urgent", color="#ABCDEF")

    async with unit_of_work():
        # Recasing a label must not collide with itself.
        await ts.update_label(label_id=label_id, name="URGENT")

    assert await _label_rows(ts) == [(label_id, "URGENT", "urgent", "#ABCDEF")]


@pytest.mark.asyncio
async def test_update_label_rejects_another_labels_name(
    the_async_session,
    unit_of_work,
):
    ts = agui_persistence.ThreadStorage(the_async_session)

    async with unit_of_work():
        first = await _label_id(ts, "Urgent")
        await _label_id(ts, "Blocked")

    with pytest.raises(agui.DuplicateLabel):
        await ts.update_label(label_id=first, name="blocked")


@pytest.mark.asyncio
async def test_update_label_rejects_an_unknown_label(the_async_session):
    ts = agui_persistence.ThreadStorage(the_async_session)

    with pytest.raises(agui.UnknownLabel):
        await ts.update_label(label_id=404, name="Urgent")


@pytest.mark.asyncio
async def test_delete_label_rejects_an_unknown_label(the_async_session):
    ts = agui_persistence.ThreadStorage(the_async_session)

    with pytest.raises(agui.UnknownLabel):
        await ts.delete_label(label_id=404)


@pytest.mark.asyncio
async def test_delete_label_leaves_its_threads_standing(
    the_async_session,
    unit_of_work,
):
    ts = agui_persistence.ThreadStorage(the_async_session)

    async with unit_of_work():
        label_id = await _label_id(ts, "Urgent")
        await _labelled(
            ts,
            room_id=ROOM_ID,
            name="kept",
            label_ids=[label_id],
        )

    async with unit_of_work():
        await ts.delete_label(label_id=label_id)

    pairs, position = await _page_names(ts, room_ids=[ROOM_ID])

    assert [name for _, name in pairs] == ["kept"]
    assert position is None
    assert await ts.list_labels() == []


@pytest.mark.asyncio
async def test_set_thread_labels_replaces_the_whole_set(
    the_async_session,
    unit_of_work,
):
    ts = agui_persistence.ThreadStorage(the_async_session)

    async with unit_of_work():
        urgent = await _label_id(ts, "Urgent")
        blocked = await _label_id(ts, "Blocked")
        thread_id = await _labelled(
            ts,
            room_id=ROOM_ID,
            name="thread",
            label_ids=[urgent],
        )

    async with unit_of_work():
        await ts.set_thread_labels(
            user_name=USER_NAME,
            room_id=ROOM_ID,
            thread_id=thread_id,
            label_ids=[blocked],
        )

    found = await ts.get_threads_labels(thread_ids=[thread_id])

    assert [label.name for label in found[thread_id]] == ["Blocked"]


@pytest.mark.asyncio
async def test_set_thread_labels_clears_with_an_empty_list(
    the_async_session,
    unit_of_work,
):
    ts = agui_persistence.ThreadStorage(the_async_session)

    async with unit_of_work():
        urgent = await _label_id(ts, "Urgent")
        thread_id = await _labelled(
            ts,
            room_id=ROOM_ID,
            name="thread",
            label_ids=[urgent],
        )

    async with unit_of_work():
        await ts.set_thread_labels(
            user_name=USER_NAME,
            room_id=ROOM_ID,
            thread_id=thread_id,
            label_ids=[],
        )

    assert await ts.get_threads_labels(thread_ids=[thread_id]) == {}


@pytest.mark.asyncio
async def test_set_thread_labels_tolerates_a_repeated_id(
    the_async_session,
    unit_of_work,
):
    ts = agui_persistence.ThreadStorage(the_async_session)

    async with unit_of_work():
        urgent = await _label_id(ts, "Urgent")
        thread_id = await _named_thread(ts, room_id=ROOM_ID, name="thread")

    async with unit_of_work():
        # The association's composite key would reject the second copy;
        # de-duplicating first turns a 500 into a no-op.
        await ts.set_thread_labels(
            user_name=USER_NAME,
            room_id=ROOM_ID,
            thread_id=thread_id,
            label_ids=[urgent, urgent],
        )

    found = await ts.get_threads_labels(thread_ids=[thread_id])

    assert [label.name for label in found[thread_id]] == ["Urgent"]


@pytest.mark.asyncio
async def test_set_thread_labels_rejects_an_unknown_label(
    the_async_session,
    unit_of_work,
):
    ts = agui_persistence.ThreadStorage(the_async_session)

    async with unit_of_work():
        thread_id = await _named_thread(ts, room_id=ROOM_ID, name="thread")

    # Assignment only ever selects from the catalogue -- it never coins
    # a label, whoever is asking.
    with pytest.raises(agui.UnknownLabel):
        await ts.set_thread_labels(
            user_name=USER_NAME,
            room_id=ROOM_ID,
            thread_id=thread_id,
            label_ids=[404],
        )


@pytest.mark.asyncio
async def test_set_thread_labels_refuses_another_users_thread(
    the_async_session,
    unit_of_work,
):
    ts = agui_persistence.ThreadStorage(the_async_session)

    async with unit_of_work():
        urgent = await _label_id(ts, "Urgent")
        thread = await ts.new_thread(
            user_name=OTHER_USER_NAME,
            email=OTHER_EMAIL,
            room_id=ROOM_ID,
            thread_metadata={"name": "theirs"},
        )
        thread_id = await thread.awaitable_attrs.thread_id

    with pytest.raises(agui.UnknownThread):
        await ts.set_thread_labels(
            user_name=USER_NAME,
            room_id=ROOM_ID,
            thread_id=thread_id,
            label_ids=[urgent],
        )


@pytest.mark.asyncio
async def test_get_threads_labels_batches_and_omits_the_unlabelled(
    the_async_session,
    unit_of_work,
):
    ts = agui_persistence.ThreadStorage(the_async_session)

    async with unit_of_work():
        urgent = await _label_id(ts, "Urgent")
        blocked = await _label_id(ts, "Blocked")
        first = await _labelled(
            ts,
            room_id=ROOM_ID,
            name="first",
            label_ids=[urgent, blocked],
        )
        second = await _labelled(
            ts,
            room_id=ROOM_ID,
            name="second",
            label_ids=[urgent],
        )
        bare = await _named_thread(ts, room_id=ROOM_ID, name="bare")

    found = await ts.get_threads_labels(
        thread_ids=[first, second, bare],
    )

    assert [label.name for label in found[first]] == ["Blocked", "Urgent"]
    assert [label.name for label in found[second]] == ["Urgent"]
    assert bare not in found


@pytest.mark.asyncio
async def test_get_threads_labels_short_circuits_on_no_threads(
    the_async_session,
):
    ts = agui_persistence.ThreadStorage(the_async_session)

    assert await ts.get_threads_labels(thread_ids=[]) == {}


@pytest.mark.asyncio
async def test_get_label_usage_counts_spans_every_user(
    the_async_session,
    unit_of_work,
):
    ts = agui_persistence.ThreadStorage(the_async_session)

    async with unit_of_work():
        urgent = await _label_id(ts, "Urgent")
        unused = await _label_id(ts, "Unused")
        await _labelled(
            ts,
            room_id=ROOM_ID,
            name="mine",
            label_ids=[urgent],
        )
        theirs = await ts.new_thread(
            user_name=OTHER_USER_NAME,
            email=OTHER_EMAIL,
            room_id=ROOM_ID,
            thread_metadata={"name": "theirs"},
        )
        await ts.set_thread_labels(
            user_name=OTHER_USER_NAME,
            room_id=ROOM_ID,
            thread_id=await theirs.awaitable_attrs.thread_id,
            label_ids=[urgent],
        )

    counts = await ts.get_label_usage_counts()

    # Global, not per-caller -- which is exactly why the view only hands
    # these to an administrator.
    assert counts[urgent] == 2
    # A label nothing carries is omitted rather than reported as zero.
    assert unused not in counts


@pytest.mark.asyncio
async def test_list_user_threads_page_filters_by_any_label(
    the_async_session,
    unit_of_work,
):
    ts = agui_persistence.ThreadStorage(the_async_session)

    async with unit_of_work():
        urgent = await _label_id(ts, "Urgent")
        blocked = await _label_id(ts, "Blocked")
        await _labelled(
            ts,
            room_id=ROOM_ID,
            name="both",
            label_ids=[urgent, blocked],
        )
        await _labelled(
            ts,
            room_id=ROOM_ID,
            name="urgent-only",
            label_ids=[urgent],
        )
        await _named_thread(ts, room_id=ROOM_ID, name="unlabelled")

    pairs, position = await _page_names(
        ts,
        room_ids=[ROOM_ID],
        label_ids=[urgent, blocked],
    )

    # "Any of", and each thread appears once however many of the
    # requested labels it carries -- the semi-join multiplies nothing.
    assert sorted(name for _, name in pairs) == ["both", "urgent-only"]
    assert position is None


@pytest.mark.asyncio
async def test_list_user_threads_page_pages_correctly_when_filtered(
    the_async_session,
    unit_of_work,
):
    ts = agui_persistence.ThreadStorage(the_async_session)

    async with unit_of_work():
        urgent = await _label_id(ts, "Urgent")
        blocked = await _label_id(ts, "Blocked")
        for index in range(4):
            await _labelled(
                ts,
                room_id=ROOM_ID,
                name=f"thread-{index}",
                label_ids=[urgent, blocked],
            )

    seen = []
    position = None
    for _ in range(2):
        pairs, position = await _page_names(
            ts,
            room_ids=[ROOM_ID],
            limit=2,
            after=position,
            label_ids=[urgent, blocked],
        )
        seen.extend(name for _, name in pairs)

    # Had the filter been a join rather than a semi-join, each thread
    # would occupy two rows and this would skip half the results.
    assert sorted(seen) == ["thread-0", "thread-1", "thread-2", "thread-3"]
    assert position is None


@pytest.mark.asyncio
async def test_list_user_threads_page_treats_no_labels_as_unfiltered(
    the_async_session,
    unit_of_work,
):
    ts = agui_persistence.ThreadStorage(the_async_session)

    async with unit_of_work():
        await _named_thread(ts, room_id=ROOM_ID, name="unlabelled")

    pairs, position = await _page_names(
        ts,
        room_ids=[ROOM_ID],
        label_ids=[],
    )

    # An empty selection means "no filter chosen", not "match nothing":
    # a client clearing its last chip must not empty the list.
    assert [name for _, name in pairs] == ["unlabelled"]
    assert position is None


@pytest.mark.asyncio
async def test_list_user_threads_page_filters_by_name(
    the_async_session,
    unit_of_work,
):
    ts = agui_persistence.ThreadStorage(the_async_session)

    async with unit_of_work():
        await _named_thread(ts, room_id=ROOM_ID, name="Osprey Pilot Manual")
        await _named_thread(ts, room_id=ROOM_ID, name="Chinook Manual")
        await _named_thread(ts, room_id=ROOM_ID, name="Unrelated")

    pairs, position = await _page_names(
        ts,
        room_ids=[ROOM_ID],
        name_query="manual",
    )

    # Case-insensitive substring.
    assert sorted(name for _, name in pairs) == [
        "Chinook Manual",
        "Osprey Pilot Manual",
    ]
    assert position is None


@pytest.mark.asyncio
async def test_list_user_threads_page_escapes_name_wildcards(
    the_async_session,
    unit_of_work,
):
    ts = agui_persistence.ThreadStorage(the_async_session)

    async with unit_of_work():
        await _named_thread(ts, room_id=ROOM_ID, name="100% coverage")
        await _named_thread(ts, room_id=ROOM_ID, name="something else")

    pairs, position = await _page_names(
        ts,
        room_ids=[ROOM_ID],
        name_query="100%",
    )

    # Unescaped, the '%' would match every thread in the room.
    assert [name for _, name in pairs] == ["100% coverage"]
    assert position is None


@pytest.mark.asyncio
async def test_list_user_threads_page_name_filter_drops_unnamed_threads(
    the_async_session,
    unit_of_work,
):
    ts = agui_persistence.ThreadStorage(the_async_session)

    async with unit_of_work():
        await _named_thread(ts, room_id=ROOM_ID, name="named")
        await ts.new_thread(
            user_name=USER_NAME,
            email=EMAIL,
            room_id=ROOM_ID,
        )

    pairs, position = await _page_names(
        ts,
        room_ids=[ROOM_ID],
        name_query="named",
    )

    # A thread with no metadata row cannot match a name search -- but it
    # still appears in the unfiltered listing, which is why the filter is
    # a correlated EXISTS rather than a join on the metadata row.
    assert [name for _, name in pairs] == ["named"]
    assert position is None

    unfiltered, _ = await _page_names(ts, room_ids=[ROOM_ID])

    assert len(unfiltered) == 2
    assert None in [name for _, name in unfiltered]


@pytest.mark.asyncio
async def test_list_user_threads_page_combines_both_filters(
    the_async_session,
    unit_of_work,
):
    ts = agui_persistence.ThreadStorage(the_async_session)

    async with unit_of_work():
        urgent = await _label_id(ts, "Urgent")
        await _labelled(
            ts,
            room_id=ROOM_ID,
            name="Osprey Manual",
            label_ids=[urgent],
        )
        await _named_thread(ts, room_id=ROOM_ID, name="Chinook Manual")
        await _labelled(
            ts,
            room_id=ROOM_ID,
            name="Unrelated",
            label_ids=[urgent],
        )

    pairs, position = await _page_names(
        ts,
        room_ids=[ROOM_ID],
        label_ids=[urgent],
        name_query="manual",
    )

    # AND across the two axes: the label chip narrows the text search
    # rather than widening it.
    assert [name for _, name in pairs] == ["Osprey Manual"]
    assert position is None
