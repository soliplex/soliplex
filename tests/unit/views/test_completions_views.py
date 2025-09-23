from unittest import mock

import fastapi
import pytest

from soliplex import config
from soliplex import installation
from soliplex import models
from soliplex.views import completions as completions_views

COMPLETION_IDS = ["foo", "bar", "baz"]
COMPLETION_ID = "qux"

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

@pytest.fixture(scope="module", params=[(), COMPLETION_IDS])
def completion_configs(request):
    return {
        completion_id: mock.create_autospec(config.CompletionConfig)
        for completion_id in request.param
    }


@pytest.mark.anyio
@mock.patch("soliplex.auth.authenticate")
@mock.patch("soliplex.models.Completion.from_config")
async def test_get_chat_completions(fc, auth_fn, completion_configs):
    request = mock.create_autospec(fastapi.Request)

    the_installation = mock.create_autospec(installation.Installation)
    the_installation.get_completion_configs.return_value = (
        completion_configs
    )
    token = object()

    found = await completions_views.get_chat_completions(
        request, the_installation=the_installation, token=token,
    )

    for (found_key, found_completion), completion_id, fc_call in zip(
        found.items(),   # should already be sorted
        sorted(completion_configs),
        fc.call_args_list,
        strict=True,
    ):
        assert found_key == completion_id
        assert found_completion is fc.return_value
        assert fc_call == mock.call(completion_configs[completion_id])

    the_installation.get_completion_configs.assert_called_once_with(
        auth_fn.return_value,
    )
    auth_fn.assert_called_once_with(the_installation, token)


@pytest.mark.anyio
@mock.patch("soliplex.auth.authenticate")
@mock.patch("soliplex.models.Completion.from_config")
async def test_get_chat_completion(fc, auth_fn, completion_configs):
    COMPLETION_ID = "foo"

    request = mock.create_autospec(fastapi.Request)

    the_installation = mock.create_autospec(installation.Installation)

    if COMPLETION_ID not in completion_configs:
        the_installation.get_completion_config.side_effect = KeyError(
            "testing"
        )
    else:
        the_installation.get_completion_config.return_value = (
            completion_configs[COMPLETION_ID]
        )

    token = object()

    if COMPLETION_ID not in completion_configs:
        with pytest.raises(fastapi.HTTPException) as exc:
            await completions_views.get_chat_completion(
                request,
                COMPLETION_ID,
                the_installation=the_installation,
                token=token,
            )

        assert exc.value.status_code == 404
        assert exc.value.detail == "No such completion: foo"

    else:
        found = await completions_views.get_chat_completion(
            request,
            COMPLETION_ID,
            the_installation=the_installation,
            token=token,
        )

        assert found is fc.return_value
        fc.assert_called_once_with(completion_configs[COMPLETION_ID])

    the_installation.get_completion_config.assert_called_once_with(
        COMPLETION_ID, auth_fn.return_value,
    )
    auth_fn.assert_called_once_with(the_installation, token)


@pytest.mark.anyio
@pytest.mark.parametrize("w_auth_user, exp_user", [
    ({}, UNKNOWN_USER),
    (AUTH_USER, AUTH_USER),
])
@mock.patch("soliplex.auth.authenticate")
async def test_post_chat_completion_miss(auth_fn, w_auth_user, exp_user):
    auth_fn.return_value = w_auth_user

    request = object()
    chat_request = mock.create_autospec(models.ChatCompletionRequest)
    chat_request.messages = ()
    the_installation = mock.create_autospec(installation.Installation)
    token = object()

    the_installation.get_agent_for_completion.side_effect = (
        KeyError("testing")
    )

    with pytest.raises(fastapi.HTTPException) as exc:
        await completions_views.post_chat_completion(
            request, "nonesuch", chat_request, the_installation, token,
        )

    assert exc.value.status_code == 404

    auth_fn.assert_called_once_with(the_installation, token)


@pytest.mark.anyio
@pytest.mark.parametrize("w_auth_user, exp_user", [
    ({}, UNKNOWN_USER),
    (AUTH_USER, AUTH_USER),
])
@pytest.mark.parametrize("w_msg", [False, True])
@mock.patch("soliplex.completions.openai_chat_completion")
@mock.patch("soliplex.auth.authenticate")
async def test_post_chat_completion_hit(
    auth_fn, occ, w_msg, w_auth_user, exp_user,
):
    auth_fn.return_value = w_auth_user

    request = object()
    chat_request = mock.create_autospec(models.ChatCompletionRequest)

    if w_msg:
        content = "test message"
        chat_request.messages = [
            models.ChatMessage(role="user", content=content)
        ]
    else:
        chat_request.messages = ()

    the_installation = mock.create_autospec(installation.Installation)
    token = object()

    response = await completions_views.post_chat_completion(
        request, COMPLETION_ID, chat_request, the_installation, token,
    )

    assert response is occ.return_value

    exp_user_profile = models.UserProfile(**exp_user)
    exp_agent_deps = models.AgentDependencies(user=exp_user_profile)
    occ.assert_awaited_once_with(
        the_installation.get_agent_for_completion.return_value,
        exp_agent_deps,
        chat_request,
    )

    the_installation.get_agent_for_completion.assert_called_once_with(
        COMPLETION_ID, auth_fn.return_value
    )

    auth_fn.assert_called_once_with(the_installation, token)
