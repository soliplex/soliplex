import asyncio
import contextlib
import datetime
import functools
import json
import logging
import pathlib
import re
import subprocess
import typing

import logfire
from starlette import datastructures

FOUR_OR_MORE_PERIODS = re.compile(r"\.{4,}")
TWO_OR_MORE_ELLIPSES = re.compile(r"…{2,}")

# import to log
logger = logging.getLogger("uvicorn.error")


def scrub_private_keys(
    json_dict: dict[str, typing.Any],
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
                    value = [scrub_private_keys(item) for item in value]
            scrubbed[key] = value
    return scrubbed


class GitMetadata:
    """Capture Git hash / branch / tag information for the repo


    To override these values (e.g., when running in a container without
    a git clone), put the relevant values in these files inside the directory
    referenced by 'file_path':

    - 'git-hash.txt'
    - 'git-branch.txt'
    - 'git-tag.txt'
    """

    _git_hash = None
    _git_branch = None
    _git_tag = None

    def __init__(self, file_path: str | pathlib.Path):
        self.file_path = pathlib.Path(file_path)
        self.repo_dir = (
            self.file_path.parent
            if self.file_path.is_file()
            else self.file_path
        )

        hash_path = self.repo_dir / "git-hash.txt"

        if hash_path.is_file():
            self._git_hash = hash_path.read_text().strip()

        branch_path = self.repo_dir / "git-branch.txt"

        if branch_path.is_file():
            self._git_branch = branch_path.read_text().strip()

        tag_path = self.repo_dir / "git-tag.txt"

        if tag_path.is_file():
            self._git_tag = tag_path.read_text().strip()

    @property
    def git_hash(self) -> str:
        if self._git_hash is None:
            repo_dir = str(self.repo_dir)
            try:
                self._git_hash = (
                    subprocess.check_output(
                        ["git", "-C", repo_dir, "rev-parse", "HEAD"],
                        stderr=subprocess.DEVNULL,
                    )
                    .decode("utf-8")
                    .strip()
                )
            except subprocess.CalledProcessError:
                self._git_hash = "unknown"

        return self._git_hash

    @property
    def git_branch(self) -> str:
        if self._git_branch is None:
            repo_dir = str(self.repo_dir)
            try:
                branches_lines = subprocess.check_output(
                    [
                        "git",
                        "-C",
                        repo_dir,
                        "branch",
                        "--list",
                    ],
                    stderr=subprocess.DEVNULL,
                ).decode("ascii")

                for branch_line in branches_lines.splitlines():
                    flag = branch_line[0]
                    branch_name = branch_line[2:]

                    if flag == "*":
                        self._git_branch = branch_name
                        break
            except subprocess.CalledProcessError:
                self._git_branch = "unknown"

        return self._git_branch

    @property
    def git_tag(self) -> str:
        if self._git_tag is None:
            repo_dir = str(self.repo_dir)
            try:
                tags_lines = subprocess.check_output(
                    [
                        "git",
                        "-C",
                        repo_dir,
                        "tag",
                        "--list",
                        "--sort=creatordate",
                        "--format=%(objectname) %(refname:strip=2)",
                    ],
                    stderr=subprocess.DEVNULL,
                ).decode("ascii")

                for tag_line in tags_lines.splitlines():
                    tag_line = tag_line.strip()
                    if tag_line:
                        long_hash, tag_name = tag_line.split(" ", 1)
                        if long_hash == self.git_hash:
                            self._git_tag = tag_name
                            break
            except subprocess.CalledProcessError:
                self._git_tag = "unknown"

        return self._git_tag


def strip_default_port(url: datastructures.URL) -> datastructures.URL:
    """
    Returns a new URL instance with the default port removed
    for http (80) and https (443).
    """
    if (url.scheme == "http" and url.port == 80) or (
        url.scheme == "https" and url.port == 443
    ):
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
                if start_span is None:  # true in tests
                    start_span = noop
                with start_span(span_name):
                    return await func(*args, **kwargs)

            return async_wrapper
        else:

            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                start_span = getattr(logfire, "start_span", None)
                if start_span is None:  # true in tests
                    start_span = noop  # pragma: no cover
                with start_span(span_name):
                    return func(*args, **kwargs)

            return sync_wrapper

    return decorator


def preprocess_markdown(text: str) -> str:
    """Remove repeated punctuation from markdown

    Avoids overflowing embedding context.
    """
    parsed = FOUR_OR_MORE_PERIODS.sub("...", text)
    parsed = TWO_OR_MORE_ELLIPSES.sub("…", parsed)
    return parsed


class SQLA_JSONSerializationError(TypeError):
    def __init__(self, obj):
        self.obj = obj
        super().__init__(f"Cannot serialize {obj} to JSON")


def sqla_json_defaults(obj):
    """Serialize known types to JSON-compatible form"""
    if isinstance(obj, datetime.datetime | datetime.date | datetime.time):
        return obj.isoformat()

    raise SQLA_JSONSerializationError(obj)


def serialize_sqla_json(sqla_json_data):
    return json.dumps(sqla_json_data, default=sqla_json_defaults)
