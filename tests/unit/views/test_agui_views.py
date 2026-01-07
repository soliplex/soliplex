import contextlib
import datetime
import functools
from unittest import mock

import fastapi
import pytest
from ag_ui import core as agui_core

from soliplex import agui as agui_package
from soliplex import installation
from soliplex import models
from soliplex.views import agui as agui_views

NOW = datetime.datetime.now(datetime.UTC)
USER_NAME = "phreddy"
GIVEN_NAME = "Phred"
FAMILY_NAME = "Phlyntstone"
EMAIL = "phreddy@example.com"

AUTH_USER = {
    "preferred_username": USER_NAME,
    "given_name": GIVEN_NAME,
    "family_name": FAMILY_NAME,
    "email": EMAIL,
}

UNKNOWN_USER = {
    "preferred_username": "<unknown>",
    "given_name": "<unknown>",
    "family_name": "<unknown>",
    "email": "<unknown>",
}

TEST_ROOM_ID = "test-room"
OTHER_ROOM_ID = "other-room"
TEST_THREAD_ID = "test-thread-123"
TEST_THREAD_NAME = "Test thread #123"
TEST_THREAD_DESC = "Test thread description"
TEST_PARENT_RUN_ID = "test-run-234"
TEST_RUN_ID = "test-run-456"
TEST_RUN_LABEL = "My test run #456"
TEST_RUN_FEEDBACK = "test-feedback"
TEST_RUN_FEEDBACK_REASON = "Just because"

EMPTY_RUN_INPUT = agui_core.RunAgentInput(
    thread_id=TEST_THREAD_ID,
    run_id=TEST_RUN_ID,
    state=None,
    messages=(),
    tools=(),
    context=(),
    forwarded_props=None,
)

AGUI_EVENTS = [
    agui_core.RunStartedEvent(
        thread_id=TEST_THREAD_ID,
        run_id=TEST_RUN_ID,
    ),
    agui_core.RunFinishedEvent(
        thread_id=TEST_THREAD_ID,
        run_id=TEST_RUN_ID,
    ),
]


@pytest.fixture
def test_thread():
    return mock.create_autospec(
        agui_package.Thread,
        room_id=TEST_ROOM_ID,
        thread_id=TEST_THREAD_ID,
        thread_metadata=None,
        created=NOW,
        awaitable_attrs=mock.AsyncMock(),
        instance=True,
    )


def _make_thread_metadata(
    name=TEST_THREAD_NAME,
    description=None,
):
    class TestMetadata(agui_package.ThreadMetadata):
        def __init__(self):
            self.name = name
            self.description = description

    return TestMetadata()


@pytest.fixture
def test_run():
    return mock.create_autospec(
        agui_package.Run,
        thread_id=TEST_THREAD_ID,
        run_id=TEST_RUN_ID,
        parent_run_id=None,
        run_metadata=None,
        created=NOW,
        finished=None,
        awaitable_attrs=mock.AsyncMock(),
        instance=True,
    )


@pytest.fixture
def test_run_metadata():
    return mock.create_autospec(
        agui_package.RunMetadata,
        label=TEST_RUN_LABEL,
    )


@pytest.fixture
def run_input():
    return agui_core.RunAgentInput(
        thread_id=TEST_THREAD_ID,
        run_id=TEST_RUN_ID,
        state={},
        messages=[],
        tools=[],
        context=[],
        forwarded_props=None,
    )


@pytest.fixture
def the_threads():
    return mock.create_autospec(agui_package.ThreadStorage)


def _awaitable(name, value):
    async def getter():
        return value

    getter_co = getter()
    getter_co.__qualname__ = f"_awaitable.locals.getter_{name}"
    return getter_co


no_error = contextlib.nullcontext

UNKNOWN_THREAD = agui_package.UnknownThread(USER_NAME, TEST_THREAD_ID)
THREAD_ROOM_MISMATCH = agui_package.ThreadRoomMismatch(
    OTHER_ROOM_ID,
    TEST_ROOM_ID,
)
UNKNOWN_PARENT_RUN = agui_package.MissingParentRun(TEST_PARENT_RUN_ID)
UNKNOWN_RUN = agui_package.UnknownRun(TEST_RUN_ID)
ALREADY_STARTED = agui_package.RunAlreadyStarted(
    USER_NAME,
    TEST_THREAD_ID,
    TEST_RUN_ID,
)


def raises_httpexc(*, match, code) -> pytest.raises:
    def _check(exc):
        return exc.status_code == code

    return pytest.raises(fastapi.HTTPException, match=match, check=_check)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "w_miss, expectation",
    [
        (False, no_error(USER_NAME)),
        (True, raises_httpexc(code=404, match="No such room")),
    ],
)
@mock.patch("soliplex.authn.authenticate")
async def test__check_user_in_room(auth_fn, w_miss, expectation):
    auth_fn.return_value = {"preferred_username": USER_NAME}

    the_installation = mock.create_autospec(installation.Installation)
    token = object()

    if w_miss:
        the_installation.get_room_config.side_effect = KeyError("testing")

    with expectation as expected:
        found = await agui_views._check_user_in_room(
            room_id=TEST_ROOM_ID,
            the_installation=the_installation,
            token=token,
        )

    if isinstance(expected, str):
        assert found == expected

    the_installation.get_room_config.assert_called_once_with(
        TEST_ROOM_ID,
        user=auth_fn.return_value,
    )
    auth_fn.assert_called_once_with(the_installation, token)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "w_miss, expectation",
    [
        (False, no_error(USER_NAME)),
        (True, raises_httpexc(code=404, match="No such room")),
    ],
)
@mock.patch("soliplex.authn.authenticate")
async def test__check_user_room_agent(auth_fn, w_miss, expectation):
    auth_fn.return_value = {"preferred_username": USER_NAME}

    the_installation = mock.create_autospec(installation.Installation)
    token = object()

    if w_miss:
        the_installation.get_agent_for_room.side_effect = KeyError("testing")

    with expectation as expected:
        found = await agui_views._check_user_room_agent(
            room_id=TEST_ROOM_ID,
            the_installation=the_installation,
            token=token,
        )

    if isinstance(expected, str):
        user_name, user_profile, agent = found
        assert user_name == expected
        assert agent is the_installation.get_agent_for_room.return_value
        assert user_profile.preferred_username == expected

    the_installation.get_agent_for_room.assert_called_once_with(
        TEST_ROOM_ID,
        user=auth_fn.return_value,
    )
    auth_fn.assert_called_once_with(the_installation, token)


@pytest.mark.anyio
@pytest.mark.parametrize("w_thread_meta", [False, True])
@mock.patch("soliplex.views.agui._check_user_in_room")
async def test_get_room_agui(cuir, the_threads, test_thread, w_thread_meta):
    cuir.return_value = USER_NAME

    request = fastapi.Request(scope={"type": "http"})
    the_installation = mock.create_autospec(installation.Installation)
    token = object()

    if w_thread_meta:
        thread_meta = test_thread.thread_metadata = _make_thread_metadata()
        test_thread.awaitable_attrs.thread_metadata = _awaitable(
            "thread_metadata",
            thread_meta,
        )
    else:
        test_thread.thread_meta = None
        test_thread.awaitable_attrs.thread_metadata = _awaitable(
            "thread_metadata", None
        )

    the_threads.list_user_threads.return_value = [test_thread]

    found = await agui_views.get_room_agui(
        request,
        room_id=TEST_ROOM_ID,
        the_installation=the_installation,
        the_threads=the_threads,
        token=token,
    )

    (m_thread,) = found.threads

    assert m_thread.room_id == TEST_ROOM_ID
    assert m_thread.thread_id == TEST_THREAD_ID
    assert m_thread.runs is None

    if w_thread_meta:
        assert m_thread.metadata.name == TEST_THREAD_NAME
    else:
        assert m_thread.metadata is None

    the_threads.list_user_threads.assert_called_once_with(
        user_name=USER_NAME,
        room_id=TEST_ROOM_ID,
    )

    cuir.assert_called_once_with(
        room_id=TEST_ROOM_ID,
        the_installation=the_installation,
        token=token,
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "tsgt_side_effect, expectation",
    [
        (None, no_error(None)),
        (UNKNOWN_THREAD, raises_httpexc(code=404, match="Unknown thread")),
        (THREAD_ROOM_MISMATCH, raises_httpexc(code=400, match="Thread room")),
    ],
)
@pytest.mark.parametrize("w_parent", [False, True])
@pytest.mark.parametrize("w_run_meta", [False, True])
@pytest.mark.parametrize("w_thread_meta", [False, True])
@mock.patch("soliplex.views.agui._check_user_in_room")
async def test_get_room_agui_thread_id(
    cuir,
    the_threads,
    test_thread,
    test_run,
    test_run_metadata,
    run_input,
    w_thread_meta,
    w_run_meta,
    w_parent,
    tsgt_side_effect,
    expectation,
):
    cuir.return_value = USER_NAME

    test_thread.list_runs.return_value = [test_run]

    if w_thread_meta:
        thread_meta = test_thread.thread_metadata = _make_thread_metadata()
        test_thread.awaitable_attrs.thread_metadata = _awaitable(
            "thread_metadata",
            thread_meta,
        )
    else:
        test_thread.thread_meta = None
        test_thread.awaitable_attrs.thread_metadata = _awaitable(
            "thread_metadata", None
        )

    test_run.awaitable_attrs.thread = _awaitable(
        "thread",
        test_thread,
    )

    run_agent_input = mock.Mock(spec_set=["to_agui_model"])
    run_agent_input.to_agui_model.return_value = run_input
    test_run.awaitable_attrs.run_agent_input = _awaitable(
        "run_agent_input",
        run_agent_input,
    )

    if w_run_meta:
        test_run.run_metadata = test_run_metadata
        test_run.awaitable_attrs.run_metadata = _awaitable(
            "run_metadata",
            test_run_metadata,
        )
    else:
        test_run.run_metadata = None
        test_run.awaitable_attrs.run_metadata = _awaitable(
            "run_metadata",
            None,
        )

    if w_parent:
        test_run.parent_run_id = TEST_PARENT_RUN_ID
    else:
        test_run.parent_run_id = None

    request = fastapi.Request(scope={"type": "http"})
    the_installation = mock.create_autospec(installation.Installation)
    token = object()

    if tsgt_side_effect is not None:
        the_threads.get_thread.side_effect = tsgt_side_effect
    else:
        the_threads.get_thread.return_value = test_thread

    with expectation as expected:
        found = await agui_views.get_room_agui_thread_id(
            request=request,
            room_id=TEST_ROOM_ID,
            thread_id=TEST_THREAD_ID,
            the_installation=the_installation,
            the_threads=the_threads,
            token=token,
        )

    if expected is None:
        assert found.room_id == TEST_ROOM_ID
        assert found.thread_id == TEST_THREAD_ID

        exp_model_run = models.AGUI_Run.from_run(
            a_run=test_run,
            a_run_input=run_input,
            a_run_meta=test_run.run_metadata,
            a_run_events=None,
        )
        assert found.runs == {TEST_RUN_ID: exp_model_run}

        if w_thread_meta:
            assert found.metadata.name == TEST_THREAD_NAME
        else:
            assert found.metadata is None

    the_threads.get_thread.assert_called_once_with(
        user_name=USER_NAME,
        room_id=TEST_ROOM_ID,
        thread_id=TEST_THREAD_ID,
    )
    cuir.assert_called_once_with(
        room_id=TEST_ROOM_ID,
        the_installation=the_installation,
        token=token,
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "tsgr_side_effect, expectation",
    [
        (None, no_error(None)),
        (UNKNOWN_THREAD, raises_httpexc(code=404, match="Unknown thread")),
        (THREAD_ROOM_MISMATCH, raises_httpexc(code=400, match="Thread room")),
        (UNKNOWN_RUN, raises_httpexc(code=404, match="Unknown run")),
    ],
)
@pytest.mark.parametrize("w_usage", [None, (1, 2, 3, 4)])
@pytest.mark.parametrize("w_events", [[], AGUI_EVENTS])
@pytest.mark.parametrize("w_parent", [False, True])
@pytest.mark.parametrize("w_run_meta", [False, True])
@mock.patch("soliplex.views.agui._check_user_in_room")
async def test_get_room_agui_thread_id_run_id(
    cuir,
    the_threads,
    test_thread,
    test_run,
    test_run_metadata,
    run_input,
    w_run_meta,
    w_parent,
    w_events,
    w_usage,
    tsgr_side_effect,
    expectation,
):
    cuir.return_value = USER_NAME

    test_run.list_events.return_value = w_events

    run_agent_input = mock.Mock(spec_set=["to_agui_model"])
    run_agent_input.to_agui_model.return_value = run_input
    test_run.awaitable_attrs.run_agent_input = _awaitable(
        "run_agent_input",
        run_agent_input,
    )

    if w_run_meta:
        test_run.run_metadata = test_run_metadata
        test_run.awaitable_attrs.run_metadata = _awaitable(
            "run_metadata",
            test_run_metadata,
        )
    else:
        test_run.run_metadata = None
        test_run.awaitable_attrs.run_metadata = _awaitable(
            "run_metadata",
            None,
        )

    if w_parent:
        test_run.parent_run_id = TEST_PARENT_RUN_ID
    else:
        test_run.parent_run_id = None

    if w_usage is not None:
        w_usage = mock.create_autospec(
            agui_package.RunUsage,
            input_tokens=w_usage[0],
            output_tokens=w_usage[1],
            requests=w_usage[2],
            tool_calls=w_usage[3],
        )

    test_run.awaitable_attrs.run_usage = _awaitable("run_usage", w_usage)

    test_run.awaitable_attrs.thread = _awaitable(
        "thread",
        test_thread,
    )

    request = fastapi.Request(scope={"type": "http"})
    the_installation = mock.create_autospec(installation.Installation)
    token = object()

    if tsgr_side_effect is not None:
        the_threads.get_run.side_effect = tsgr_side_effect
    else:
        the_threads.get_run.return_value = test_run

    with expectation as expected:
        found = await agui_views.get_room_agui_thread_id_run_id(
            request=request,
            room_id=TEST_ROOM_ID,
            thread_id=TEST_THREAD_ID,
            run_id=TEST_RUN_ID,
            the_installation=the_installation,
            the_threads=the_threads,
            token=token,
        )

    if expected is None:
        assert found.thread_id == TEST_THREAD_ID
        assert found.run_id == TEST_RUN_ID

        assert found.events == w_events

        if w_run_meta:
            assert found.metadata.label == TEST_RUN_LABEL
        else:
            assert found.metadata is None

    the_threads.get_run.assert_called_once_with(
        user_name=USER_NAME,
        room_id=TEST_ROOM_ID,
        thread_id=TEST_THREAD_ID,
        run_id=TEST_RUN_ID,
    )
    cuir.assert_called_once_with(
        room_id=TEST_ROOM_ID,
        the_installation=the_installation,
        token=token,
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "w_thread_meta",
    [
        {},
        {"name": "NAME"},
        {"name": "NAME", "description": "DESCRIPTION"},
    ],
)
@mock.patch("soliplex.views.agui._check_user_in_room")
async def test_post_room_agui(
    cuir,
    the_threads,
    test_thread,
    test_run,
    run_input,
    w_thread_meta,
):
    cuir.return_value = USER_NAME

    test_thread.list_runs.return_value = [test_run]

    if w_thread_meta:
        thread_meta = _make_thread_metadata(**w_thread_meta)
        test_thread.thread_metadata = thread_meta
        test_thread.awaitable_attrs.thread_metadata = _awaitable(
            "thread_metadata",
            thread_meta,
        )
        exp_meta = {"description": None} | w_thread_meta
        ntr = {"metadata": w_thread_meta}
        new_thread_request = models.AGUI_NewThreadRequest.model_validate(ntr)
    else:
        test_thread.thread_metadata = None
        test_thread.awaitable_attrs.thread_metadata = _awaitable(
            "thread_metadata",
            None,
        )
        exp_meta = None
        new_thread_request = models.AGUI_NewThreadRequest()

    token = object()
    request = fastapi.Request(scope={"type": "http"})
    the_installation = mock.create_autospec(installation.Installation)

    the_threads.new_thread.return_value = test_thread
    test_thread.list_runs.return_value = [test_run]

    test_run.parent_run_id = None

    test_run.run_metadata = None
    test_run.awaitable_attrs.run_metadata = _awaitable("run_metadata", None)

    test_run.run_input = run_input
    run_agent_input = mock.Mock(spec_set=["to_agui_model"])
    run_agent_input.to_agui_model.return_value = run_input
    test_run.awaitable_attrs.run_agent_input = _awaitable(
        "run_agent_input",
        run_agent_input,
    )
    test_run.awaitable_attrs.thread = _awaitable(
        "thread",
        test_thread,
    )

    found = await agui_views.post_room_agui(
        request,
        room_id=TEST_ROOM_ID,
        new_thread_request=new_thread_request,
        the_installation=the_installation,
        the_threads=the_threads,
        token=token,
    )

    assert found.room_id == TEST_ROOM_ID
    assert found.thread_id == TEST_THREAD_ID
    assert found.metadata == new_thread_request.metadata

    (m_run,) = found.runs.values()
    assert m_run.thread_id == TEST_THREAD_ID
    assert m_run.run_id == TEST_RUN_ID
    assert m_run.parent_run_id is None

    the_threads.new_thread.assert_called_once_with(
        room_id=TEST_ROOM_ID,
        user_name=USER_NAME,
        thread_metadata=exp_meta,
        initial_run=True,
    )

    cuir.assert_called_once_with(
        room_id=TEST_ROOM_ID,
        the_installation=the_installation,
        token=token,
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "w_parent_id, missing_parent, expectation",
    [
        (None, False, no_error()),
        (TEST_PARENT_RUN_ID, False, no_error()),
        (
            TEST_PARENT_RUN_ID,
            True,
            raises_httpexc(code=400, match="Unknown parent run"),
        ),
    ],
)
@pytest.mark.parametrize("w_run_meta", [False, True])
@mock.patch("soliplex.views.agui._check_user_in_room")
async def test_post_room_agui_thread_id(
    cuir,
    the_threads,
    test_run,
    test_run_metadata,
    run_input,
    w_run_meta,
    w_parent_id,
    missing_parent,
    expectation,
):
    cuir.return_value = USER_NAME

    request = fastapi.Request(scope={"type": "http"})
    nrr = {}

    if w_parent_id:
        nrr = {"parent_run_id": TEST_PARENT_RUN_ID}

    if missing_parent:
        the_threads.new_run.side_effect = UNKNOWN_PARENT_RUN
    else:
        the_threads.new_run.return_value = test_run

        test_run.awaitable_attrs.run_id = _awaitable("run_id", TEST_RUN_ID)
        test_run.awaitable_attrs.created = _awaitable("created", NOW)

        if w_run_meta:
            run_meta_kw = nrr["metadata"] = {"label": TEST_RUN_LABEL}
            test_run.run_metadata = test_run_metadata
            test_run.awaitable_attrs.run_metadata = _awaitable(
                "run_metadata",
                test_run_metadata,
            )
        else:
            run_meta_kw = test_run.run_metadata = None
            test_run.awaitable_attrs.run_metadata = _awaitable(
                "run_metadata",
                None,
            )

        test_run.run_input = run_input
        run_agent_input = mock.Mock(spec_set=["to_agui_model"])
        run_agent_input.to_agui_model.return_value = run_input
        test_run.awaitable_attrs.run_agent_input = _awaitable(
            "run_agent_input",
            run_agent_input,
        )

    test_run.list_events.return_value = []

    new_run_request = models.AGUI_NewRunRequest.model_validate(nrr)

    the_installation = mock.create_autospec(installation.Installation)
    token = object()

    with expectation as expected:
        found = await agui_views.post_room_agui_thread_id(
            request,
            room_id=TEST_ROOM_ID,
            thread_id=TEST_THREAD_ID,
            new_run_request=new_run_request,
            the_installation=the_installation,
            the_threads=the_threads,
            token=token,
        )

    if expected is None:
        assert found.thread_id == TEST_THREAD_ID

        if w_run_meta:
            assert found.metadata == models.AGUI_RunMetadata.from_run_meta(
                test_run_metadata,
            )
        else:
            assert found.metadata is None

        assert found.parent_run_id == w_parent_id

        the_threads.new_run.assert_called_once_with(
            user_name=USER_NAME,
            room_id=TEST_ROOM_ID,
            thread_id=TEST_THREAD_ID,
            run_metadata=run_meta_kw,
            parent_run_id=w_parent_id,
        )

    cuir.assert_called_once_with(
        room_id=TEST_ROOM_ID,
        the_installation=the_installation,
        token=token,
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "tsutm_side_effect, expectation",
    [
        (None, no_error(205)),
        (UNKNOWN_THREAD, raises_httpexc(code=404, match="Unknown thread")),
        (THREAD_ROOM_MISMATCH, raises_httpexc(code=400, match="Thread room")),
    ],
)
@pytest.mark.parametrize(
    "w_meta",
    [
        None,
        {"name": TEST_THREAD_NAME},
        {"name": TEST_THREAD_NAME, "description": TEST_THREAD_DESC},
    ],
)
@mock.patch("soliplex.views.agui._check_user_in_room")
async def test_post_room_agui_thread_id_meta(
    cuir,
    the_threads,
    w_meta,
    tsutm_side_effect,
    expectation,
):
    cuir.return_value = USER_NAME

    request = fastapi.Request(scope={"type": "http"})

    if w_meta is not None:
        exp_t_meta = w_meta
        r_meta = models.AGUI_ThreadMetadata.model_validate(w_meta)
    else:
        exp_t_meta = None
        r_meta = models.AGUI_ThreadMetadata()

    the_installation = mock.create_autospec(installation.Installation)
    token = object()

    the_threads.update_thread_metadata.side_effect = tsutm_side_effect

    with expectation as expected:
        found = await agui_views.post_room_agui_thread_id_meta(
            request,
            room_id=TEST_ROOM_ID,
            thread_id=TEST_THREAD_ID,
            new_metadata=r_meta,
            the_installation=the_installation,
            the_threads=the_threads,
            token=token,
        )

    if isinstance(expected, int):
        assert isinstance(found, fastapi.Response)
        assert found.status_code == expected

    the_threads.update_thread_metadata.assert_called_once_with(
        user_name=USER_NAME,
        room_id=TEST_ROOM_ID,
        thread_id=TEST_THREAD_ID,
        thread_metadata=exp_t_meta,
    )
    cuir.assert_called_once_with(
        room_id=TEST_ROOM_ID,
        the_installation=the_installation,
        token=token,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("w_event_count", [0, 1, 10])
async def test_tee_events(w_event_count):
    event_log = []
    on_done = mock.AsyncMock(spec_set=())

    async def event_iter():
        for event in range(w_event_count):
            yield event

    expected = [
        event
        async for event in agui_views.tee_events(
            event_iter(),
            event_log,
            on_done,
        )
    ]

    assert len(event_log) == w_event_count
    assert event_log == expected

    on_done.assert_awaited_once_with(events=event_log)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "ari_side_effect, expectation",
    [
        (None, no_error()),
        (UNKNOWN_THREAD, raises_httpexc(code=404, match="Unknown thread")),
        (THREAD_ROOM_MISMATCH, raises_httpexc(code=400, match="Thread room")),
        (UNKNOWN_RUN, raises_httpexc(code=404, match="Unknown run")),
        (ALREADY_STARTED, raises_httpexc(code=400, match="already started")),
    ],
)
@pytest.mark.parametrize("w_usage", [False, True])
@mock.patch("fastapi.responses.StreamingResponse")
@mock.patch("pydantic_ai.ui.ag_ui.AGUIAdapter")
@mock.patch("soliplex.agui.parser.agui_events_from_dicts")
@mock.patch("soliplex.agui.mpx.multiplex_streams")
@mock.patch("soliplex.agui.compact_event_stream")
@mock.patch("soliplex.views.agui._check_user_room_agent")
@mock.patch("soliplex.views.agui.tee_events")
async def test_post_room_agui_thread_id_run_id(
    tee,
    cura,
    ces,
    mpx,
    aefd,
    aga,
    sr,
    the_threads,
    test_run,
    run_input,
    w_usage,
    ari_side_effect,
    expectation,
):
    USER_PROFILE = models.UserProfile(**AUTH_USER)
    agent = object()
    cura.return_value = (USER_NAME, USER_PROFILE, agent)

    request = fastapi.Request(scope={"type": "http"})

    the_installation = mock.create_autospec(installation.Installation)
    the_installation.get_agent_for_room.return_value = agent

    exp_deps = the_installation.get_agent_deps_for_room.return_value
    exp_emitter = exp_deps.agui_emitter = mock.Mock(spec_set=["close"])
    exp_emitter.close = mock.AsyncMock(spec_set=())

    token = object()

    test_run.run_input = None
    the_threads.get_run.return_value = test_run

    if ari_side_effect is not None:
        the_threads.add_run_input.side_effect = ari_side_effect
    else:
        the_threads.add_run_input.return_value = test_run

    aga.from_request = mock.AsyncMock()
    exp_adapter = aga.from_request.return_value
    exp_adapter.run_input = run_input
    exp_adapter.encode_stream = mock.MagicMock()
    exp_adapter.run_stream = mock.MagicMock()
    exp_agent_stream = exp_adapter.run_stream.return_value
    exp_sse_stream = exp_adapter.encode_stream.return_value

    with expectation as expected:
        found = await agui_views.post_room_agui_thread_id_run_id(
            request,
            room_id=TEST_ROOM_ID,
            thread_id=TEST_THREAD_ID,
            run_id=TEST_RUN_ID,
            the_installation=the_installation,
            the_threads=the_threads,
            token=token,
        )

    if expected is None:
        assert found is sr.return_value

        sr.assert_called_once_with(
            exp_sse_stream,
            media_type=exp_adapter.accept,
        )

        exp_adapter.encode_stream.assert_called_once_with(tee.return_value)

        tee.assert_called_once()
        event_stream, event_list = tee.call_args_list[0].args

        assert event_stream is mpx.return_value
        assert event_list == []

        on_done = tee.call_args_list[0].kwargs["on_done"]
        assert isinstance(on_done, functools.partial)
        assert on_done.func is the_threads.save_run_events
        assert on_done.keywords == {
            "user_name": USER_NAME,
            "room_id": TEST_ROOM_ID,
            "thread_id": TEST_THREAD_ID,
            "run_id": TEST_RUN_ID,
        }

        mpx.assert_called_once_with(ces.return_value, aefd.return_value)

        ces.assert_called_once_with(exp_agent_stream)

        aefd.assert_called_once_with(exp_emitter)

        exp_adapter.run_stream.assert_called_once()
        (rs_call_0,) = exp_adapter.run_stream.call_args_list
        assert rs_call_0.args == ()
        assert rs_call_0.kwargs["deps"] is exp_deps

        # the 'agui_emitter' stream does not get closed until the
        # adapter's 'run_stream' calls its 'on_complete' callback.
        exp_emitter.close.assert_not_awaited()

        # the 'ts.save_run_usage' API does not get called until the
        # adapter's 'run_stream' calls its 'on_complete' callback.
        the_threads.save_run_usage.assert_not_awaited()

        rs_on_complete = rs_call_0.kwargs["on_complete"]

        if w_usage:
            faux_result = mock.Mock()
            faux_result.usage.return_value = agui_package.RunUsageStats(
                1,
                2,
                3,
                4,
            )
        else:
            faux_result = object()

        await rs_on_complete(faux_result)

        if w_usage:
            the_threads.save_run_usage.assert_awaited_once_with(
                user_name=USER_NAME,
                room_id=TEST_ROOM_ID,
                thread_id=TEST_THREAD_ID,
                run_id=TEST_RUN_ID,
                input_tokens=1,
                output_tokens=2,
                requests=3,
                tool_calls=4,
            )
        else:
            the_threads.save_run_usage.assert_not_awaited()

        exp_emitter.close.assert_awaited_once_with()

        the_installation.get_agent_deps_for_room.assert_called_once_with(
            TEST_ROOM_ID,
            USER_PROFILE,
            exp_adapter.run_input,
        )

        aga.from_request.assert_called_once_with(
            request=request,
            agent=agent,
        )

        the_threads.add_run_input.assert_called_once_with(
            user_name=USER_NAME,
            room_id=TEST_ROOM_ID,
            thread_id=TEST_THREAD_ID,
            run_id=TEST_RUN_ID,
            run_input=exp_adapter.run_input,
        )

        cura.assert_called_once_with(
            room_id=TEST_ROOM_ID,
            the_installation=the_installation,
            token=token,
        )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "tsurm_side_effect, expectation",
    [
        (None, no_error(205)),
        (UNKNOWN_THREAD, raises_httpexc(code=404, match="Unknown thread")),
        (THREAD_ROOM_MISMATCH, raises_httpexc(code=400, match="Thread room")),
        (UNKNOWN_RUN, raises_httpexc(code=404, match="Unknown run")),
    ],
)
@pytest.mark.parametrize(
    "w_meta",
    [
        None,
        {"label": TEST_RUN_LABEL},
    ],
)
@mock.patch("soliplex.views.agui._check_user_in_room")
async def test_post_room_agui_thread_id_run_id_meta(
    cuir,
    the_threads,
    w_meta,
    tsurm_side_effect,
    expectation,
):
    cuir.return_value = USER_NAME

    request = fastapi.Request(scope={"type": "http"})

    if w_meta is not None:
        exp_t_meta = w_meta
        r_meta = models.AGUI_RunMetadata.model_validate(w_meta)
    else:
        exp_t_meta = {}
        r_meta = models.AGUI_RunMetadata()

    the_installation = mock.create_autospec(installation.Installation)
    token = object()

    the_threads.update_run_metadata.side_effect = tsurm_side_effect

    with expectation as expected:
        found = await agui_views.post_room_agui_thread_id_run_id_meta(
            request,
            room_id=TEST_ROOM_ID,
            thread_id=TEST_THREAD_ID,
            run_id=TEST_RUN_ID,
            new_metadata=r_meta,
            the_installation=the_installation,
            the_threads=the_threads,
            token=token,
        )

    if isinstance(expected, int):
        assert isinstance(found, fastapi.Response)
        assert found.status_code == expected

    the_threads.update_run_metadata.assert_called_once_with(
        user_name=USER_NAME,
        room_id=TEST_ROOM_ID,
        thread_id=TEST_THREAD_ID,
        run_id=TEST_RUN_ID,
        run_metadata=exp_t_meta,
    )
    cuir.assert_called_once_with(
        room_id=TEST_ROOM_ID,
        the_installation=the_installation,
        token=token,
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "tssrf_side_effect, expectation",
    [
        (None, no_error(205)),
        (UNKNOWN_THREAD, raises_httpexc(code=404, match="Unknown thread")),
        (THREAD_ROOM_MISMATCH, raises_httpexc(code=400, match="Thread room")),
        (UNKNOWN_RUN, raises_httpexc(code=404, match="Unknown run")),
    ],
)
@mock.patch("soliplex.views.agui._check_user_in_room")
async def test_post_room_agui_thread_id_run_id_feedback(
    cuir,
    the_threads,
    tssrf_side_effect,
    expectation,
):
    cuir.return_value = USER_NAME

    request = fastapi.Request(scope={"type": "http"})

    r_feedback = models.AGUI_RunFeedback(
        feedback=TEST_RUN_FEEDBACK,
        reason=TEST_RUN_FEEDBACK_REASON,
    )

    the_installation = mock.create_autospec(installation.Installation)
    token = object()

    the_threads.save_run_feedback.side_effect = tssrf_side_effect

    with expectation as expected:
        found = await agui_views.post_room_agui_thread_id_run_id_feedback(
            request,
            room_id=TEST_ROOM_ID,
            thread_id=TEST_THREAD_ID,
            run_id=TEST_RUN_ID,
            new_feedback=r_feedback,
            the_installation=the_installation,
            the_threads=the_threads,
            token=token,
        )

    if isinstance(expected, int):
        assert isinstance(found, fastapi.Response)
        assert found.status_code == expected

    the_threads.save_run_feedback.assert_called_once_with(
        user_name=USER_NAME,
        room_id=TEST_ROOM_ID,
        thread_id=TEST_THREAD_ID,
        run_id=TEST_RUN_ID,
        feedback=TEST_RUN_FEEDBACK,
        reason=TEST_RUN_FEEDBACK_REASON,
    )
    cuir.assert_called_once_with(
        room_id=TEST_ROOM_ID,
        the_installation=the_installation,
        token=token,
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "tsdr_side_effect, expectation",
    [
        (None, no_error(204)),
        (UNKNOWN_THREAD, raises_httpexc(code=404, match="Unknown thread")),
        (THREAD_ROOM_MISMATCH, raises_httpexc(code=400, match="Thread room")),
    ],
)
@mock.patch("soliplex.views.agui._check_user_in_room")
async def test_delete_room_agui_thread_id(
    cuir,
    the_threads,
    test_thread,
    tsdr_side_effect,
    expectation,
):
    cuir.return_value = USER_NAME

    request = fastapi.Request(scope={"type": "http"})
    the_installation = mock.create_autospec(installation.Installation)
    token = object()

    the_threads.delete_thread.side_effect = tsdr_side_effect

    with expectation as expected:
        found = await agui_views.delete_room_agui_thread_id(
            request,
            room_id=TEST_ROOM_ID,
            thread_id=TEST_THREAD_ID,
            the_installation=the_installation,
            the_threads=the_threads,
            token=token,
        )

    if isinstance(expected, int):
        assert isinstance(found, fastapi.Response)
        assert found.status_code == expected

    the_threads.delete_thread.assert_called_once_with(
        user_name=USER_NAME,
        room_id=TEST_ROOM_ID,
        thread_id=TEST_THREAD_ID,
    )
    cuir.assert_called_once_with(
        room_id=TEST_ROOM_ID,
        the_installation=the_installation,
        token=token,
    )
