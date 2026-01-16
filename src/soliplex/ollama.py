"""
Pull Ollama models via HTTP API.
"""

import json
import urllib.error
import urllib.request

DEFAULT_OLLAMA_URL = "http://localhost:11434"


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
