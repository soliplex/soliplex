from unittest import mock

import httpx
import pytest

from soliplex import context_window
from soliplex import loggers

BASE_URL = "http://vllm.example.com:8000/v1"
MODEL_NAME = "Qwen/Qwen2.5-0.5B-Instruct"


@pytest.fixture(autouse=True)
def clear_cache():
    context_window._MAX_MODEL_LEN.clear()
    yield
    context_window._MAX_MODEL_LEN.clear()


@pytest.fixture
def the_logger():
    return mock.create_autospec(loggers.LogWrapper)


def _card(model_id=MODEL_NAME, **kw):
    return {"id": model_id, "object": "model", **kw}


def _client_returning(payload=None, exc=None, status_code=200):
    """Patch 'httpx.AsyncClient' with one whose GET is scripted."""
    response = mock.Mock(spec_set=["json", "raise_for_status"])

    if payload is _NOT_JSON:
        response.json = mock.Mock(side_effect=ValueError("not JSON"))
    else:
        response.json = mock.Mock(return_value=payload)

    response.raise_for_status = mock.Mock()

    client = mock.AsyncMock()
    client.__aenter__.return_value = client

    if exc is not None:
        client.get = mock.AsyncMock(side_effect=exc)
    else:
        client.get = mock.AsyncMock(return_value=response)

    return mock.patch.object(
        context_window.httpx,
        "AsyncClient",
        return_value=client,
    ), client


_NOT_JSON = object()


@pytest.mark.parametrize(
    "payload, expected",
    [
        pytest.param(
            {"data": [_card(max_model_len=8192)]},
            8192,
            id="named-card",
        ),
        pytest.param(
            {
                "data": [
                    _card("other", max_model_len=111),
                    _card(max_model_len=8192),
                ],
            },
            8192,
            id="picks-the-named-one",
        ),
        pytest.param(
            {"data": [_card("served-under-another-name", max_model_len=4096)]},
            4096,
            id="sole-card-fallback",
        ),
        pytest.param({"data": [_card()]}, None, id="card-without-window"),
        pytest.param(
            {"data": [_card("a"), _card("b")]},
            None,
            id="absent-and-not-alone",
        ),
        pytest.param({"data": []}, None, id="empty-listing"),
        pytest.param({}, None, id="no-data-key"),
        pytest.param([], None, id="payload-not-a-mapping"),
        pytest.param(
            {"data": ["not-a-card"]},
            None,
            id="card-not-a-mapping",
        ),
        pytest.param(
            {"data": ["not-a-card", _card(max_model_len=2048)]},
            2048,
            id="skips-non-mapping-cards",
        ),
    ],
)
@pytest.mark.anyio
async def test_get_max_model_len_reads_the_listing(
    payload, expected, the_logger
):
    patcher, _client = _client_returning(payload)

    with patcher:
        found = await context_window.get_max_model_len(
            base_url=BASE_URL,
            model_name=MODEL_NAME,
            the_logger=the_logger,
        )

    assert found == expected
    the_logger.warning.assert_not_called()


@pytest.mark.anyio
async def test_get_max_model_len_sends_the_api_key(the_logger):
    patcher, client = _client_returning({"data": [_card(max_model_len=16)]})

    with patcher:
        await context_window.get_max_model_len(
            base_url=BASE_URL,
            model_name=MODEL_NAME,
            api_key="sekrit",
            the_logger=the_logger,
        )

    client.get.assert_awaited_once_with(
        f"{BASE_URL}/models",
        headers={"Authorization": "Bearer sekrit"},
    )


@pytest.mark.anyio
async def test_get_max_model_len_omits_absent_api_key(the_logger):
    patcher, client = _client_returning({"data": [_card(max_model_len=16)]})

    with patcher:
        await context_window.get_max_model_len(
            base_url=BASE_URL,
            model_name=MODEL_NAME,
            the_logger=the_logger,
        )

    client.get.assert_awaited_once_with(f"{BASE_URL}/models", headers={})


@pytest.mark.anyio
async def test_get_max_model_len_unreachable_provider(the_logger):
    """An unreachable provider is a passing condition, so it is not cached."""
    patcher, _client = _client_returning(
        exc=httpx.ConnectError("nope"),
    )

    with patcher:
        found = await context_window.get_max_model_len(
            base_url=BASE_URL,
            model_name=MODEL_NAME,
            the_logger=the_logger,
        )

    assert found is None
    assert (BASE_URL, MODEL_NAME) not in context_window._MAX_MODEL_LEN
    # The host is in the message, not only in the structured fields:
    # the console handler renders one and not the other.
    message, *positional = the_logger.warning.call_args.args
    assert message == loggers.CONTEXT_WINDOW_UNAVAILABLE
    assert positional[0] == BASE_URL
    assert the_logger.warning.call_args.kwargs == {
        "base_url": BASE_URL,
        "model_name": MODEL_NAME,
        "reason": "nope",
    }
    assert BASE_URL in message % tuple(positional)


@pytest.mark.anyio
async def test_get_max_model_len_unreadable_body(the_logger):
    """A decode failure's exception quotes the body, so only its kind logs."""
    patcher, _client = _client_returning(_NOT_JSON)

    with patcher:
        found = await context_window.get_max_model_len(
            base_url=BASE_URL,
            model_name=MODEL_NAME,
            the_logger=the_logger,
        )

    assert found is None
    assert (BASE_URL, MODEL_NAME) not in context_window._MAX_MODEL_LEN
    message, *positional = the_logger.warning.call_args.args
    assert message == loggers.CONTEXT_WINDOW_UNREADABLE
    assert BASE_URL in message % tuple(positional)


@pytest.mark.anyio
async def test_get_max_model_len_answers_from_cache(the_logger):
    """A window that exists does not change under a running deployment."""
    context_window._MAX_MODEL_LEN[(BASE_URL, MODEL_NAME)] = 8192
    patcher, client = _client_returning({"data": [_card(max_model_len=1)]})

    with patcher:
        found = await context_window.get_max_model_len(
            base_url=BASE_URL,
            model_name=MODEL_NAME,
            the_logger=the_logger,
        )

    assert found == 8192
    client.get.assert_not_awaited()


@pytest.mark.anyio
async def test_get_max_model_len_retries_after_an_absent_window(the_logger):
    """An absent window is not an answer, so it is asked for again.

    A provider can be reachable but not yet serving the model -- Ollama
    reports no size for one it has evicted. Remembering that absence
    would hide the gauge for the life of the process even once the
    provider began answering.
    """
    patcher, _client = _client_returning({"data": [_card()]})

    with patcher:
        assert (
            await context_window.get_max_model_len(
                base_url=BASE_URL,
                model_name=MODEL_NAME,
                the_logger=the_logger,
            )
            is None
        )

    assert (BASE_URL, MODEL_NAME) not in context_window._MAX_MODEL_LEN

    patcher, _client = _client_returning({"data": [_card(max_model_len=4096)]})

    with patcher:
        assert (
            await context_window.get_max_model_len(
                base_url=BASE_URL,
                model_name=MODEL_NAME,
                the_logger=the_logger,
            )
            == 4096
        )
