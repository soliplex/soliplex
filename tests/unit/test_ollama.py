import json
import urllib.error
from unittest import mock

import pytest

from soliplex import ollama

# find_yaml_files tests

def test_find_yaml_files_recursively(temp_dir):
    # Create nested structure with yaml and yml files
    (temp_dir / "config.yaml").touch()
    (temp_dir / "settings.yml").touch()
    subdir = temp_dir / "subdir"
    subdir.mkdir()
    (subdir / "nested.yaml").touch()
    (subdir / "other.txt").touch()

    found = ollama.find_yaml_files(temp_dir)

    assert len(found) == 3
    found_names = {f.name for f in found}
    assert found_names == {"config.yaml", "settings.yml", "nested.yaml"}


def test_find_yaml_files_returns_empty_list_for_empty_dir(temp_dir):
    found = ollama.find_yaml_files(temp_dir)

    assert found == []


# _extract_models_from_agent_configs tests

@pytest.mark.parametrize(
    "data, expected",
    [
        # Empty data
        ({}, set()),
        # No agent_configs
        ({"other_key": "value"}, set()),
        # Empty agent_configs
        ({"agent_configs": []}, set()),
        # agent_configs is None
        ({"agent_configs": None}, set()),
        # Non-dict agent entry
        ({"agent_configs": ["not_a_dict"]}, set()),
        # Ollama provider with model_name
        (
            {
                "agent_configs": [
                    {"provider_type": "ollama", "model_name": "llama3"}
                ]
            },
            {"llama3"},
        ),
        # Default provider_type (ollama) with model_name
        (
            {"agent_configs": [{"model_name": "mistral"}]},
            {"mistral"},
        ),
        # OLLAMA (uppercase) provider_type
        (
            {
                "agent_configs": [
                    {"provider_type": "OLLAMA", "model_name": "gemma"}
                ]
            },
            {"gemma"},
        ),
        # Non-ollama provider skipped
        (
            {
                "agent_configs": [
                    {"provider_type": "openai", "model_name": "gpt-4"}
                ]
            },
            set(),
        ),
        # No model_name
        (
            {"agent_configs": [{"provider_type": "ollama"}]},
            set(),
        ),
        # Multiple agents, mixed providers
        (
            {
                "agent_configs": [
                    {"provider_type": "ollama", "model_name": "llama3"},
                    {"provider_type": "openai", "model_name": "gpt-4"},
                    {"model_name": "codellama"},
                ]
            },
            {"llama3", "codellama"},
        ),
    ],
)
def test_extract_models_from_agent_configs(data, expected):
    found = ollama._extract_models_from_agent_configs(data)

    assert found == expected


# _extract_models_from_environment tests

@pytest.mark.parametrize(
    "data, expected",
    [
        # Empty data
        ({}, set()),
        # No environment
        ({"other_key": "value"}, set()),
        # Empty environment
        ({"environment": []}, set()),
        # environment is None
        ({"environment": None}, set()),
        # Non-dict env item
        ({"environment": ["not_a_dict"]}, set()),
        # DEFAULT_AGENT_MODEL
        (
            {
                "environment": [
                    {"name": "DEFAULT_AGENT_MODEL", "value": "llama3"}
                ]
            },
            {"llama3"},
        ),
        # EMBEDDINGS_MODEL
        (
            {
                "environment": [
                    {"name": "EMBEDDINGS_MODEL", "value": "nomic-embed"}
                ]
            },
            {"nomic-embed"},
        ),
        # QA_MODEL
        (
            {"environment": [{"name": "QA_MODEL", "value": "mistral"}]},
            {"mistral"},
        ),
        # Unrecognized env var
        (
            {"environment": [{"name": "OTHER_MODEL", "value": "ignored"}]},
            set(),
        ),
        # No value
        (
            {"environment": [{"name": "DEFAULT_AGENT_MODEL", "value": None}]},
            set(),
        ),
        # Empty value
        (
            {"environment": [{"name": "DEFAULT_AGENT_MODEL", "value": ""}]},
            set(),
        ),
        # Multiple env vars
        (
            {
                "environment": [
                    {"name": "DEFAULT_AGENT_MODEL", "value": "llama3"},
                    {"name": "EMBEDDINGS_MODEL", "value": "nomic-embed"},
                    {"name": "OTHER_VAR", "value": "ignored"},
                ]
            },
            {"llama3", "nomic-embed"},
        ),
    ],
)
def test_extract_models_from_environment(data, expected):
    found = ollama._extract_models_from_environment(data)

    assert found == expected


# _extract_models_from_haiku_rag tests

@pytest.mark.parametrize(
    "data, expected",
    [
        # Empty data
        ({}, set()),
        # No haiku-rag sections
        ({"other_key": "value"}, set()),
        # embeddings section with ollama provider
        (
            {
                "embeddings": {
                    "model": {"provider": "ollama", "name": "nomic-embed"}
                }
            },
            {"nomic-embed"},
        ),
        # qa section with ollama provider
        (
            {"qa": {"model": {"provider": "ollama", "name": "llama3"}}},
            {"llama3"},
        ),
        # research section with ollama provider
        (
            {"research": {"model": {"provider": "ollama", "name": "mistral"}}},
            {"mistral"},
        ),
        # reranking section with ollama provider
        (
            {
                "reranking": {
                    "model": {"provider": "ollama", "name": "bge-reranker"}
                }
            },
            {"bge-reranker"},
        ),
        # Non-ollama provider
        (
            {
                "embeddings": {
                    "model": {"provider": "openai", "name": "ada-002"}
                }
            },
            set(),
        ),
        # Empty provider
        (
            {"embeddings": {"model": {"provider": "", "name": "model"}}},
            set(),
        ),
        # No name
        (
            {"embeddings": {"model": {"provider": "ollama"}}},
            set(),
        ),
        # Section data is not dict
        (
            {"embeddings": "not_a_dict"},
            set(),
        ),
        # Model is not dict
        (
            {"embeddings": {"model": "not_a_dict"}},
            set(),
        ),
        # Multiple sections
        (
            {
                "embeddings": {
                    "model": {"provider": "ollama", "name": "nomic"}
                },
                "qa": {
                    "model": {"provider": "ollama", "name": "llama3"}
                },
                "research": {
                    "model": {"provider": "openai", "name": "gpt-4"}
                },
            },
            {"nomic", "llama3"},
        ),
    ],
)
def test_extract_models_from_haiku_rag(data, expected):
    found = ollama._extract_models_from_haiku_rag(data)

    assert found == expected


# _extract_models_from_room_or_completion tests

@pytest.mark.parametrize(
    "data, expected",
    [
        # Empty data
        ({}, set()),
        # agent section with model_name
        (
            {"agent": {"model_name": "llama3"}},
            {"llama3"},
        ),
        # agent without model_name
        (
            {"agent": {"other_key": "value"}},
            set(),
        ),
        # agent is not dict
        (
            {"agent": "not_a_dict"},
            set(),
        ),
        # quizzes with judge_agent
        (
            {
                "quizzes": [
                    {"judge_agent": {"model_name": "mistral"}}
                ]
            },
            {"mistral"},
        ),
        # quizzes with non-dict entry
        (
            {"quizzes": ["not_a_dict"]},
            set(),
        ),
        # quizzes with non-dict judge_agent
        (
            {"quizzes": [{"judge_agent": "not_a_dict"}]},
            set(),
        ),
        # quizzes without model_name in judge_agent
        (
            {"quizzes": [{"judge_agent": {"other_key": "value"}}]},
            set(),
        ),
        # Empty quizzes
        (
            {"quizzes": []},
            set(),
        ),
        # quizzes is None (falsy)
        (
            {"quizzes": None},
            set(),
        ),
        # Both agent and quizzes
        (
            {
                "agent": {"model_name": "llama3"},
                "quizzes": [
                    {"judge_agent": {"model_name": "mistral"}},
                    {"judge_agent": {"model_name": "codellama"}},
                ],
            },
            {"llama3", "mistral", "codellama"},
        ),
    ],
)
def test_extract_models_from_room_or_completion(data, expected):
    found = ollama._extract_models_from_room_or_completion(data)

    assert found == expected


# extract_models_from_yaml tests

def test_extract_models_from_yaml_extracts_from_valid_yaml(temp_dir):
    yaml_file = temp_dir / "config.yaml"
    yaml_file.write_text(
        """
agent_configs:
  - provider_type: ollama
    model_name: llama3
environment:
  - name: EMBEDDINGS_MODEL
    value: nomic-embed
"""
    )

    found = ollama.extract_models_from_yaml(yaml_file)

    assert found == {"llama3", "nomic-embed"}


def test_extract_models_from_yaml_returns_empty_on_file_read_error(temp_dir):
    nonexistent_file = temp_dir / "nonesuch.yaml"

    found = ollama.extract_models_from_yaml(nonexistent_file)

    assert found == set()


def test_extract_models_from_yaml_returns_empty_on_invalid_yaml(temp_dir):
    yaml_file = temp_dir / "invalid.yaml"
    yaml_file.write_text("{{{{invalid yaml")

    found = ollama.extract_models_from_yaml(yaml_file)

    assert found == set()


def test_extract_models_from_yaml_returns_empty_when_data_not_dict(temp_dir):
    yaml_file = temp_dir / "list.yaml"
    yaml_file.write_text("- item1\n- item2")

    found = ollama.extract_models_from_yaml(yaml_file)

    assert found == set()


def test_extract_models_from_yaml_combines_all_extraction_methods(temp_dir):
    yaml_file = temp_dir / "complete.yaml"
    yaml_file.write_text(
        """
agent_configs:
  - model_name: model1
environment:
  - name: QA_MODEL
    value: model2
embeddings:
  model:
    provider: ollama
    name: model3
agent:
  model_name: model4
"""
    )

    found = ollama.extract_models_from_yaml(yaml_file)

    assert found == {"model1", "model2", "model3", "model4"}


# collect_models tests

def test_collect_models_returns_empty_for_nonexistent_directory(temp_dir):
    nonexistent = temp_dir / "nonesuch"

    found = ollama.collect_models(nonexistent)

    assert found == set()


def test_collect_models_collects_from_all_yaml_files(temp_dir):
    (temp_dir / "config1.yaml").write_text(
        "agent_configs:\n  - model_name: llama3"
    )
    (temp_dir / "config2.yml").write_text(
        "environment:\n  - name: QA_MODEL\n    value: mistral"
    )

    found = ollama.collect_models(temp_dir)

    assert found == {"llama3", "mistral"}


def test_collect_models_calls_on_found_callback(temp_dir):
    (temp_dir / "config.yaml").write_text(
        "agent_configs:\n  - model_name: llama3"
    )
    callback_calls = []

    def on_found(file_path, models):
        callback_calls.append((file_path, models))

    found = ollama.collect_models(temp_dir, on_found=on_found)

    assert found == {"llama3"}
    assert len(callback_calls) == 1
    assert callback_calls[0][0].name == "config.yaml"
    assert callback_calls[0][1] == {"llama3"}


def test_collect_models_skips_callback_for_files_without_models(temp_dir):
    (temp_dir / "empty.yaml").write_text("other_key: value")
    callback_calls = []

    def on_found(file_path, models):
        callback_calls.append((file_path, models))

    found = ollama.collect_models(temp_dir, on_found=on_found)

    assert found == set()
    assert len(callback_calls) == 0


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
