import asyncio
import contextlib
import functools
import logging
import os
import pathlib
import subprocess
import traceback
import typing

import logfire
from starlette import datastructures

# import to log
logger = logging.getLogger("uvicorn.error")


def scrub_private_keys(
    json_dict: dict[str, typing.Any]
) -> dict[str, typing.Any]:
    """Return a copy of 'json_dict' with private keys removed

    'json_dict'
        the dict to be copied
    """
    scrubbed = {}
    for key, value in json_dict.items():
        if not key.startswith("_"):
            if isinstance(value, dict):
                value = scrub_private_keys(value)
            if isinstance(value, list):
                if value and isinstance(value[0], dict):
                    value = [
                        scrub_private_keys(item) for item in value
                    ]
            scrubbed[key] = value
    return scrubbed


def interpolate_env_vars(source: str) -> str:
    """Interplate environment variables into a string

    'source'
        the string containing potential format replacements to be
        filled using environment variables
    """
    if not source.startswith("env:"):
        return source

    stripped = source[len("env:"):]

    return stripped.format(**os.environ)


def get_git_hash_for_file(file_path: str):
    file_path = pathlib.Path(file_path)
    repo_dir = file_path.parent
    hash_path = repo_dir / "git-hash.txt"

    if hash_path.is_file():
        return hash_path.read_text().strip()

    try:
        return subprocess.check_output(
            ['git', '-C', repo_dir, 'rev-parse', 'HEAD']
        ).decode('utf-8').strip()
    except Exception:
        traceback.print_exc()
        return 'unknown'


def strip_default_port(url: datastructures.URL) -> datastructures.URL:
    """
    Returns a new URL instance with the default port removed
    for http (80) and https (443).
    """
    if (url.scheme == "http" and url.port == 80) or (
            url.scheme == "https" and url.port == 443):
        # Build userinfo if present
        userinfo = ""
        if url.username:
            userinfo = url.username
            if url.password:
                userinfo += f":{url.password}"
            userinfo += "@"
        # Rebuild the URL without the port
        return datastructures.URL(
            f"{url.scheme}://"
            f"{userinfo}"
            f"{url.hostname}"
            f"{url.path or ''}"
            f"{f'?{url.query}' if url.query else ''}"
            f"{f'#{url.fragment}' if url.fragment else ''}"
        )
    return url


@contextlib.contextmanager
def noop(*arg, **kw):
    yield


def logfire_span(span_name):
    def decorator(func):
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                start_span = getattr(logfire, "start_span", None)
                if start_span is None: # true in tests
                    start_span = noop
                with start_span(span_name):
                    return await func(*args, **kwargs)
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                start_span = getattr(logfire, "start_span", None)
                if start_span is None: # true in tests
                    start_span = noop # pragma: no cover
                with start_span(span_name):
                    return func(*args, **kwargs)
            return sync_wrapper
    return decorator
