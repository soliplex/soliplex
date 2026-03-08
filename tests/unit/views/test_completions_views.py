from unittest import mock

import fastapi
import pytest

from soliplex import installation
from soliplex import models
from soliplex.config import completions as config_completions
from soliplex.views import completions as completions_views

COMPLETION_IDS = ["foo", "bar", "baz"]
COMPLETION_ID = "qux"

USER_NAME = "phreddy"
GIVEN_NAME = "Phred"
FAMILY_NAME = "Phlyntstone"
EMAIL = "phreddy@example.com"

AUTH_USER_CLAIMS = {
    "preferred_username": USER_NAME,
    "given_name": GIVEN_NAME,
    "family_name": FAMILY_NAME,
    "email": EMAIL,
}

UNKNOWN_USER_CLAIMS = {
    "preferred_username": "<unknown>",
    "given_name": "<unknown>",
    "family_name": "<unknown>",
    "email": "<unknown>",
}


@pytest.fixture(scope="module", params=[(), COMPLETION_IDS])
def completion_configs(request):
    return {
        completion_id: mock.create_autospec(
            config_completions.CompletionConfig,
        )
        for completion_id in request.param
    }


@pytest.mark.anyio
@mock.patch("soliplex.models.Completion.from_config")
async def test_get_chat_completions(fc, completion_configs):
    request = mock.create_autospec(fastapi.Request)

    the_installation = mock.create_autospec(installation.Installation)
    the_installation.get_completion_configs.return_value = completion_configs

    found = await completions_views.get_chat_completions(
        request,
        the_installation=the_installation,
        the_user_claims=AUTH_USER_CLAIMS,
    )

    for (found_key, found_completion), completion_id, fc_call in zip(
        found.items(),  # should already be sorted
        sorted(completion_configs),
        fc.call_args_list,
        strict=True,
    ):
        assert found_key == completion_id
        assert found_completion is fc.return_value
        assert fc_call == mock.call(completion_configs[completion_id])

    the_installation.get_completion_configs.assert_awaited_once_with(
        user=AUTH_USER_CLAIMS,
    )


@pytest.mark.anyio
@mock.patch("soliplex.models.Completion.from_config")
async def test_get_chat_completion(fc, completion_configs):
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

    if COMPLETION_ID not in completion_configs:
        with pytest.raises(fastapi.HTTPException) as exc:
            await completions_views.get_chat_completion(
                request,
                COMPLETION_ID,
                the_installation=the_installation,
                the_user_claims=AUTH_USER_CLAIMS,
            )

        assert exc.value.status_code == 404
        assert exc.value.detail == "No such completion: foo"

    else:
        found = await completions_views.get_chat_completion(
            request,
            COMPLETION_ID,
            the_installation=the_installation,
            the_user_claims=AUTH_USER_CLAIMS,
        )

        assert found is fc.return_value
        fc.assert_called_once_with(completion_configs[COMPLETION_ID])

    the_installation.get_completion_config.assert_awaited_once_with(
        completion_id=COMPLETION_ID,
        user=AUTH_USER_CLAIMS,
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "w_auth_user, exp_user",
    [
        ({}, UNKNOWN_USER_CLAIMS),
        (AUTH_USER_CLAIMS, AUTH_USER_CLAIMS),
    ],
)
async def test_post_chat_completion_miss(w_auth_user, exp_user):
    request = object()
    chat_request = mock.create_autospec(models.ChatCompletionRequest)
    chat_request.messages = ()
    the_installation = mock.create_autospec(installation.Installation)

    the_installation.get_agent_for_completion.side_effect = KeyError("testing")

    with pytest.raises(fastapi.HTTPException) as exc:
        await completions_views.post_chat_completion(
            request=request,
            completion_id="nonesuch",
            chat_request=chat_request,
            the_installation=the_installation,
            the_user_claims=w_auth_user,
        )

    assert exc.value.status_code == 404


@pytest.mark.anyio
@pytest.mark.parametrize(
    "w_auth_user, exp_user",
    [
        ({}, UNKNOWN_USER_CLAIMS),
        (AUTH_USER_CLAIMS, AUTH_USER_CLAIMS),
    ],
)
@pytest.mark.parametrize("w_msg", [False, True])
@mock.patch("soliplex.completions.openai_chat_completion")
async def test_post_chat_completion_hit(
    occ,
    w_msg,
    w_auth_user,
    exp_user,
):
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

    response = await completions_views.post_chat_completion(
        request=request,
        completion_id=COMPLETION_ID,
        chat_request=chat_request,
        the_installation=the_installation,
        the_user_claims=w_auth_user,
    )

    assert response is occ.return_value

    exp_user_profile = models.UserProfile(**exp_user)
    occ.assert_awaited_once_with(
        the_installation.get_agent_for_completion.return_value,
        the_installation.get_agent_deps_for_completion.return_value,
        chat_request,
    )

    the_installation.get_agent_for_completion.assert_awaited_once_with(
        completion_id=COMPLETION_ID,
        user=w_auth_user,
    )

    the_installation.get_agent_deps_for_completion.assert_awaited_once_with(
        completion_id=COMPLETION_ID,
        user=exp_user_profile,
    )
