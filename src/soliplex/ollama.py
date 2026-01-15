"""
Collect and pull Ollama models referenced in soliplex configuration files.
"""

import json
import urllib.error
import urllib.request

import yaml

DEFAULT_OLLAMA_URL = "http://localhost:11434"


def find_yaml_files(directory):
    """Find all YAML files in a directory recursively."""
    yaml_files = []
    for pattern in ("**/*.yaml", "**/*.yml"):
        yaml_files.extend(directory.glob(pattern))
    return yaml_files


def _extract_models_from_agent_configs(data):
    """Extract model names from agent_configs section."""
    models = set()
    agent_configs = data.get("agent_configs", [])
    if not agent_configs:
        return models

    for agent in agent_configs:
        if not isinstance(agent, dict):
            continue
        provider_type = agent.get("provider_type", "ollama")
        if provider_type.lower() == "ollama":
            model_name = agent.get("model_name")
            if model_name:
                models.add(model_name)
    return models


def _extract_models_from_environment(data):
    """Extract model names from environment section."""
    models = set()
    environment = data.get("environment", [])
    if not environment:
        return models

    model_env_vars = {"DEFAULT_AGENT_MODEL", "EMBEDDINGS_MODEL", "QA_MODEL"}

    for env_item in environment:
        if isinstance(env_item, dict):
            name = env_item.get("name")
            value = env_item.get("value")
            if name in model_env_vars and value:
                models.add(value)
    return models


def _extract_models_from_haiku_rag(data):
    """Extract model names from haiku.rag configuration sections."""
    models = set()

    for section in ("embeddings", "qa", "research", "reranking"):
        section_data = data.get(section, {})
        if isinstance(section_data, dict):
            model = section_data.get("model", {})
            if isinstance(model, dict):
                provider = model.get("provider", "").lower()
                name = model.get("name")
                if provider == "ollama" and name:
                    models.add(name)

    return models


def _extract_models_from_room_or_completion(data):
    """Extract model names from room_config.yaml or completion_config.yaml."""
    models = set()

    agent = data.get("agent", {})
    if isinstance(agent, dict):
        model_name = agent.get("model_name")
        if model_name:
            models.add(model_name)

    quizzes = data.get("quizzes", [])
    if quizzes:
        for quiz in quizzes:
            if not isinstance(quiz, dict):
                continue
            judge_agent = quiz.get("judge_agent", {})
            if isinstance(judge_agent, dict):
                model_name = judge_agent.get("model_name")
                if model_name:
                    models.add(model_name)

    return models


def extract_models_from_yaml(file_path):
    """Extract all Ollama model names from a YAML configuration file."""
    models = set()

    try:
        with open(file_path) as f:
            data = yaml.safe_load(f)
    except Exception:
        return models

    if not isinstance(data, dict):
        return models

    models.update(_extract_models_from_agent_configs(data))
    models.update(_extract_models_from_environment(data))
    models.update(_extract_models_from_haiku_rag(data))
    models.update(_extract_models_from_room_or_completion(data))

    return models


def collect_models(directory, on_found=None):
    """
    Collect all Ollama model names from a configuration directory.

    Args:
        directory: Path to scan for YAML files
        on_found: Optional callback(file_path, models) called for each
            file with models

    Returns:
        Set of model names
    """
    all_models = set()

    if not directory.exists():
        return all_models

    yaml_files = find_yaml_files(directory)
    for yaml_file in yaml_files:
        models = extract_models_from_yaml(yaml_file)
        if models:
            if on_found:
                on_found(yaml_file, models)
            all_models.update(models)

    return all_models


def pull_model(model_name, ollama_url, on_status=None):
    """
    Pull an Ollama model via HTTP API.

    Args:
        model_name: Name of the model to pull
        ollama_url: Base URL of the Ollama API
        on_status: Optional callback(message, is_error) for status updates

    Returns:
        True on success, False on failure
    """
    def status(msg, is_error=False):
        if on_status:
            on_status(msg, is_error)

    url = f"{ollama_url.rstrip('/')}/api/pull"
    payload = json.dumps({"name": model_name, "stream": False}).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        status(f"POST {url}")
        with urllib.request.urlopen(req, timeout=600) as response:
            result = json.loads(response.read().decode("utf-8"))
            status_text = result.get("status", "unknown")
            status(f"Status: {status_text}")
            return True
    except urllib.error.HTTPError as e:
        status(f"HTTP Error {e.code}: {e.reason}", is_error=True)
        return False
    except urllib.error.URLError as e:
        status(f"Connection error: {e.reason}", is_error=True)
        return False
    except Exception as e:
        status(f"Error: {e}", is_error=True)
        return False
