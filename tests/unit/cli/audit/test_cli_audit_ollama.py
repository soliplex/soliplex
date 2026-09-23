from __future__ import annotations

from unittest import mock

import pytest
import requests

from soliplex import installation
from soliplex.cli.audit import ollama as audit_ollama

CHAT_ROLE = installation.ProviderRole.CHAT
EMBEDDING_ROLE = installation.ProviderRole.EMBEDDING
RERANKING_ROLE = installation.ProviderRole.RERANKING


@pytest.mark.parametrize(
    "w_provider_info, w_responses, exp_errors",
    [
        # No Ollama URLs configured -> no errors.
        ({}, {}, {}),
        # URL present but no models referenced -> skipped, no errors.
        (
            {"ollama": {"http://a.example.com": {}}},
            {},
            {},
        ),
        # All required models are available -> no errors.
        (
            {
                "ollama": {
                    "http://a.example.com": {
                        "llama3": CHAT_ROLE,
                        "mistral": CHAT_ROLE,
                    },
                },
            },
            {
                "http://a.example.com": {
                    "models": [{"name": "llama3"}, {"name": "mistral"}],
                },
            },
            {},
        ),
        # Some required models are missing -> sorted list reported.
        (
            {
                "ollama": {
                    "http://a.example.com": {
                        "llama3": CHAT_ROLE,
                        "mistral": CHAT_ROLE,
                        "phi3": CHAT_ROLE,
                    },
                },
            },
            {
                "http://a.example.com": {"models": [{"name": "llama3"}]},
            },
            {
                "ollama": {
                    "http://a.example.com": {
                        "missing_models": ["mistral", "phi3"],
                    },
                },
            },
        ),
        # Server returns an empty 'models' list -> everything is missing.
        (
            {
                "ollama": {
                    "http://a.example.com": {"llama3": CHAT_ROLE},
                },
            },
            {"http://a.example.com": {"models": []}},
            {
                "ollama": {
                    "http://a.example.com": {"missing_models": ["llama3"]},
                },
            },
        ),
        # Multiple URLs: a mix of OK and missing.
        (
            {
                "ollama": {
                    "http://a.example.com": {"llama3": CHAT_ROLE},
                    "http://b.example.com": {"mistral": CHAT_ROLE},
                },
            },
            {
                "http://a.example.com": {
                    "models": [{"name": "llama3"}],
                },
                "http://b.example.com": {"models": []},
            },
            {
                "ollama": {
                    "http://b.example.com": {"missing_models": ["mistral"]},
                },
            },
        ),
    ],
)
@mock.patch("soliplex.cli.audit.ollama.ollama.REST_API")
def test__missing_ollama_models_compares_available_to_required(
    rest_api_cls,
    the_installation,
    w_provider_info,
    w_responses,
    exp_errors,
):
    the_installation._all_provider_info = w_provider_info

    instances = {}
    for url, response in w_responses.items():
        instance = mock.Mock()
        instance.get_available_models.return_value = response
        instances[url] = instance

    rest_api_cls.side_effect = lambda url: instances[url]

    # Only URLs with a required-model set should trigger an
    # 'all_models' call.
    expected_calls = [
        mock.call(url)
        for url, models in w_provider_info.get("ollama", {}).items()
        if models
    ]

    found = audit_ollama._missing_ollama_models(the_installation)

    assert found == exp_errors
    assert rest_api_cls.call_args_list == expected_calls


@mock.patch("soliplex.cli.audit.ollama.ollama.REST_API")
def test__missing_ollama_models_reports_unreachable_server(
    rest_api_cls,
    the_installation,
):
    the_installation._all_provider_info = {
        "ollama": {
            "http://a.example.com": {"llama3": CHAT_ROLE},
        }
    }

    instance = mock.Mock()
    instance.get_available_models.side_effect = requests.ConnectionError(
        "refused",
    )
    rest_api_cls.return_value = instance

    found = audit_ollama._missing_ollama_models(the_installation)

    assert found == {
        "ollama": {
            "http://a.example.com": {"unreachable": "('refused',)"},
        },
    }


def test__unresponsive_ollama_models_all_respond():
    rest_api = mock.Mock()
    models = {"llama3": CHAT_ROLE, "mistral": CHAT_ROLE}

    found = audit_ollama._unresponsive_ollama_models(rest_api, models)

    assert found == {}
    assert rest_api.chat_completion.call_args_list == [
        mock.call("llama3"),
        mock.call("mistral"),
    ]


def test__unresponsive_ollama_models_records_failures():
    rest_api = mock.Mock()
    rest_api.chat_completion.side_effect = [
        None,
        requests.ConnectionError("boom"),
    ]
    models = {"llama3": CHAT_ROLE, "mistral": CHAT_ROLE}

    found = audit_ollama._unresponsive_ollama_models(rest_api, models)

    assert found == {"mistral": "('boom',)"}


def test__unresponsive_ollama_models_probes_embedding_model():
    # Regression, soliplex#1356: an embedding model answers 400 to a
    # chat completion, so probing it as a chat model reports a healthy
    # model as unresponsive.
    rest_api = mock.Mock()
    models = {"embed-me": EMBEDDING_ROLE}

    found = audit_ollama._unresponsive_ollama_models(rest_api, models)

    assert found == {}
    rest_api.embeddings.assert_called_once_with("embed-me")
    rest_api.chat_completion.assert_not_called()


def test__unresponsive_ollama_models_records_embedding_failure():
    rest_api = mock.Mock()
    rest_api.embeddings.side_effect = requests.ConnectionError("boom")
    models = {"embed-me": EMBEDDING_ROLE}

    found = audit_ollama._unresponsive_ollama_models(rest_api, models)

    assert found == {"embed-me": "('boom',)"}


def test__unresponsive_ollama_models_skips_rerank_model():
    # Ollama serves no rerank endpoint, so there is nothing to probe:
    # a rerank model must not be reported broken for failing one it
    # never claimed.
    rest_api = mock.Mock()
    models = {"rerank-me": RERANKING_ROLE}

    found = audit_ollama._unresponsive_ollama_models(rest_api, models)

    assert found == {}
    rest_api.chat_completion.assert_not_called()
    rest_api.embeddings.assert_not_called()


@mock.patch("soliplex.cli.audit.ollama.ollama.REST_API")
def test__missing_ollama_models_checks_responsiveness_when_requested(
    rest_api_cls,
    the_installation,
):
    the_installation._all_provider_info = {
        "ollama": {
            "http://a.example.com": {
                "llama3": CHAT_ROLE,
                "mistral": CHAT_ROLE,
                "phi3": CHAT_ROLE,
            },
        },
    }

    instance = mock.Mock()
    instance.get_available_models.return_value = {
        "models": [{"name": "llama3"}, {"name": "mistral"}],
    }

    # 'llama3' answers; 'mistral' fails. 'phi3' is missing, so never probed.
    def chat_completion(model_name):
        if model_name == "mistral":
            raise requests.ConnectionError("boom")

    instance.chat_completion.side_effect = chat_completion
    rest_api_cls.return_value = instance

    found = audit_ollama._missing_ollama_models(
        the_installation,
        check_responsive=True,
    )

    assert found == {
        "ollama": {
            "http://a.example.com": {
                "missing_models": ["phi3"],
                "unresponsive_models": {"mistral": "('boom',)"},
            },
        },
    }
    # Only installed-and-required models are probed for responsiveness.
    assert instance.chat_completion.call_args_list == [
        mock.call("llama3"),
        mock.call("mistral"),
    ]


@mock.patch("soliplex.cli.audit.ollama.ollama.REST_API")
def test__missing_ollama_models_responsive_all_ok(
    rest_api_cls,
    the_installation,
):
    the_installation._all_provider_info = {
        "ollama": {
            "http://a.example.com": {"llama3": CHAT_ROLE},
        },
    }

    instance = mock.Mock()
    instance.get_available_models.return_value = {
        "models": [{"name": "llama3"}],
    }
    rest_api_cls.return_value = instance

    found = audit_ollama._missing_ollama_models(
        the_installation,
        check_responsive=True,
    )

    assert found == {}
    instance.chat_completion.assert_called_once_with("llama3")


@mock.patch("soliplex.cli.audit.ollama.ollama.REST_API")
def test__missing_ollama_models_skips_responsiveness_by_default(
    rest_api_cls,
    the_installation,
):
    the_installation._all_provider_info = {
        "ollama": {
            "http://a.example.com": {"llama3": CHAT_ROLE},
        },
    }

    instance = mock.Mock()
    instance.get_available_models.return_value = {
        "models": [{"name": "llama3"}],
    }
    rest_api_cls.return_value = instance

    found = audit_ollama._missing_ollama_models(the_installation)

    assert found == {}
    instance.chat_completion.assert_not_called()


# _audit_ollama_section: ui only
# audit_ollama: command
