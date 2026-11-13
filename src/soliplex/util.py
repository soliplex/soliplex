import asyncio
import contextlib
import dataclasses
import datetime
import errno
import functools
import json
import logging
import os
import pathlib
import re
import stat
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
            self._git_hash = hash_path.read_text(encoding="utf-8").strip()

        branch_path = self.repo_dir / "git-branch.txt"

        if branch_path.is_file():
            self._git_branch = branch_path.read_text(encoding="utf-8").strip()

        tag_path = self.repo_dir / "git-tag.txt"

        if tag_path.is_file():
            self._git_tag = tag_path.read_text(encoding="utf-8").strip()

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


UNIX_EPOCH = datetime.datetime(1970, 1, 1, tzinfo=datetime.UTC)


def modified_at(stat_result: os.stat_result) -> datetime.datetime | None:
    """Return the modification time in 'stat_result', in UTC.

    'None' when a 'datetime' cannot hold it (outside years 1 to 9999):
    whoever writes the file can set any time, and a filesystem may store
    it as set.  Adding to the epoch, unlike 'fromtimestamp', fails only
    with 'OverflowError', and the same way on every platform.
    """
    try:
        return UNIX_EPOCH + datetime.timedelta(seconds=stat_result.st_mtime)
    except OverflowError:
        return None


# Room uploads are written through a hidden reservation file, which
# holds the upload's quota until it is renamed into place.
UPLOAD_RESERVATION_PREFIX = ".soliplex-upload-"

# The Linux NFS client (EFS included) renames a file which is unlinked
# while still open to '.nfsXXXX', until the last holder closes it.
NFS_SILLY_RENAME_PREFIX = ".nfs"


def is_internal_upload_name(name: str) -> bool:
    """Is 'name' an internal file in an uploads directory?

    Internal files are never listed, downloaded, or deleted through the
    API, nor shown to the agent's tools;  they still occupy storage.
    """
    return name.startswith(
        (UPLOAD_RESERVATION_PREFIX, NFS_SILLY_RENAME_PREFIX),
    )


def upload_files(directory: pathlib.Path) -> dict[str, os.stat_result]:
    """Map each file in the uploads 'directory' to its stat.

    Symlinks are followed, as the download views follow them: the
    operator may link a shared file in.  A missing 'directory' has no
    files.  One stat decides each entry, so an entry which is not a
    regular file when stat'd, or cannot be stat'd, is left out, as are
    internal files (see 'is_internal_upload_name').
    """
    files = {}

    for file_or_sub in directory.glob("*"):
        if is_internal_upload_name(file_or_sub.name):
            continue

        try:
            stat_result = file_or_sub.stat()
        except OSError:  # removed, a dangling or looping link, access denied
            continue

        if stat.S_ISREG(stat_result.st_mode):
            files[file_or_sub.name] = stat_result

    return files


def _lstat_counted(path: pathlib.Path) -> os.stat_result | None:
    """'lstat' 'path' for counting stored bytes, failing closed.

    Return 'None' only for a file which is gone (removed since it was
    listed):  it no longer occupies storage.  Retry 'ESTALE' (another
    NFS client replaced the file) once.  Raise every other 'OSError':
    an unreadable file must never be counted as zero bytes.
    """
    try:
        return path.lstat()
    except FileNotFoundError:
        return None
    except OSError as exc:
        if exc.errno != errno.ESTALE:
            raise

    try:
        return path.lstat()
    except FileNotFoundError:
        return None


def stored_size(path: pathlib.Path) -> int:
    """Return the bytes 'path' itself stores: its size, if a regular file.

    Unlike 'upload_files', symlinks are *not* followed:  a link placed by
    the operator stores none of its target's bytes in the uploads tree,
    so it counts as zero, as do a missing path and anything not a regular
    file.  One 'lstat' decides, so no branch is reachable only through a
    symlink.  Fails closed:  see '_lstat_counted'.
    """
    stat_result = _lstat_counted(path)

    if stat_result is None or not stat.S_ISREG(stat_result.st_mode):
        return 0

    return stat_result.st_size


@dataclasses.dataclass(frozen=True, kw_only=True)
class HiddenUpload:
    """An internal file in an uploads directory (a reservation, '.nfs*')"""

    name: str
    size_bytes: int
    mtime: float


@dataclasses.dataclass(frozen=True, kw_only=True)
class UploadsScan:
    """One pass over an uploads directory

    'files' is the listing, as 'upload_files' returns it.  'stored_bytes'
    counts what the quota counts:  every regular file, internal ones
    included, but no symlink.  'hidden' holds the internal files.
    """

    files: dict[str, os.stat_result]
    stored_bytes: int
    hidden: list[HiddenUpload]


def scan_uploads(directory: pathlib.Path) -> UploadsScan:
    """Scan the uploads 'directory' once, for its listing and its usage

    On a network filesystem each metadata call is a round trip, so one
    pass serves both:  a regular file costs a single 'lstat', which is
    also its listing stat.  The count fails closed (see
    '_lstat_counted'), so this raises 'OSError' rather than undercount.
    A missing 'directory' is empty.
    """
    files = {}
    stored_bytes = 0
    hidden = []

    try:
        entries = list(os.scandir(directory))
    except FileNotFoundError:
        entries = []

    for entry in entries:
        path = pathlib.Path(entry.path)
        lstat_result = _lstat_counted(path)

        if lstat_result is None:
            continue

        is_regular = stat.S_ISREG(lstat_result.st_mode)

        if is_regular:
            stored_bytes += lstat_result.st_size

        if is_internal_upload_name(entry.name):
            if is_regular:
                hidden.append(
                    HiddenUpload(
                        name=entry.name,
                        size_bytes=lstat_result.st_size,
                        mtime=lstat_result.st_mtime,
                    )
                )
            continue

        if is_regular:  # its 'lstat' is its listing stat
            stat_result = lstat_result
        else:  # list it if it links to a regular file, as 'upload_files'
            try:
                stat_result = path.stat()
            except OSError:  # a dangling or looping link, access denied
                continue

        # One test for files and links alike:  no branch is reachable
        # only through a symlink, which some hosts cannot create.
        if stat.S_ISREG(stat_result.st_mode):
            files[entry.name] = stat_result

    return UploadsScan(
        files=files,
        stored_bytes=stored_bytes,
        hidden=hidden,
    )


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
