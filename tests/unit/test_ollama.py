import contextlib
import json
import urllib.error
from unittest import mock

import pytest
import requests

from soliplex import ollama

TEST_OLLAMA_URL = "https://ollama.example.com:11434"
TEST_MODEL_NAME = "test-model:7.8"
SOURCE_MODEL_NAME = "dest-model:7.8"
DEST_MODEL_NAME = "dest-model:7.8"
MODEL_TEMPLATE = "Test model template"
MODEL_LICENSE = "Test model license"
SYSTEM_PROMPT = "Test sytem prompt"
MODEL_PARAMETERS = {"test-param": 0.1234}
MODEL_MESSAGES = [{"role": "user", "message": "Why is the sky blue?"}]
MODEL_QUANTIZE = "q1_K"


@pytest.fixture
def rest_api():
    return ollama.REST_API(TEST_OLLAMA_URL)


@pytest.mark.parametrize(
    "status_code, expectation",
    [
        (None, contextlib.nullcontext()),
        (400, pytest.raises(requests.exceptions.HTTPError)),
    ],
)
@mock.patch("soliplex.ollama.requests.get")
def test_ollama_rest_api_get_version(
    r_get,
    rest_api,
    status_code,
    expectation,
):
    if status_code is not None:
        r_get.side_effect = requests.HTTPError(status_code)

    with expectation as expected:
        found = rest_api.get_version()

    if status_code is not None:
        assert expected.value.args == (status_code,)
    else:
        assert found is r_get.return_value.json.return_value

    r_get.assert_called_once_with(f"{TEST_OLLAMA_URL}/api/version")


@pytest.mark.parametrize(
    "status_code, expectation",
    [
        (None, contextlib.nullcontext()),
        (400, pytest.raises(requests.exceptions.HTTPError)),
    ],
)
@mock.patch("soliplex.ollama.requests.get")
def test_ollama_rest_api_get_available_models(
    r_get,
    rest_api,
    status_code,
    expectation,
):
    if status_code is not None:
        r_get.side_effect = requests.HTTPError(status_code)

    with expectation as expected:
        found = rest_api.get_available_models()

    if status_code is not None:
        assert expected.value.args == (status_code,)
    else:
        assert found is r_get.return_value.json.return_value

    r_get.assert_called_once_with(f"{TEST_OLLAMA_URL}/api/tags")


@pytest.mark.parametrize(
    "status_code, expectation",
    [
        (None, contextlib.nullcontext()),
        (400, pytest.raises(requests.exceptions.HTTPError)),
    ],
)
@mock.patch("soliplex.ollama.requests.get")
def test_ollama_rest_api_get_running_models(
    r_get,
    rest_api,
    status_code,
    expectation,
):
    if status_code is not None:
        r_get.side_effect = requests.HTTPError(status_code)

    with expectation as expected:
        found = rest_api.get_running_models()

    if status_code is not None:
        assert expected.value.args == (status_code,)
    else:
        assert found is r_get.return_value.json.return_value

    r_get.assert_called_once_with(f"{TEST_OLLAMA_URL}/api/ps")


@pytest.mark.parametrize("w_verbose", [None, False, True])
@pytest.mark.parametrize(
    "status_code, expectation",
    [
        (None, contextlib.nullcontext()),
        (400, pytest.raises(requests.exceptions.HTTPError)),
    ],
)
@mock.patch("soliplex.ollama.requests.post")
def test_ollama_rest_api_show_model(
    r_post, rest_api, status_code, expectation, w_verbose
):
    exp_data = {"model": TEST_MODEL_NAME}

    kwargs = {}

    if w_verbose is not None:
        kwargs["verbose"] = exp_data["verbose"] = w_verbose

    if status_code is not None:
        r_post.side_effect = requests.HTTPError(status_code)

    with expectation as expected:
        found = rest_api.show_model(TEST_MODEL_NAME, **kwargs)

    if status_code is not None:
        assert expected.value.args == (status_code,)
    else:
        assert found is r_post.return_value.json.return_value

    r_post.assert_called_once_with(
        f"{TEST_OLLAMA_URL}/api/show", json=exp_data
    )


@pytest.mark.parametrize("w_stream", [None, False, True])
@pytest.mark.parametrize(
    "w_kwargs",
    [
        {},
        {
            "template": MODEL_TEMPLATE,
            "license": MODEL_LICENSE,
            "system_prompt": SYSTEM_PROMPT,
            "parameters": MODEL_PARAMETERS,
            "messages": MODEL_MESSAGES,
            "quantize": MODEL_QUANTIZE,
        },
    ],
)
@pytest.mark.parametrize(
    "status_code, expectation",
    [
        (None, contextlib.nullcontext()),
        (400, pytest.raises(requests.exceptions.HTTPError)),
    ],
)
@mock.patch("soliplex.ollama.requests.post")
def test_ollama_rest_api_create_model(
    r_post,
    rest_api,
    status_code,
    expectation,
    w_kwargs,
    w_stream,
):
    exp_data = {
        "model": TEST_MODEL_NAME,
        "from": SOURCE_MODEL_NAME,
    } | w_kwargs

    if "system_prompt" in w_kwargs:
        exp_data["system"] = exp_data.pop("system_prompt")

    call_kwargs = {}

    if w_stream is not None:
        exp_data["stream"] = call_kwargs["stream"] = w_stream

    if status_code is not None:
        r_post.side_effect = requests.HTTPError(status_code)

    with expectation as expected:
        found = rest_api.create_model(
            model_name=TEST_MODEL_NAME,
            source_model_name=SOURCE_MODEL_NAME,
            **call_kwargs,
            **w_kwargs,
        )

    if status_code is not None:
        assert expected.value.args == (status_code,)
    else:
        assert found is r_post.return_value.json.return_value

    r_post.assert_called_once_with(
        f"{TEST_OLLAMA_URL}/api/create", json=exp_data
    )


@pytest.mark.parametrize(
    "status_code, expectation",
    [
        (None, contextlib.nullcontext()),
        (400, pytest.raises(requests.exceptions.HTTPError)),
    ],
)
@mock.patch("soliplex.ollama.requests.post")
def test_ollama_rest_api_copy_model(
    r_post,
    rest_api,
    status_code,
    expectation,
):
    exp_data = {"source": SOURCE_MODEL_NAME, "destination": DEST_MODEL_NAME}

    if status_code is not None:
        r_post.side_effect = requests.HTTPError(status_code)

    with expectation as expected:
        found = rest_api.copy_model(
            SOURCE_MODEL_NAME,
            DEST_MODEL_NAME,
        )

    if status_code is not None:
        assert expected.value.args == (status_code,)
    else:
        assert found is r_post.return_value.json.return_value

    r_post.assert_called_once_with(
        f"{TEST_OLLAMA_URL}/api/copy", json=exp_data
    )


@pytest.mark.parametrize(
    "status_code, expectation",
    [
        (None, contextlib.nullcontext()),
        (400, pytest.raises(requests.exceptions.HTTPError)),
    ],
)
@mock.patch("soliplex.ollama.requests.post")
def test_ollama_rest_api_push_model(
    r_post,
    rest_api,
    status_code,
    expectation,
):
    exp_data = {"model": TEST_MODEL_NAME}

    if status_code is not None:
        r_post.side_effect = requests.HTTPError(status_code)

    with expectation as expected:
        found = rest_api.push_model(TEST_MODEL_NAME)

    if status_code is not None:
        assert expected.value.args == (status_code,)
    else:
        assert found is r_post.return_value.json.return_value

    r_post.assert_called_once_with(
        f"{TEST_OLLAMA_URL}/api/push", json=exp_data
    )


@pytest.mark.parametrize("w_stream", [None, False, True])
@pytest.mark.parametrize(
    "status_code, expectation",
    [
        (None, contextlib.nullcontext()),
        (400, pytest.raises(requests.exceptions.HTTPError)),
    ],
)
@mock.patch("soliplex.ollama.requests.post")
def test_ollama_rest_api_pull_model(
    r_post,
    rest_api,
    status_code,
    expectation,
    w_stream,
):
    exp_data = {"model": TEST_MODEL_NAME}
    kwargs = {}

    if w_stream is not None:
        exp_data["stream"] = kwargs["stream"] = w_stream

    if status_code is not None:
        r_post.side_effect = requests.HTTPError(status_code)

    with expectation as expected:
        found = rest_api.pull_model(TEST_MODEL_NAME, **kwargs)

    if status_code is not None:
        assert expected.value.args == (status_code,)
    else:
        assert found is r_post.return_value.json.return_value

    r_post.assert_called_once_with(
        f"{TEST_OLLAMA_URL}/api/pull", json=exp_data
    )


@pytest.mark.parametrize(
    "status_code, expectation",
    [
        (None, contextlib.nullcontext()),
        (400, pytest.raises(requests.exceptions.HTTPError)),
    ],
)
@mock.patch("soliplex.ollama.requests.delete")
def test_ollama_rest_api_delete_model(
    r_delete,
    rest_api,
    status_code,
    expectation,
):
    exp_data = {"model": TEST_MODEL_NAME}

    if status_code is not None:
        r_delete.side_effect = requests.HTTPError(status_code)

    with expectation as expected:
        found = rest_api.delete_model(TEST_MODEL_NAME)

    if status_code is not None:
        assert expected.value.args == (status_code,)
    else:
        assert found is r_delete.return_value.json.return_value

    r_delete.assert_called_once_with(
        f"{TEST_OLLAMA_URL}/api/delete",
        json=exp_data,
    )


# pull_model tests


def test_pull_model_successful_pull():
    mock_response = mock.MagicMock()
    response_data = json.dumps({"status": "success"}).encode()
    mock_response.read.return_value = response_data
    mock_response.__enter__ = mock.MagicMock(return_value=mock_response)
    mock_response.__exit__ = mock.MagicMock(return_value=False)

    status_calls = []

    def on_status(msg, is_error=False):
        status_calls.append((msg, is_error))

    with mock.patch("urllib.request.urlopen", return_value=mock_response):
        result = ollama.pull_model(
            "llama3", "http://localhost:11434", on_status=on_status
        )

    assert result is True
    assert len(status_calls) == 2
    assert "POST" in status_calls[0][0]
    assert status_calls[0][1] is False
    assert "success" in status_calls[1][0]
    assert status_calls[1][1] is False


def test_pull_model_successful_pull_without_callback():
    mock_response = mock.MagicMock()
    response_data = json.dumps({"status": "success"}).encode()
    mock_response.read.return_value = response_data
    mock_response.__enter__ = mock.MagicMock(return_value=mock_response)
    mock_response.__exit__ = mock.MagicMock(return_value=False)

    with mock.patch("urllib.request.urlopen", return_value=mock_response):
        result = ollama.pull_model("llama3", "http://localhost:11434")

    assert result is True


def test_pull_model_strips_trailing_slash_from_url():
    mock_response = mock.MagicMock()
    mock_response.read.return_value = json.dumps({"status": "ok"}).encode()
    mock_response.__enter__ = mock.MagicMock(return_value=mock_response)
    mock_response.__exit__ = mock.MagicMock(return_value=False)

    with mock.patch("urllib.request.urlopen", return_value=mock_response):
        with mock.patch("urllib.request.Request") as req_mock:
            req_mock.return_value = mock.MagicMock()
            ollama.pull_model("llama3", "http://localhost:11434/")

            # Verify URL doesn't have double slash
            call_args = req_mock.call_args
            assert call_args[0][0] == "http://localhost:11434/api/pull"


def test_pull_model_http_error():
    status_calls = []

    def on_status(msg, is_error=False):
        status_calls.append((msg, is_error))

    http_error = urllib.error.HTTPError(
        "http://localhost:11434/api/pull", 404, "Not Found", {}, None
    )

    with mock.patch("urllib.request.urlopen", side_effect=http_error):
        result = ollama.pull_model(
            "llama3", "http://localhost:11434", on_status=on_status
        )

    assert result is False
    assert any("HTTP Error 404" in call[0] for call in status_calls)
    assert any(call[1] is True for call in status_calls)


def test_pull_model_url_error():
    status_calls = []

    def on_status(msg, is_error=False):
        status_calls.append((msg, is_error))

    url_error = urllib.error.URLError("Connection refused")

    with mock.patch("urllib.request.urlopen", side_effect=url_error):
        result = ollama.pull_model(
            "llama3", "http://localhost:11434", on_status=on_status
        )

    assert result is False
    assert any("Connection error" in call[0] for call in status_calls)
    assert any(call[1] is True for call in status_calls)


def test_pull_model_generic_exception():
    status_calls = []

    def on_status(msg, is_error=False):
        status_calls.append((msg, is_error))

    with mock.patch(
        "urllib.request.urlopen", side_effect=Exception("Unexpected error")
    ):
        result = ollama.pull_model(
            "llama3", "http://localhost:11434", on_status=on_status
        )

    assert result is False
    assert any("Error:" in call[0] for call in status_calls)
    assert any(call[1] is True for call in status_calls)


def test_pull_model_response_without_status_field():
    mock_response = mock.MagicMock()
    mock_response.read.return_value = json.dumps({}).encode()
    mock_response.__enter__ = mock.MagicMock(return_value=mock_response)
    mock_response.__exit__ = mock.MagicMock(return_value=False)

    status_calls = []

    def on_status(msg, is_error=False):
        status_calls.append((msg, is_error))

    with mock.patch("urllib.request.urlopen", return_value=mock_response):
        result = ollama.pull_model(
            "llama3", "http://localhost:11434", on_status=on_status
        )

    assert result is True
    assert any("unknown" in call[0] for call in status_calls)
