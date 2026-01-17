"""
Pull Ollama models via HTTP API.
"""

import dataclasses
import json
import typing
import urllib.error
import urllib.request

import requests

DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"


@dataclasses.dataclass
class REST_API:
    ollama_base_url: str = DEFAULT_OLLAMA_BASE_URL

    def _api_url(self, endpoint_name) -> str:
        return f"{self.ollama_base_url}/api/{endpoint_name}"

    def _get_endpoint(self, endpoint_name):
        url = self._api_url(endpoint_name)

        response = requests.get(url)
        response.raise_for_status()

        return response.json()

    def _post_endpoint(self, endpoint_name, data):
        url = self._api_url(endpoint_name)

        response = requests.post(url, json=data)
        response.raise_for_status()

        return response.json()

    def _delete_endpoint(self, endpoint_name, data):
        url = self._api_url(endpoint_name)

        response = requests.delete(url, json=data)
        response.raise_for_status()

        return response.json()

    def get_version(self):
        """Return the version of the Ollama server"""
        return self._get_endpoint("version")

    def get_available_models(self):
        """Return metadata about models available on the Ollama server"""
        return self._get_endpoint("tags")

    def get_running_models(self):
        """Return metadata about models running on the Ollama server"""
        return self._get_endpoint("ps")

    def show_model(self, model_name: str, verbose: bool = None):
        """Return metadata about an individual model on the Ollama server"""
        data = {"model": model_name}

        if verbose is not None:
            data["verbose"] = verbose

        return self._post_endpoint("show", data)

    def create_model(
        self,
        *,
        model_name: str,
        source_model_name: str,
        stream: bool = None,
        template: str = None,
        license: str | list[str] = None,
        system_prompt: str = None,
        parameters: typing.Sequence[dict[str, typing.Any]] = None,
        messages: str = None,
        quantize: str = None,
    ):
        """Copy a model to a new name / tag on the Ollama server"""
        data = {
            "model": model_name,
            "from": source_model_name,
        }
        if stream is not None:
            data["stream"] = stream

        if template is not None:
            data["template"] = template

        if license is not None:
            data["license"] = license

        if system_prompt is not None:
            data["system"] = system_prompt

        if parameters is not None:
            data["parameters"] = parameters

        if messages is not None:
            data["messages"] = messages

        if quantize is not None:
            data["quantize"] = quantize

        return self._post_endpoint("create", data)

    def copy_model(self, source_model_name: str, dest_model_name: str):
        """Copy a model to a new name / tag on the Ollama server"""
        data = {"source": source_model_name, "destination": dest_model_name}

        return self._post_endpoint("copy", data)

    def push_model(self, model_name: str):
        """Publish a model on the Ollama server"""
        data = {"model": model_name}

        return self._post_endpoint("push", data)

    def pull_model(self, model_name: str, stream=None):
        """Download a published model on the Ollama server"""
        data = {"model": model_name}

        if stream is not None:
            data["stream"] = stream

        return self._post_endpoint("pull", data)

    def delete_model(self, model_name: str):
        """Delte a published model on the Ollama server"""
        data = {"model": model_name}

        return self._delete_endpoint("delete", data)


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
