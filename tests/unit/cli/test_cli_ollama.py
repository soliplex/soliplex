from __future__ import annotations

from unittest import mock

import pytest
import requests
import typer

from soliplex.cli import ollama as cli_ollama


@pytest.fixture
def ctx():
    return mock.create_autospec(typer.Context, obj={})


@pytest.mark.parametrize(
    "w_unknown_urls, exp_message",
    [
        # Single unknown URL.
        (
            ["http://nope.example.com"],
            "URL(s) not referenced by installation: http://nope.example.com",
        ),
        # Multiple unknown URLs are joined with ", ".
        (
            ["http://a.example.com", "http://b.example.com"],
            (
                "URL(s) not referenced by installation: "
                "http://a.example.com, http://b.example.com"
            ),
        ),
    ],
)
def test_UnknownOllamaURLs(w_unknown_urls, exp_message):
    exc = cli_ollama.UnknownOllamaURLs(w_unknown_urls)

    # 'unknown_urls' is normalized to a list (defensive copy).
    assert exc.unknown_urls == list(w_unknown_urls)
    assert exc.unknown_urls is not w_unknown_urls
    assert str(exc) == exp_message


def test_UnknownOllamaURLs_accepts_non_list_iterable():
    # Generator inputs are coerced to a list so the message can be built.
    exc = cli_ollama.UnknownOllamaURLs(
        iter(["http://a.example.com", "http://b.example.com"]),
    )

    assert exc.unknown_urls == [
        "http://a.example.com",
        "http://b.example.com",
    ]


@pytest.mark.parametrize(
    "w_result, exp_message",
    [
        # Empty result: the keys list is empty in the message tail.
        ({}, "No status returned in result: keys were "),
        # Single key.
        (
            {"error": "boom"},
            "No status returned in result: keys were error",
        ),
        # Multiple keys are joined in their dict order.
        (
            {"error": "boom", "code": 42},
            "No status returned in result: keys were error, code",
        ),
    ],
)
def test_NoStatusReturned(w_result, exp_message):
    exc = cli_ollama.NoStatusReturned(w_result)

    assert exc.result is w_result
    # The exception subclasses KeyError so callers can catch either type.
    assert isinstance(exc, KeyError)
    # The 'KeyError.__str__' wraps the message in single quotes; use 'args'
    # to read the raw text.
    (message,) = exc.args
    assert message == exp_message


def test__pull_one_model_returns_status_on_success():
    rest_api = mock.Mock()
    rest_api.pull_model.return_value = {"status": "success"}

    found = cli_ollama._pull_one_model(rest_api, "llama3")

    assert found == "success"
    rest_api.pull_model.assert_called_once_with("llama3", stream=False)


def test__pull_one_model_lets_RequestException_propagate():
    rest_api = mock.Mock()
    rest_api.pull_model.side_effect = requests.RequestException("boom")

    with pytest.raises(requests.RequestException):
        cli_ollama._pull_one_model(rest_api, "llama3")


def test__pull_one_model_raises_NoStatusReturned_on_missing_status():
    rest_api = mock.Mock()
    result = {"error": "boom"}
    rest_api.pull_model.return_value = result

    with pytest.raises(cli_ollama.NoStatusReturned) as excinfo:
        cli_ollama._pull_one_model(rest_api, "llama3")

    # The raw response is attached for diagnostics, and the chain is
    # suppressed ('raise ... from None').
    assert excinfo.value.result is result
    assert excinfo.value.__cause__ is None
    assert excinfo.value.__suppress_context__ is True


@pytest.mark.parametrize(
    "w_ollama_urls",
    [
        # Empty list short-circuits.
        [],
        # 'None' is a valid sentinel for "no filter".
        None,
    ],
)
def test__filter_ollama_url_models_returns_input_when_no_urls_supplied(
    w_ollama_urls,
):
    ollama_url_models = {
        "http://a.example.com": {"llama3"},
        "http://b.example.com": {"mistral"},
    }

    found = cli_ollama._filter_ollama_url_models(
        ollama_url_models,
        w_ollama_urls,
    )

    # No new dict is allocated when no filtering is needed.
    assert found is ollama_url_models


@pytest.mark.parametrize(
    "w_configured, w_filter, exp_filtered",
    [
        # Single URL match.
        (
            {
                "http://a.example.com": {"llama3"},
                "http://b.example.com": {"mistral"},
            },
            ["http://a.example.com"],
            {"http://a.example.com": {"llama3"}},
        ),
        # Multiple URL matches preserve caller-supplied order.
        (
            {
                "http://a.example.com": {"llama3"},
                "http://b.example.com": {"mistral"},
                "http://c.example.com": {"phi3"},
            },
            ["http://c.example.com", "http://a.example.com"],
            {
                "http://c.example.com": {"phi3"},
                "http://a.example.com": {"llama3"},
            },
        ),
    ],
)
def test__filter_ollama_url_models_restricts_to_known_urls(
    w_configured,
    w_filter,
    exp_filtered,
):
    found = cli_ollama._filter_ollama_url_models(w_configured, w_filter)

    assert found == exp_filtered
    # Iteration order is preserved (matters for downstream per-URL output).
    assert list(found) == list(exp_filtered)


@pytest.mark.parametrize(
    "w_configured, w_filter, exp_unknown",
    [
        # No configured URLs; anything is unknown.
        ({}, ["http://nope.example.com"], ["http://nope.example.com"]),
        # All requested URLs are unknown.
        (
            {"http://a.example.com": {"llama3"}},
            ["http://x.example.com", "http://y.example.com"],
            ["http://x.example.com", "http://y.example.com"],
        ),
        # Mixed: only the unknown URL is reported.
        (
            {"http://a.example.com": {"llama3"}},
            ["http://a.example.com", "http://x.example.com"],
            ["http://x.example.com"],
        ),
    ],
)
def test__filter_ollama_url_models_raises_UnknownOllamaURLs(
    w_configured,
    w_filter,
    exp_unknown,
):
    with pytest.raises(cli_ollama.UnknownOllamaURLs) as excinfo:
        cli_ollama._filter_ollama_url_models(w_configured, w_filter)

    assert excinfo.value.unknown_urls == exp_unknown


# pull_models: command, ui only
