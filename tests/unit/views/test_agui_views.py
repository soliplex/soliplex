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
TEST_THREAD_ID = "test-thread-123"
TEST_THREAD = agui_thread.Thread(
    room_id=TEST_ROOM_ID,
    thread_id=TEST_THREAD_ID,
)
TEST_PARENT_RUN_ID = "test-run-234"
TEST_PARENT_RUN = agui_thread.Run(
    run_id=TEST_PARENT_RUN_ID,
)
TEST_RUN_ID = "test-run-456"


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


def raises_httpexc(*, match, code) -> pytest.raises:
    def _check(exc):
        return exc.status_code == code

    return pytest.raises(fastapi.HTTPException, match=match, check=_check)


@pytest.mark.anyio
@pytest.mark.parametrize("w_miss", ["room"])
@mock.patch("soliplex.auth.authenticate")
async def test_post_room_agui_errors(
    auth_fn,
    run_input,
    w_miss,
):
    auth_fn.return_value = {}

    request = fastapi.Request(scope={"type": "http"})
    new_thread_request = models.AGUI_NewThreadRequest.model_validate({})
    the_installation = mock.create_autospec(installation.Installation)
    the_threads = mock.create_autospec(agui_thread.Threads)
    token = object()

    if w_miss == "room":
        the_installation.get_room_config.side_effect = KeyError("testing")
        expectation = raises_httpexc(code=404, match="No such room")
    else:  # pragma NO COVER
        return

    with expectation:
        await agui_views.post_room_agui(
            request,
            room_id=TEST_ROOM_ID,
            new_thread_request=new_thread_request,
            the_installation=the_installation,
            the_threads=the_threads,
            token=token,
        )

    the_installation.get_room_config.assert_called_once_with(
        TEST_ROOM_ID,
        user=auth_fn.return_value,
    )
    auth_fn.assert_called_once_with(the_installation, token)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "w_meta",
    [
        {},
        {"name": "NAME"},
        {"name": "NAME", "description": "DESCRIPTION"},
    ],
)
@pytest.mark.parametrize(
    "w_auth_user, exp_user",
    [
        ({}, UNKNOWN_USER),
        (AUTH_USER, AUTH_USER),
    ],
)
@mock.patch("soliplex.auth.authenticate")
async def test_post_room_agui(
    auth_fn,
    run_input,
    w_auth_user,
    exp_user,
    w_meta,
):
    auth_fn.return_value = w_auth_user
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
    the_threads.new_thread.return_value = TEST_THREAD

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

    the_threads.new_thread.assert_called_once_with(
        room_id=TEST_ROOM_ID,
        user_name=exp_user["preferred_username"],
        metadata=exp_meta,
    )


@pytest.mark.anyio
@pytest.mark.parametrize("w_miss", ["room", "thread", "run", "parent"])
@mock.patch("pydantic_ai.ui.ag_ui.AGUIAdapter")
@mock.patch("soliplex.auth.authenticate")
async def test_post_room_agui_thread_id_errors(
    auth_fn,
    aga,
    run_input,
    w_miss,
):
    auth_fn.return_value = {}
    aga.from_request = mock.AsyncMock()

    token = object()

    request = fastapi.Request(scope={"type": "http"})
    new_run_request = models.AGUI_NewRunRequest.model_validate({})

    the_installation = mock.create_autospec(installation.Installation)
    the_threads = mock.create_autospec(agui_thread.Threads)
    exp_thread = the_threads.get_thread.return_value = mock.create_autospec(
        agui_thread.Thread
    )

    if w_miss == "room":
        the_installation.get_room_config.side_effect = KeyError("testing")
        expectation = raises_httpexc(code=404, match="No such room")
    elif w_miss == "thread":
        the_threads.get_thread.side_effect = agui_thread.UnknownThread(
            user_name="user-name",
            thread_id=TEST_THREAD_ID,
        )
        expectation = raises_httpexc(code=404, match="No such thread")
    elif w_miss == "parent":
        exp_thread.new_run.side_effect = agui_thread.MissingParentRunId(
            "testing"
        )
        expectation = raises_httpexc(code=400, match="No such parent")
    else:  # pragma NO COVER
        return

    with expectation:
        await agui_views.post_room_agui_thread_id(
            request,
            room_id=TEST_ROOM_ID,
            thread_id=TEST_THREAD_ID,
            new_run_request=new_run_request,
            the_installation=the_installation,
            the_threads=the_threads,
            token=token,
        )

    the_installation.get_room_config.assert_called_once_with(
        TEST_ROOM_ID,
        user=auth_fn.return_value,
    )
    auth_fn.assert_called_once_with(the_installation, token)


@pytest.mark.anyio
@pytest.mark.parametrize("w_parent_run_id", [None, TEST_PARENT_RUN_ID])
@pytest.mark.parametrize(
    "w_meta",
    [
        {},
        {"label": "LABEL"},
    ],
)
@pytest.mark.parametrize(
    "w_auth_user, exp_user",
    [
        ({}, UNKNOWN_USER),
        (AUTH_USER, AUTH_USER),
    ],
)
@mock.patch("soliplex.auth.authenticate")
async def test_post_room_agui_thread_id(
    auth_fn,
    run_input,
    w_auth_user,
    exp_user,
    w_meta,
    w_parent_run_id,
):
    auth_fn.return_value = w_auth_user
    token = object()

    request = fastapi.Request(scope={"type": "http"})
    nrr = {}

    if w_parent_run_id:
        nrr = {"parent_run_id": TEST_PARENT_RUN_ID}

    if w_meta:
        nrr["metadata"] = w_meta
        exp_meta = agui_thread.RunMetadata(**w_meta)
    else:
        exp_meta = None

    new_run_request = models.AGUI_NewRunRequest.model_validate(nrr)

    the_installation = mock.create_autospec(installation.Installation)
    the_threads = mock.create_autospec(agui_thread.Threads)
    exp_thread = the_threads.get_thread.return_value = mock.create_autospec(
        agui_thread.Thread,
    )
    exp_thread.new_run.return_value = mock.create_autospec(
        agui_thread.Run,
        run_id=TEST_RUN_ID,
        run_input=run_input,
    )

    found = await agui_views.post_room_agui_thread_id(
        request,
        room_id=TEST_ROOM_ID,
        thread_id=TEST_THREAD_ID,
        new_run_request=new_run_request,
        the_installation=the_installation,
        the_threads=the_threads,
        token=token,
    )

    assert found.room_id == TEST_ROOM_ID
    assert found.thread_id == TEST_THREAD_ID
    assert found.metadata == new_run_request.metadata
    assert found.parent_run_id == w_parent_run_id

    exp_thread.new_run.assert_called_once_with(
        metadata=exp_meta,
        parent_run_id=w_parent_run_id,
    )


@pytest.mark.anyio
@pytest.mark.parametrize("w_miss", ["room", "thread", "run", "parent"])
@mock.patch("pydantic_ai.ui.ag_ui.AGUIAdapter")
@mock.patch("soliplex.auth.authenticate")
async def test_post_room_agui_thread_id_run_id_errors(
    auth_fn,
    aga,
    run_input,
    w_miss,
):
    auth_fn.return_value = {}
    aga.from_request = mock.AsyncMock()

    token = object()

    request = fastapi.Request(scope={"type": "http"})

    the_installation = mock.create_autospec(installation.Installation)
    the_threads = mock.create_autospec(agui_thread.Threads)
    exp_thread = the_threads.get_thread.return_value = mock.create_autospec(
        agui_thread.Thread
    )
    exp_run = exp_thread.get_run.return_value = mock.create_autospec(
        agui_thread.Run
    )
    exp_run.check_run_input.return_value = None

    if w_miss == "room":
        the_installation.get_agent_for_room.side_effect = KeyError("testing")
        expectation = raises_httpexc(code=404, match="No such room")
    elif w_miss == "thread":
        the_threads.get_thread.side_effect = agui_thread.UnknownThread(
            user_name="user-name",
            thread_id=TEST_THREAD_ID,
        )
        expectation = raises_httpexc(code=404, match="No such thread")
    elif w_miss == "run":
        exp_thread.get_run.side_effect = agui_thread.UnknownRunId("testing")
        expectation = raises_httpexc(code=404, match="No such run")
    elif w_miss == "parent":
        exp_run.check_run_input.side_effect = agui_thread.RunInputMismatch(
            "testing"
        )
        expectation = raises_httpexc(code=400, match="Mismatched 'run_input'")
    else:  # pragma NO COVER
        return

    with expectation:
        await agui_views.post_room_agui_thread_id_run_id(
            request,
            room_id=TEST_ROOM_ID,
            thread_id=TEST_THREAD_ID,
            run_id=TEST_RUN_ID,
            the_installation=the_installation,
            the_threads=the_threads,
            token=token,
        )

    the_installation.get_agent_for_room.assert_called_once_with(
        TEST_ROOM_ID,
        user=auth_fn.return_value,
    )
    auth_fn.assert_called_once_with(the_installation, token)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "w_auth_user, exp_user",
    [
        ({}, UNKNOWN_USER),
        (AUTH_USER, AUTH_USER),
    ],
)
@mock.patch("fastapi.responses.StreamingResponse")
@mock.patch("pydantic_ai.ui.ag_ui.AGUIAdapter")
@mock.patch("soliplex.agui.parser.EventStreamParser")
@mock.patch("soliplex.auth.authenticate")
async def test_post_room_agui_thread_id_run_id(
    auth_fn,
    esp,
    aga,
    sr,
    run_input,
    w_auth_user,
    exp_user,
):
    auth_fn.return_value = w_auth_user
    exp_user_profile = models.UserProfile(**exp_user)

    agent = object()
    token = object()

    request = fastapi.Request(scope={"type": "http"})

    the_installation = mock.create_autospec(installation.Installation)
    the_installation.get_agent_for_room.return_value = agent

    aga.from_request = mock.AsyncMock()
    exp_adapter = aga.from_request.return_value
    exp_adapter.run_input = run_input
    exp_adapter.encode_stream = mock.MagicMock()
    exp_adapter.run_stream = mock.MagicMock()

    the_threads = mock.create_autospec(agui_thread.Threads)
    exp_thread = the_threads.get_thread.return_value
    exp_run = exp_thread.get_run.return_value
    exp_run.check_run_input = mock.Mock(return_value=None)

    exp_deps = models.AgentDependencies(
        the_installation=the_installation,
        user=exp_user_profile,
    )

    exp_agent_stream = exp_adapter.run_stream.return_value

    exp_esp = esp.return_value

    exp_esp_stream = exp_esp.parse_stream.return_value

    exp_sse_stream = exp_adapter.encode_stream.return_value

    found = await agui_views.post_room_agui_thread_id_run_id(
        request,
        room_id=TEST_ROOM_ID,
        thread_id=TEST_THREAD_ID,
        run_id=TEST_RUN_ID,
        the_installation=the_installation,
        the_threads=the_threads,
        token=token,
    )

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

    the_installation.get_agent_for_room.assert_called_once_with(
        TEST_ROOM_ID,
        user=auth_fn.return_value,
    )
    auth_fn.assert_called_once_with(the_installation, token)
