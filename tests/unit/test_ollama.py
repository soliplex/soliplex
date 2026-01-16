import json
import urllib.error
from unittest import mock

from soliplex import ollama

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


# DEFAULT_OLLAMA_URL test


def test_default_ollama_url_value():
    assert ollama.DEFAULT_OLLAMA_URL == "http://localhost:11434"
