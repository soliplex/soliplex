from __future__ import annotations  # forward refs in typing decls

import contextlib
import dataclasses
import io
import json
import os
import pathlib
import stat
import tempfile
import typing
import uuid

import packaging.requirements as packaging_requirements
import pydantic_ai
import skills_ref
from bubble_sandbox import config as bs_config
from bubble_sandbox import models as bs_models
from bubble_sandbox import sandbox as bs_sandbox
from PIL import Image as PIL_Image
from pydantic_ai import capabilities as ai_capabilities
from pydantic_ai import messages as ai_messages
from pydantic_ai import toolsets as ai_toolests

from soliplex import loggers
from soliplex import sandbox_audit

if typing.TYPE_CHECKING:  # avoid an import cycle at runtime
    from soliplex.config import installation as config_installation

# Applied when neither the installation nor the room sets a limit.
DEFAULT_EXECUTION_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_OUTPUT_CHARS = 10_000

_HERE = pathlib.Path(__file__)
SKILL_PROPERTIES = skills_ref.read_properties(str(_HERE.parent))

# Where 'bubble_sandbox' bind-mounts named volumes inside the
# sandbox (see 'bubble_sandbox.sandbox.volumes_sandbox_args').
SANDBOX_VOLUMES_PATH = SKILL_PROPERTIES.metadata["sandbox_volumes_path"]
# Where 'bubble_sandbox' bind-mounts the scratch directory inside the
# sandbox (see 'bubble_sandbox.sandbox.workdir_sandbox_args').
SANDBOX_WORKDIR_PATH = SKILL_PROPERTIES.metadata["sandbox_workdir_path"]


NO_OUTPUT = "The command produced no output."


def _plural(count: int, noun: str) -> str:
    return noun if count == 1 else f"{noun}s"


def format_execute_result(
    result: bs_models.ExecuteResult,
    *,
    persistent: bool = True,
) -> str:
    """Render an execution's result as the text the agent sees.

    'persistent' says whether a file written under the workspace outlives
    the call, which decides what the model can be told to do about a limit
    it cannot raise.
    """
    if result.timed_out:
        if persistent:
            remedy = (
                "narrow the input, or split the task and write intermediate "
                f"results under '{SANDBOX_WORKDIR_PATH}'"
            )
        else:
            remedy = (
                "narrow the input -- nothing written survives the command, "
                "so the work cannot be split across runs"
            )

        return (
            f"The sandbox stopped this run after {result.timeout_seconds} "
            f"seconds. That limit is fixed; do less work per run: {remedy}."
        )

    streams = [
        f"{name}:\n{stream}"
        for name, stream in (
            ("stdout", result.stdout),
            ("stderr", result.stderr),
        )
        if stream
    ]

    output = "\n\n".join(streams) if streams else NO_OUTPUT

    if result.truncated:
        if persistent:
            remedy = (
                "write the full detail to a file under "
                f"'{SANDBOX_WORKDIR_PATH}' and tell the user its name"
            )
        else:
            remedy = (
                "print a shorter summary instead -- a file written here "
                "does not survive the command"
            )

        output += (
            f"\n\n... (truncated at {result.max_output_chars} "
            f"{_plural(result.max_output_chars, 'character')} per stream; "
            f"{remedy})"
        )

    if result.exit_code is not None and result.exit_code != 0:
        return f"Command failed (exit code {result.exit_code}):\n{output}"

    return output


class SandboxUnavailable(pydantic_ai.ToolFailed):
    """The sandbox could not be started, for a reason only an operator
    can fix."""

    def __init__(self, environment, reason):
        self.environment = environment
        self.reason = reason
        super().__init__(
            f"The sandbox could not be started in the {environment!r} "
            f"environment: {reason}. Report this to the user as a sandbox "
            "configuration problem; retrying will not fix it."
        )


class WorkspacePathBlocked(pydantic_ai.ModelRetry):
    def __init__(self, path):
        self.path = path
        super().__init__(
            f"'{SANDBOX_WORKDIR_PATH}/{path}' could not be written: "
            "something in the workspace is in the way. Remove it with "
            "'run', then try again."
        )


# Anything 'bubble_sandbox' raises that the model should see as a
# failed call rather than an aborted run.
EXECUTION_ERRORS = (
    RuntimeError,
    OSError,
    bs_config.InvalidEnvironmentName,
    bs_sandbox.InvalidScriptPath,
)


# 'bubble_sandbox' reports these against a host path, which means nothing
# inside the sandbox.
_EXECUTION_ERROR_REASONS = (
    (bs_config.EnvironmentNotFound, "it is not installed on this server"),
    (
        bs_config.EnvironmentNotInitialized,
        "its Python virtualenv is missing",
    ),
    (bs_config.InvalidEnvironmentName, "its name is not usable"),
)


def translate_execution_error(exc, *, environment_name):
    """Return the error the model should see for a failed sandbox start."""
    if isinstance(exc, bs_sandbox.InvalidScriptPath):
        return WorkspacePathBlocked(exc.script_path)

    for klass, reason in _EXECUTION_ERROR_REASONS:
        if isinstance(exc, klass):
            return SandboxUnavailable(environment_name, reason)

    return SandboxUnavailable(environment_name, str(exc))


RUN_DESCRIPTION = f"""\
Run a shell command inside the bubblewrap sandbox.

Prefer ``run_python`` for anything that parses, filters, or aggregates \
data.  Use this to inspect an input before writing a script against it.

- Pass ``command`` as a single string to get shell features (pipes, \
redirection, ``&&``); it runs via "sh -c", and paths with spaces need \
quoting.
- Pass it as a list of strings -- executable first, then one element per \
argument -- to avoid quoting altogether.
- Paths are absolute and sandbox-visible: inputs under \
'{SANDBOX_VOLUMES_PATH}/', writes under '{SANDBOX_WORKDIR_PATH}'.  Host \
paths do not exist inside the sandbox.
- Independent commands can go in separate ``run`` calls in one response.
"""


async def skill_run(
    *,
    bwrap_sandbox: bs_sandbox.BwrapSandbox,
    command: str | list[str],
    environment_name: str | None = None,
    workdir: pathlib.Path | None = None,
    timeout: float | None = None,  # seconds
    extra_volumes: bs_models.VolumeMap = None,
) -> bs_models.ExecuteResult:
    """Execute a shell command in the working directory.

    Args:
        command: Shell command to execute.
        environment_name: name of sandbox environment
        workdir: path on host system to mount as the working directory
        timeout: Maximum execution time in seconds. Defaults to the value
            in the 'bubble_sandbox.config.Config' used to construct
            the toolset.
    """
    if isinstance(command, str):
        command = ["sh", "-c", command]

    try:
        result = await bwrap_sandbox.execute(
            command=command,
            environment_name=environment_name,
            workdir=workdir,
            timeout=timeout,
            extra_volumes=extra_volumes,
        )
    except EXECUTION_ERRORS as exc:
        raise translate_execution_error(
            exc,
            environment_name=environment_name,
        ) from exc

    return result


RUN_PYTHON_DESCRIPTION = f"""\
Execute a Python script inside the bubblewrap sandbox.

``script`` is Python source, not a shell command; use ``run`` for those.

- Pass a complete, self-contained script as one string.
- It runs under the Python this room configures, with that \
environment's packages.
- Print results to stdout.  Both streams are captured and returned.
- Paths are absolute and sandbox-visible: inputs under \
'{SANDBOX_VOLUMES_PATH}/', writes under '{SANDBOX_WORKDIR_PATH}'.  Host \
paths do not exist inside the sandbox.
"""


async def skill_run_python(
    *,
    bwrap_sandbox: bs_sandbox.BwrapSandbox,
    script: str,
    environment_name: str | None = None,
    workdir: pathlib.Path | None = None,
    script_path: str = bs_sandbox.DEFAULT_SCRIPT_PATH,
    timeout: float | None = None,  # seconds
    extra_volumes: bs_models.VolumeMap = None,
) -> bs_models.ExecuteResult:
    """Execute a python script in the working directory.

    Args:
        script: Python script to execute.
        environment_name: name of sandbox environment
        workdir: path on host system to mount as the working directory
        timeout: Maximum execution time in seconds. Defaults to the value
            in the 'bubble_sandbox.config.Config' used to construct
            the toolset.
    """
    try:
        result = await bwrap_sandbox.execute_python(
            script=script,
            environment_name=environment_name,
            workdir=workdir,
            script_path=script_path,
            timeout=timeout,
            extra_volumes=extra_volumes,
        )
    except EXECUTION_ERRORS as exc:
        raise translate_execution_error(
            exc,
            environment_name=environment_name,
        ) from exc

    return result


class InvalidSubdir(ValueError):
    def __init__(self, path, expected_parent):
        self.path = path
        self.expected_parent = expected_parent
        super().__init__(f"{path} not a subdir of {expected_parent}")


def _check_is_subdir(path: pathlib.Path, expected_parent: pathlib.Path):
    ep_resolved = expected_parent.resolve()

    try:
        resolved = path.resolve()
    except ValueError as exc:
        raise InvalidSubdir(path, ep_resolved) from exc
    else:
        if resolved.parent == ep_resolved:
            return

    raise InvalidSubdir(path, ep_resolved)


def _check_subdirs(base: pathlib.Path, paths: list[str]) -> pathlib.Path:
    current = base
    for path in paths:
        on_deck = current / path
        _check_is_subdir(on_deck, current)
        current = on_deck
    return current.resolve()


def get_workdir(
    workdirs_path: pathlib.Path | None,
    room_id: str | None,
    thread_id: str | None,
):
    """Return the thread's sandbox workspace, creating it if need be."""
    if (
        workdirs_path is not None
        and room_id is not None
        and thread_id is not None
    ):
        workdir = _check_subdirs(
            workdirs_path,
            [room_id, str(thread_id)],
        )
        workdir.mkdir(parents=True, exist_ok=True)
        return workdir
    else:
        return None


def _get_upload_volume(
    upload_path: pathlib.Path | None,
    volume_id: str | None,
):
    if upload_path is not None and volume_id is not None:
        volume_dir = _check_subdirs(upload_path, [str(volume_id)])
        if volume_dir.exists():
            return bs_models.VolumeInfo(
                host_path=volume_dir,
                writable=False,
            )
        else:
            return bs_models.VolumeInfo(
                host_path=None,
                writable=False,
            )


def get_extra_volumes(
    rooms_upload_path: pathlib.Path | None,
    threads_upload_path: pathlib.Path | None,
    room_id: str | None,
    thread_id: str | None,
):
    result = {}

    room_volume = _get_upload_volume(rooms_upload_path, room_id)

    if room_volume is not None:
        result["room"] = room_volume

    thread_volume = _get_upload_volume(threads_upload_path, str(thread_id))

    if thread_volume is not None:
        result["thread"] = thread_volume

    return result


# Below the workspace root, which the download endpoint does not serve.
EXECUTIONS_SUBDIR = ".soliplex/executions"


def script_snapshot_path(run_id: str, call_id: uuid.UUID) -> str:
    """Return the workspace path 'run_python' keeps its source at."""
    return f"{EXECUTIONS_SUBDIR}/script-{run_id}-{call_id}.py"


def write_transcript(
    transcripts_path: pathlib.Path | None,
    room_id: str | None,
    thread_id: str | None,
    run_id: str | None,
    *,
    call_id: uuid.UUID,
    content: str,
    suffix: str,
) -> str | None:
    """Save a command / script transcript for auditing; return its host path.

    Written under '<transcripts_path>/<room_id>/<thread_id>/<run_id>/' named
    for 'call_id', with owner-only ('0600') permissions. This directory is
    never mounted into the sandbox, so executed code cannot read or tamper
    with the saved transcript. Returns 'None' (writing nothing) when no
    'transcripts_path' is configured.
    """
    if (
        transcripts_path is not None
        and room_id is not None
        and thread_id is not None
        and run_id is not None
    ):
        run_dir = _check_subdirs(
            transcripts_path,
            [room_id, str(thread_id), str(run_id)],
        )
        run_dir.mkdir(parents=True, exist_ok=True)
        target = run_dir / f"{call_id}{suffix}"
        target.write_text(content, encoding="utf-8")
        target.chmod(0o600)

        return str(target)
    else:
        return None


class UnreadablePath(pydantic_ai.ModelRetry):
    def __init__(self, path, reason):
        self.path = path
        self.reason = reason
        super().__init__(
            f"Cannot read {path!r}: {reason}. Check the path with 'run', "
            "for example 'ls'."
        )


class ImageTooLarge(pydantic_ai.ToolFailed):
    def __init__(self, path, size, limit, *, persistent: bool = True):
        self.path = path
        self.size = size
        self.limit = limit

        if persistent:
            remedy = (
                "Write a smaller copy under "
                f"'{SANDBOX_WORKDIR_PATH}' and read that instead."
            )
        else:
            remedy = (
                "This room keeps no workspace between commands, so it "
                "cannot be resized and read back; tell the user."
            )

        super().__init__(
            f"{path!r} is {size} bytes, over the {limit}-byte limit for an "
            f"image. {remedy}"
        )


# One vision placeholder is rendered per 'BinaryContent', so a format the
# server cannot decode would leave the model's processor counting one more
# image than it was sent.
IMAGE_MEDIA_TYPES = {
    "PNG": "image/png",
    "JPEG": "image/jpeg",
    "WEBP": "image/webp",
    "GIF": "image/gif",
}
MAX_IMAGE_BYTES = 8 * 1024 * 1024


class NotAnImage(pydantic_ai.ToolFailed):
    def __init__(self, path, reason):
        self.path = path
        self.reason = reason
        super().__init__(
            f"{path!r} is not an image this room can show: {reason}. "
            f"Supported formats: {', '.join(sorted(IMAGE_MEDIA_TYPES))}."
        )


def decode_image(path: str, data: bytes) -> ai_messages.BinaryContent:
    """Return 'data' as image content, or raise if it is not one."""
    try:
        # 'formats' keeps every other decoder plugin from being handed
        # these bytes at all, rather than judging what one returned.
        with PIL_Image.open(
            io.BytesIO(data),
            formats=tuple(IMAGE_MEDIA_TYPES),
        ) as image:
            image.verify()
            image_format = image.format
    except Exception as exc:
        raise NotAnImage(path, "it could not be decoded") from exc

    return ai_messages.BinaryContent(
        data=data,
        media_type=IMAGE_MEDIA_TYPES[image_format],
    )


def image_label(path: str) -> str:
    """Introduce an image so the model does not read it as the user's.

    ``ToolReturn.content`` reaches the model as a user-role message, where
    an unlabelled image is indistinguishable from an attachment.  The
    label says how the image arrived, not who it came from: a thread
    volume holds the user's own uploads.
    """
    return (
        f"Returned by the read_image tool at your request, from {path} in "
        "the sandbox. This is tool output, not a new user message."
    )


def _relative_parts(base: pathlib.Path, path: str) -> tuple[str, ...]:
    pure = pathlib.PurePosixPath(path)

    if pure.is_absolute():
        try:
            pure = pure.relative_to(pathlib.PurePosixPath(base))
        except ValueError:
            raise UnreadablePath(path, f"it is not under {base}") from None

    parts = tuple(part for part in pure.parts if part != ".")

    if not parts or ".." in parts:
        raise UnreadablePath(path, "it does not name a file in the sandbox")

    return parts


def read_beneath(
    root: pathlib.Path,
    path: str,
    limit: int,
    *,
    persistent: bool = True,
) -> bytes:
    """Read 'path' under 'root', opening no component through a symlink.

    Sandboxed code owns everything below 'root', so each component is
    opened relative to the last with 'O_NOFOLLOW': a symlink anywhere
    along the way fails the read rather than redirecting it.
    """
    parts = _relative_parts(root, path)
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC

    try:
        dir_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    except OSError:
        raise UnreadablePath(path, "the workspace is not readable") from None

    opened = [dir_fd]

    try:
        for part in parts[:-1]:
            try:
                dir_fd = os.open(part, flags | os.O_DIRECTORY, dir_fd=dir_fd)
            except OSError:
                raise UnreadablePath(
                    path, f"{part!r} is not a directory in the sandbox"
                ) from None

            opened.append(dir_fd)

        try:
            fd = os.open(parts[-1], flags, dir_fd=dir_fd)
        except OSError:
            raise UnreadablePath(path, "there is no such file") from None

        opened.append(fd)

        stat_result = os.fstat(fd)

        if not stat.S_ISREG(stat_result.st_mode):
            raise UnreadablePath(path, "it is not a regular file")

        if stat_result.st_size > limit:
            raise ImageTooLarge(
                path,
                stat_result.st_size,
                limit,
                persistent=persistent,
            )

        with open(fd, "rb", closefd=False) as handle:
            return handle.read(limit)
    finally:
        for fd in opened:
            os.close(fd)


WORKDIR_VOLUME_NAME = "work"


def resolve_sandbox_path(
    path: str,
    *,
    workdir: pathlib.Path | None,
    volumes: bs_models.VolumeMap,
) -> tuple[pathlib.Path, str]:
    """Map a sandbox path to its host root and the part below it."""
    pure = pathlib.PurePosixPath(path)
    workdir_root = pathlib.PurePosixPath(SANDBOX_WORKDIR_PATH)
    volumes_root = pathlib.PurePosixPath(SANDBOX_VOLUMES_PATH)

    if pure.is_relative_to(workdir_root):
        if workdir is None:
            raise UnreadablePath(path, "this room keeps no workspace")

        rest = pure.relative_to(workdir_root).parts

        if rest:
            return workdir, str(pathlib.PurePosixPath(*rest))

    elif pure.is_relative_to(volumes_root):
        rest = pure.relative_to(volumes_root).parts

        if len(rest) > 1:
            volume = volumes.get(rest[0])

            if volume is not None and volume.host_path is not None:
                return volume.host_path, str(pathlib.PurePosixPath(*rest[1:]))

    raise UnreadablePath(path, "it does not name a file in the sandbox")


READ_IMAGE_DESCRIPTION = f"""\
Read an image from the sandbox so you can look at it.

``ls`` and ``cat`` return text, so this is the only way to see a chart \
the sandbox drew or a picture it was given.

- ``path`` is an absolute sandbox path, under '{SANDBOX_WORKDIR_PATH}' or \
'{SANDBOX_VOLUMES_PATH}/'.
- Use it when the picture is what you need to answer.  An image the user \
asked for, and will download, does not need reading back.
"""


def effective_volumes(
    static: bs_models.VolumeMap | None,
    runtime: bs_models.VolumeMap | None,
) -> bs_models.VolumeMap:
    """Return the volume map the sandbox will mount, runtime over static."""
    return (static or {}) | (runtime or {})


def _downloadable_count(directory: pathlib.Path | None) -> int:
    """Count what the workdir endpoint serves: top-level regular files."""
    if directory is None or not directory.is_dir():
        return 0

    return sum(
        1
        for entry in directory.glob("*")
        if not entry.is_symlink() and entry.is_file()
    )


def _file_count(volume: bs_models.VolumeInfo) -> int:
    return _downloadable_count(volume.host_path)


def _count_phrase(count: int) -> str:
    if not count:
        return "empty"

    return f"{count} file" if count == 1 else f"{count} files"


def _dependency_names(dependencies: list[str]) -> list[str]:
    """Return the project name of each requirement string."""
    names = []

    for dependency in dependencies:
        try:
            names.append(packaging_requirements.Requirement(dependency).name)
        except packaging_requirements.InvalidRequirement:
            names.append(dependency)

    return names


@contextlib.contextmanager
def workspace(
    workdirs_path: pathlib.Path | None,
    room_id: str | None,
    thread_id: str | None,
):
    """Yield the directory to mount read-write, and whether it survives.

    Without 'workdirs_path' the call gets a temporary directory, discarded
    when it returns.
    """
    workdir = get_workdir(workdirs_path, room_id, thread_id)

    if workdir is not None:
        yield workdir, True
        return

    with tempfile.TemporaryDirectory(
        ignore_cleanup_errors=True,
    ) as temporary:
        yield pathlib.Path(temporary), False


def render_mount_table(
    *,
    workdir: pathlib.Path | None,
    persistent: bool = True,
    volumes: bs_models.VolumeMap,
    dependencies: list[str],
) -> str:
    """Return the per-request description of what the sandbox mounts."""
    if persistent:
        workdir_note = (
            f"{_count_phrase(_downloadable_count(workdir))}, "
            "kept for this thread"
        )
    else:
        workdir_note = "discarded after each command"

    rows = [(SANDBOX_WORKDIR_PATH, "read-write", workdir_note)]
    rows.extend(
        (
            f"{SANDBOX_VOLUMES_PATH}/{name}",
            "read-write" if volume.writable else "read-only",
            _count_phrase(_file_count(volume)),
        )
        for name, volume in sorted(volumes.items())
    )

    width = max(len(path) for path, _, _ in rows)
    table = "\n".join(
        f"  {path:<{width}}  {access:<10}  {note}"
        for path, access, note in rows
    )

    if persistent:
        preamble = (
            "Sandbox: no network. Files you write at the top level of "
            f"{SANDBOX_WORKDIR_PATH} are downloadable by the user -- name "
            "the file when you write one. Files from earlier turns are "
            "still there; do not assume they are current, and do not "
            "delete or overwrite them unless the task calls for it."
        )
    else:
        preamble = (
            f"Sandbox: no network. {SANDBOX_WORKDIR_PATH} is discarded "
            "when each command ends, so nothing written there survives "
            "into the next one, and the user cannot fetch it. Report "
            "everything that matters in your reply."
        )

    lines = [preamble, "", table]

    names = _dependency_names(dependencies)
    if names:
        lines.extend(["", f"Python packages: {', '.join(names)}"])

    return "\n".join(lines)


def create_sandbox_toolset(
    *,
    id: str | None = None,
    environment: str = "bare",
    sandbox_config: bs_config.Config | None = None,
    volumes: bs_models.VolumeMap | None = None,
    max_retries: int = 1,
    multimodal: bool = False,
    installation_config: config_installation.InstallationConfig | None = None,
) -> ai_toolests.FunctionToolset:
    """Create a sandbox toolset for shell / script execution.

    This toolset provides tools for executing shell commands and Python
    scripts.

    Args:
        id: Optional unique ID for the toolset.

        environment: name of the configured environment every execution
            runs in.  The model does not choose it.

        sandbox_config: bubble_sandbox configuration

        volumes: bubble_sandbox volume map

        max_retries: Maximum number of retries for each tool during a run.
            When the model sends invalid arguments (e.g. missing required
            fields), the validation error is fed back and the model can retry
            up to this many times. Defaults to 1.

    Returns:
        FunctionToolset with 'run' and 'run_python', plus 'read_image'
        when 'multimodal' says the room's model accepts images.
    """
    if sandbox_config is None:
        sandbox_config = bs_config.Config()

    if installation_config is not None:
        i_config = installation_config
        s_config = i_config.sandbox_config
        sandbox_config.environments_pathname = s_config.environments_path
        workdirs_path = s_config.workdirs_path

        threads_upload_path = i_config.threads_upload_path
        rooms_upload_path = i_config.rooms_upload_path
        transcripts_path = s_config.transcripts_path
    else:
        workdirs_path = None
        threads_upload_path = None
        rooms_upload_path = None
        transcripts_path = None

    if volumes is None:
        volumes = {}

    bwrap_sandbox = bs_sandbox.BwrapSandbox(
        default_environment=environment,
        config=sandbox_config,
        volumes=volumes,
    )

    toolset = ai_toolests.FunctionToolset(id=id, max_retries=max_retries)

    async def _execute(ctx, *, action, content, suffix, run_in):
        deps = ctx.deps

        with (
            sandbox_audit.audit_sandbox_exec(
                deps,
                action=action,
                environment=environment,
            ) as access,
            workspace(
                workdirs_path,
                deps.room_id,
                deps.thread_id,
            ) as (workdir, persistent),
        ):
            access.record_workdir(workdir)

            extra_volumes = get_extra_volumes(
                rooms_upload_path,
                threads_upload_path,
                deps.room_id,
                deps.thread_id,
            )

            call_id = uuid.uuid4()

            ref = write_transcript(
                transcripts_path,
                deps.room_id,
                deps.thread_id,
                deps.run_id,
                call_id=call_id,
                content=content,
                suffix=suffix,
            )
            if ref is not None:
                access.record_ref(ref)

            result = await run_in(
                workdir=workdir,
                extra_volumes=extra_volumes,
                call_id=call_id,
            )
            access.record_result(result)

            return format_execute_result(result, persistent=persistent)

    @toolset.tool(description=RUN_DESCRIPTION)
    async def run(
        ctx: pydantic_ai.RunContext,
        command: str | list[str],
    ) -> str:
        async def run_in(*, workdir, extra_volumes, call_id):
            return await skill_run(
                bwrap_sandbox=bwrap_sandbox,
                command=command,
                environment_name=environment,
                workdir=workdir,
                extra_volumes=extra_volumes,
            )

        return await _execute(
            ctx,
            action=loggers.AUDIT_SANDBOX_ACTION_RUN,
            content=(
                command if isinstance(command, str) else json.dumps(command)
            ),
            suffix=".txt",
            run_in=run_in,
        )

    @toolset.tool(description=RUN_PYTHON_DESCRIPTION)
    async def run_python(
        ctx: pydantic_ai.RunContext,
        script: str,
    ) -> str:
        run_id = ctx.deps.run_id

        async def run_in(*, workdir, extra_volumes, call_id):
            return await skill_run_python(
                bwrap_sandbox=bwrap_sandbox,
                script=script,
                environment_name=environment,
                workdir=workdir,
                script_path=script_snapshot_path(run_id, call_id),
                extra_volumes=extra_volumes,
            )

        return await _execute(
            ctx,
            action=loggers.AUDIT_SANDBOX_ACTION_RUN_PYTHON,
            content=script,
            suffix=".py",
            run_in=run_in,
        )

    if multimodal:

        @toolset.tool(description=READ_IMAGE_DESCRIPTION)
        async def read_image(
            ctx: pydantic_ai.RunContext,
            path: str,
        ) -> ai_messages.ToolReturn:
            deps = ctx.deps

            with sandbox_audit.audit_sandbox_read_image(
                deps, path=path
            ) as access:
                workdir = get_workdir(
                    workdirs_path,
                    deps.room_id,
                    deps.thread_id,
                )
                mounted = effective_volumes(
                    volumes,
                    get_extra_volumes(
                        rooms_upload_path,
                        threads_upload_path,
                        deps.room_id,
                        deps.thread_id,
                    ),
                )
                root, relative = resolve_sandbox_path(
                    path,
                    workdir=workdir,
                    volumes=mounted,
                )
                volume_name = (
                    WORKDIR_VOLUME_NAME
                    if root == workdir
                    else pathlib.PurePosixPath(path).parts[3]
                )

                data = read_beneath(
                    root,
                    relative,
                    MAX_IMAGE_BYTES,
                    persistent=workdir is not None,
                )
                content = decode_image(path, data)
                access.record_image(volume_name, data, content.media_type)

                return ai_messages.ToolReturn(
                    return_value=f"Read {path}.",
                    content=[image_label(path), content],
                )

    return toolset


def _instructions() -> str:
    text = (pathlib.Path(__file__).parent / "SKILL.md").read_text(
        encoding="utf-8"
    )
    return text.split("---", 2)[-1].strip()


@dataclasses.dataclass
class SandboxCapability(ai_capabilities.AbstractCapability[typing.Any]):
    environment: str = "bare"
    sandbox_config: bs_config.Config | None = None
    volumes: bs_models.VolumeMap | None = None
    max_retries: int = 1
    multimodal: bool = False
    installation_config: typing.Any = None

    def get_instructions(self) -> list[typing.Any]:
        return [_instructions(), self.runtime_instructions]

    def _dependencies(self) -> list[str]:
        sandbox_config = self.sandbox_config or bs_config.Config()
        i_config = self.installation_config

        if i_config is not None and i_config.sandbox_config is not None:
            sandbox_config = sandbox_config.model_copy(
                update={
                    "environments_pathname": (
                        i_config.sandbox_config.environments_path
                    )
                }
            )

        for info in sandbox_config.list_environments():
            if info.name == self.environment:
                return list(info.dependencies)

        return []

    async def runtime_instructions(self, ctx: pydantic_ai.RunContext) -> str:
        deps = ctx.deps
        i_config = self.installation_config

        if i_config is None:
            workdirs_path = rooms_upload_path = threads_upload_path = None
        else:
            workdirs_path = i_config.sandbox_config.workdirs_path
            rooms_upload_path = i_config.rooms_upload_path
            threads_upload_path = i_config.threads_upload_path

        workdir = get_workdir(
            workdirs_path,
            deps.room_id,
            deps.thread_id,
        )

        return render_mount_table(
            workdir=workdir,
            persistent=workdir is not None,
            volumes=effective_volumes(
                self.volumes,
                get_extra_volumes(
                    rooms_upload_path,
                    threads_upload_path,
                    deps.room_id,
                    deps.thread_id,
                ),
            ),
            dependencies=self._dependencies(),
        )

    def get_toolset(self) -> ai_toolests.FunctionToolset:
        return create_sandbox_toolset(
            id=self.id,
            environment=self.environment,
            sandbox_config=self.sandbox_config,
            volumes=self.volumes,
            max_retries=self.max_retries,
            multimodal=self.multimodal,
            installation_config=self.installation_config,
        )


def create_bwrap_sandbox_capability(
    id: str | None = None,
    *,
    environment: str = "bare",
    sandbox_config: bs_config.Config | None = None,
    volumes: bs_models.VolumeMap | None = None,
    max_retries: int = 1,
    multimodal: bool = False,
    installation_config: config_installation.InstallationConfig | None = None,
    defer_loading: bool = False,
) -> SandboxCapability:
    return SandboxCapability(
        id=id or SKILL_PROPERTIES.name,
        description=SKILL_PROPERTIES.description.strip(),
        defer_loading=defer_loading,
        environment=environment,
        sandbox_config=sandbox_config,
        volumes=volumes,
        max_retries=max_retries,
        multimodal=multimodal,
        installation_config=installation_config,
    )
