from unittest import mock

import fastapi
import pytest

from soliplex import completions
from soliplex import config
from soliplex import installation

COMPLETION_IDS = ["foo", "bar", "baz"]

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

    found = await completions.get_chat_completions(
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
    the_installation.get_completion_configs.return_value = (
        completion_configs
    )
    token = object()

    if COMPLETION_ID not in completion_configs:
        with pytest.raises(fastapi.HTTPException) as exc:
            await completions.get_chat_completion(
                request,
                COMPLETION_ID,
                the_installation=the_installation,
                token=token,
            )

        assert exc.value.status_code == 404
        assert exc.value.detail == "No such completion: foo"

    else:
        found = await completions.get_chat_completion(
            request,
            COMPLETION_ID,
            the_installation=the_installation,
            token=token,
        )

        assert found is fc.return_value
        fc.assert_called_once_with(completion_configs[COMPLETION_ID])

    the_installation.get_completion_configs.assert_called_once_with(
        auth_fn.return_value,
    )
    auth_fn.assert_called_once_with(the_installation, token)
