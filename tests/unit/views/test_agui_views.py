import contextlib
import dataclasses
from unittest import mock

import fastapi
import pytest
from ag_ui import core as agui_core

from soliplex import installation
from soliplex import models
from soliplex.agui import thread as agui_thread
from soliplex.views import agui as agui_views

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
TEST_THREAD = agui_thread.Thread(
    room_id=TEST_ROOM_ID,
    thread_id=TEST_THREAD_ID,
)

TEST_PARENT_RUN_ID = "test-run-234"
TEST_PARENT_RUN = agui_thread.Run(
    run_id=TEST_PARENT_RUN_ID,
)
TEST_RUN_ID = "test-run-456"
TEST_RUN_LABEL = "My test run #456"

EMPTY_RUN_INPUT = agui_core.RunAgentInput(
    thread_id=TEST_THREAD_ID,
    run_id=TEST_RUN_ID,
    state=None,
    messages=(),
    tools=(),
    context=(),
    forwarded_props=None,
)

TEST_RUN = agui_thread.Run(
    run_id=TEST_RUN_ID,
    run_input=EMPTY_RUN_INPUT,
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


no_error = contextlib.nullcontext


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
@mock.patch("soliplex.auth.authenticate")
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
@mock.patch("soliplex.auth.authenticate")
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
@pytest.mark.parametrize(
    "w_miss, w_room_id, expectation",
    [
        (False, TEST_ROOM_ID, no_error()),
        (
            False,
            OTHER_ROOM_ID,
            raises_httpexc(code=400, match="Expected thread.room_id:"),
        ),
        (True, TEST_ROOM_ID, raises_httpexc(code=404, match="No such thread")),
    ],
)
async def test__check_user_thread(w_miss, w_room_id, expectation):
    the_threads = mock.create_autospec(agui_thread.Threads)

    if w_miss:
        the_threads.get_thread.side_effect = agui_thread.UnknownThread(
            user_name=USER_NAME,
            thread_id=TEST_THREAD_ID,
        )
    else:
        the_threads.get_thread.return_value = agui_thread.Thread(
            room_id=w_room_id,
            thread_id=TEST_THREAD_ID,
        )

    with expectation as expected:
        found = await agui_views._check_user_thread(
            room_id=TEST_ROOM_ID,
            thread_id=TEST_THREAD_ID,
            user_name=USER_NAME,
            the_threads=the_threads,
        )

    if expected is None:
        assert found is the_threads.get_thread.return_value

    the_threads.get_thread.assert_called_once_with(
        user_name=USER_NAME,
        thread_id=TEST_THREAD_ID,
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "w_miss, expectation",
    [
        (False, no_error()),
        (True, raises_httpexc(code=404, match="No such run")),
    ],
)
async def test__check_user_thread_run(w_miss, expectation):
    thread = mock.create_autospec(agui_thread.Thread)

    if w_miss:
        thread.get_run.side_effect = agui_thread.UnknownRunId(
            run_id=TEST_RUN_ID,
        )
    else:
        thread.get_run.return_value = agui_thread.Run(
            run_id=TEST_RUN_ID,
        )

    with expectation as expected:
        found = await agui_views._check_user_thread_run(
            run_id=TEST_RUN_ID,
            thread=thread,
        )

    if expected is None:
        assert found is thread.get_run.return_value

    thread.get_run.assert_called_once_with(run_id=TEST_RUN_ID)


@pytest.mark.anyio
@pytest.mark.parametrize("w_meta", [False, True])
@mock.patch("soliplex.views.agui._check_user_in_room")
async def test_get_room_agui(cuir, w_meta):
    cuir.return_value = USER_NAME

    request = fastapi.Request(scope={"type": "http"})
    the_installation = mock.create_autospec(installation.Installation)
    the_threads = mock.create_autospec(agui_thread.Threads)
    token = object()

    thr_replace = {"runs": {}}

    if w_meta:
        thr_replace["metadata"] = agui_thread.ThreadMetadata(
            name=TEST_THREAD_NAME,
        )

    the_threads.user_threads.return_value = {
        TEST_THREAD_ID: dataclasses.replace(TEST_THREAD, **thr_replace),
    }

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
    if w_meta:
        assert m_thread.metadata.name == TEST_THREAD_NAME
    else:
        assert m_thread.metadata is None

    cuir.assert_called_once_with(TEST_ROOM_ID, the_installation, token)


@pytest.mark.anyio
@pytest.mark.parametrize("w_meta", [False, True])
@mock.patch("soliplex.views.agui._check_user_thread")
@mock.patch("soliplex.views.agui._check_user_in_room")
async def test_get_room_agui_thread_id(cuir, cut, w_meta):
    cuir.return_value = USER_NAME

    thr_replace = {"runs": {TEST_RUN_ID: TEST_RUN}}

    if w_meta:
        thr_replace["metadata"] = agui_thread.ThreadMetadata(
            name=TEST_THREAD_NAME,
        )

    thread = dataclasses.replace(TEST_THREAD, **thr_replace)

    cut.return_value = thread

    request = fastapi.Request(scope={"type": "http"})
    the_installation = mock.create_autospec(installation.Installation)
    the_threads = mock.create_autospec(agui_thread.Threads)
    token = object()

    found = await agui_views.get_room_agui_thread_id(
        request=request,
        room_id=TEST_ROOM_ID,
        thread_id=TEST_THREAD_ID,
        the_installation=the_installation,
        the_threads=the_threads,
        token=token,
    )

    assert found.room_id == TEST_ROOM_ID
    assert found.thread_id == TEST_THREAD_ID

    assert found.runs == {
        TEST_RUN_ID: models.AGUI_Run.from_run_and_thread(
            a_run=TEST_RUN,
            a_thread=TEST_THREAD,
        ),
    }

    if w_meta:
        assert found.metadata.name == TEST_THREAD_NAME
    else:
        assert found.metadata is None

    cut.assert_called_once_with(
        TEST_ROOM_ID,
        TEST_THREAD_ID,
        USER_NAME,
        the_threads,
    )
    cuir.assert_called_once_with(TEST_ROOM_ID, the_installation, token)


@pytest.mark.anyio
@pytest.mark.parametrize("w_room_meta", [False, True])
@mock.patch("soliplex.views.agui._check_user_thread_run")
@mock.patch("soliplex.views.agui._check_user_thread")
@mock.patch("soliplex.views.agui._check_user_in_room")
async def test_get_room_agui_thread_id_run_id(cuir, cut, cutr, w_room_meta):
    cuir.return_value = USER_NAME

    run_replace = {"events": AGUI_EVENTS}

    if w_room_meta:
        run_replace["metadata"] = agui_thread.RunMetadata(
            label=TEST_RUN_LABEL,
        )

    run = dataclasses.replace(TEST_RUN, **run_replace)
    cutr.return_value = run

    exp_thread = dataclasses.replace(TEST_THREAD, runs={TEST_RUN_ID: TEST_RUN})
    cut.return_value = exp_thread

    request = fastapi.Request(scope={"type": "http"})
    the_installation = mock.create_autospec(installation.Installation)
    the_threads = mock.create_autospec(agui_thread.Threads)
    token = object()

    found = await agui_views.get_room_agui_thread_id_run_id(
        request=request,
        room_id=TEST_ROOM_ID,
        thread_id=TEST_THREAD_ID,
        run_id=TEST_RUN_ID,
        the_installation=the_installation,
        the_threads=the_threads,
        token=token,
    )

    assert found.room_id == TEST_ROOM_ID
    assert found.thread_id == TEST_THREAD_ID
    assert found.run_id == TEST_RUN_ID

    assert found.events == AGUI_EVENTS

    if w_room_meta:
        assert found.metadata.label == TEST_RUN_LABEL
    else:
        assert found.metadata is None

    cutr.assert_called_once_with(exp_thread, TEST_RUN_ID)
    cut.assert_called_once_with(
        TEST_ROOM_ID,
        TEST_THREAD_ID,
        USER_NAME,
        the_threads,
    )
    cuir.assert_called_once_with(TEST_ROOM_ID, the_installation, token)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "w_meta",
    [
        {},
        {"name": "NAME"},
        {"name": "NAME", "description": "DESCRIPTION"},
    ],
)
@mock.patch("soliplex.views.agui._check_user_in_room")
async def test_post_room_agui(
    cuir,
    run_input,
    w_meta,
):
    cuir.return_value = USER_NAME

    token = object()

    request = fastapi.Request(scope={"type": "http"})
    if w_meta:
        ntr = {"metadata": w_meta}
        new_thread_request = models.AGUI_NewThreadRequest.model_validate(ntr)
        exp_meta = agui_thread.ThreadMetadata(**w_meta)
    else:
        new_thread_request = models.AGUI_NewThreadRequest()
        exp_meta = None

    the_installation = mock.create_autospec(installation.Installation)
    the_threads = mock.create_autospec(agui_thread.Threads)
    exp_thread = the_threads.new_thread.return_value = dataclasses.replace(
        TEST_THREAD,
        runs={},
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

    ((first_run_id, first_run),) = list(exp_thread.runs.items())

    m_run = found.runs[first_run_id]
    assert m_run.room_id == TEST_ROOM_ID
    assert m_run.thread_id == TEST_THREAD_ID
    assert m_run.parent_run_id is None

    the_threads.new_thread.assert_called_once_with(
        room_id=TEST_ROOM_ID,
        user_name=USER_NAME,
        metadata=exp_meta,
    )

    cuir.assert_called_once_with(TEST_ROOM_ID, the_installation, token)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "w_parent_id, missing_parent, expectation",
    [
        (None, False, no_error()),
        (TEST_PARENT_RUN_ID, False, no_error()),
        (
            TEST_PARENT_RUN_ID,
            True,
            raises_httpexc(code=400, match="No such parent"),
        ),
    ],
)
@pytest.mark.parametrize(
    "w_meta",
    [
        {},
        {"label": "LABEL"},
    ],
)
@mock.patch("soliplex.views.agui._check_user_thread")
@mock.patch("soliplex.views.agui._check_user_in_room")
async def test_post_room_agui_thread_id(
    cuir,
    cut,
    run_input,
    w_meta,
    w_parent_id,
    missing_parent,
    expectation,
):
    cuir.return_value = USER_NAME

    request = fastapi.Request(scope={"type": "http"})
    nrr = {}

    if w_parent_id:
        nrr = {"parent_run_id": TEST_PARENT_RUN_ID}

    if w_meta:
        nrr["metadata"] = w_meta
        exp_meta = agui_thread.RunMetadata(**w_meta)
    else:
        exp_meta = None

    new_run_request = models.AGUI_NewRunRequest.model_validate(nrr)

    the_installation = mock.create_autospec(installation.Installation)
    the_threads = mock.create_autospec(agui_thread.Threads)
    token = object()

    exp_thread = mock.create_autospec(
        agui_thread.Thread,
        room_id=TEST_ROOM_ID,
    )
    cut.return_value = exp_thread

    if missing_parent:
        exp_thread.new_run.side_effect = agui_thread.MissingParentRunId(
            TEST_PARENT_RUN_ID,
        )
    else:
        exp_thread.new_run.return_value = mock.create_autospec(
            agui_thread.Run,
            run_id=TEST_RUN_ID,
            run_input=run_input,
            events=[],
        )

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
        assert found.room_id == TEST_ROOM_ID
        assert found.thread_id == TEST_THREAD_ID
        assert found.metadata == new_run_request.metadata
        assert found.parent_run_id == w_parent_id

        exp_thread.new_run.assert_called_once_with(
            metadata=exp_meta,
            parent_run_id=w_parent_id,
        )

        cut.assert_called_once_with(
            TEST_ROOM_ID,
            TEST_THREAD_ID,
            USER_NAME,
            the_threads,
        )
        cuir.assert_called_once_with(TEST_ROOM_ID, the_installation, token)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "w_meta",
    [
        None,
        {"name": TEST_THREAD_NAME},
        {"name": TEST_THREAD_NAME, "description": TEST_THREAD_DESC},
    ],
)
@mock.patch("soliplex.views.agui._check_user_in_room")
async def test_post_room_agui_thread_id_meta(cuir, w_meta):
    cuir.return_value = USER_NAME

    request = fastapi.Request(scope={"type": "http"})

    if w_meta is not None:
        exp_t_meta = agui_thread.ThreadMetadata(**w_meta)
        r_meta = models.AGUI_ThreadMetadata.model_validate(w_meta)
    else:
        exp_t_meta = None
        r_meta = models.AGUI_ThreadMetadata()

    the_installation = mock.create_autospec(installation.Installation)
    the_threads = mock.create_autospec(agui_thread.Threads)
    token = object()

    found = await agui_views.post_room_agui_thread_id_meta(
        request,
        room_id=TEST_ROOM_ID,
        thread_id=TEST_THREAD_ID,
        new_metadata=r_meta,
        the_installation=the_installation,
        the_threads=the_threads,
        token=token,
    )

    assert isinstance(found, fastapi.Response)
    assert found.status_code == 205

    the_threads.update_thread.assert_called_once_with(
        user_name=USER_NAME,
        thread_id=TEST_THREAD_ID,
        metadata=exp_t_meta,
    )
    cuir.assert_called_once_with(TEST_ROOM_ID, the_installation, token)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "bad_run_input, expectation",
    [
        (False, no_error()),
        (True, raises_httpexc(code=400, match="Mismatched 'run_input'")),
    ],
)
@mock.patch("fastapi.responses.StreamingResponse")
@mock.patch("pydantic_ai.ui.ag_ui.AGUIAdapter")
@mock.patch("soliplex.agui.parser.EventStreamParser")
@mock.patch("soliplex.views.agui._check_user_thread_run")
@mock.patch("soliplex.views.agui._check_user_thread")
@mock.patch("soliplex.views.agui._check_user_room_agent")
async def test_post_room_agui_thread_id_run_id(
    cura,
    cut,
    cutr,
    esp,
    aga,
    sr,
    run_input,
    bad_run_input,
    expectation,
):
    USER_PROFILE = models.UserProfile(**AUTH_USER)
    agent = object()
    cura.return_value = (USER_NAME, USER_PROFILE, agent)

    request = fastapi.Request(scope={"type": "http"})

    the_installation = mock.create_autospec(installation.Installation)
    the_installation.get_agent_for_room.return_value = agent
    the_threads = mock.create_autospec(agui_thread.Threads)
    token = object()

    exp_thread = mock.create_autospec(agui_thread.Thread)
    cut.return_value = exp_thread

    exp_run = mock.create_autospec(agui_thread.Run)
    cutr.return_value = exp_run

    if bad_run_input:
        exp_run.check_run_input.side_effect = agui_thread.RunInputMismatch(
            "testing",
        )
    else:
        exp_run.check_run_input.return_value = None

    exp_deps = models.AgentDependencies(
        the_installation=the_installation,
        user=USER_PROFILE,
    )

    aga.from_request = mock.AsyncMock()
    exp_adapter = aga.from_request.return_value
    exp_adapter.run_input = run_input
    exp_adapter.encode_stream = mock.MagicMock()
    exp_adapter.run_stream = mock.MagicMock()
    exp_agent_stream = exp_adapter.run_stream.return_value
    exp_esp = esp.return_value
    exp_esp_stream = exp_esp.parse_stream.return_value
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

        exp_adapter.encode_stream.assert_called_once_with(exp_esp_stream)

        exp_esp.parse_stream.assert_called_once_with(exp_agent_stream)

        esp.assert_called_once_with(exp_adapter.run_input, run=exp_run)

        exp_adapter.run_stream.assert_called_once_with(deps=exp_deps)

        aga.from_request.assert_called_once_with(
            request=request,
            agent=agent,
        )

        cutr.assert_called_once_with(exp_thread, TEST_RUN_ID)
        cut.assert_called_once_with(
            TEST_ROOM_ID,
            TEST_THREAD_ID,
            USER_NAME,
            the_threads,
        )
        cura.assert_called_once_with(TEST_ROOM_ID, the_installation, token)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "w_meta",
    [
        None,
        {"label": TEST_RUN_LABEL},
    ],
)
@mock.patch("soliplex.views.agui._check_user_thread")
@mock.patch("soliplex.views.agui._check_user_in_room")
async def test_post_room_agui_thread_id_run_id_meta(cuir, cut, w_meta):
    cuir.return_value = USER_NAME
    exp_thread = mock.create_autospec(
        agui_thread.Thread,
        room_id=TEST_ROOM_ID,
    )
    cut.return_value = exp_thread

    request = fastapi.Request(scope={"type": "http"})

    if w_meta is not None:
        exp_t_meta = agui_thread.RunMetadata(**w_meta)
        r_meta = models.AGUI_RunMetadata.model_validate(w_meta)
    else:
        exp_t_meta = None
        r_meta = models.AGUI_RunMetadata()

    the_installation = mock.create_autospec(installation.Installation)
    the_threads = mock.create_autospec(agui_thread.Threads)
    token = object()

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

    assert isinstance(found, fastapi.Response)
    assert found.status_code == 205

    exp_thread.update_run.assert_called_once_with(
        run_id=TEST_RUN_ID,
        metadata=exp_t_meta,
    )
    cut.assert_called_once_with(
        TEST_ROOM_ID,
        TEST_THREAD_ID,
        USER_NAME,
        the_threads,
    )
    cuir.assert_called_once_with(TEST_ROOM_ID, the_installation, token)


@pytest.mark.anyio
@mock.patch("soliplex.views.agui._check_user_thread")
@mock.patch("soliplex.views.agui._check_user_in_room")
async def test_delete_room_agui_thread_id(cuir, cut):
    cuir.return_value = USER_NAME

    request = fastapi.Request(scope={"type": "http"})
    the_installation = mock.create_autospec(installation.Installation)
    the_threads = mock.create_autospec(agui_thread.Threads)
    token = object()

    exp_thread = mock.create_autospec(agui_thread.Thread)
    cut.return_value = exp_thread

    the_threads.delete_thread.return_value = None

    found = await agui_views.delete_room_agui_thread_id(
        request,
        room_id=TEST_ROOM_ID,
        thread_id=TEST_THREAD_ID,
        the_installation=the_installation,
        the_threads=the_threads,
        token=token,
    )

    assert isinstance(found, fastapi.Response)
    assert found.status_code == 204

    the_threads.delete_thread.assert_called_once_with(
        user_name=USER_NAME,
        thread_id=TEST_THREAD_ID,
    )
    cut.assert_called_once_with(
        TEST_ROOM_ID,
        TEST_THREAD_ID,
        USER_NAME,
        the_threads,
    )
    cuir.assert_called_once_with(TEST_ROOM_ID, the_installation, token)
