import dataclasses
import json
import pathlib
import typing
import uuid

import pydantic_ai
import skills_ref
from bubble_sandbox import config as bs_config
from bubble_sandbox import models as bs_models
from bubble_sandbox import sandbox as bs_sandbox
from pydantic_ai import capabilities as ai_capabilities
from pydantic_ai import toolsets as ai_toolests

from soliplex import loggers
from soliplex import sandbox_audit

VolumeName = typing.Literal["thread"] | typing.Literal["room"]

_HERE = pathlib.Path(__file__)
SKILL_PROPERTIES = skills_ref.read_properties(str(_HERE.parent))

# Where 'bubble_sandbox' bind-mounts named volumes inside the
# sandbox (see 'bubble_sandbox.sandbox.volumes_sandbox_args').
SANDBOX_VOLUMES_PATH = SKILL_PROPERTIES.metadata["sandbox_volumes_path"]
# Where 'bubble_sandbox' bind-mounts the scratch directory inside the
# sandbox (see 'bubble_sandbox.sandbox.workdir_sandbox_args').
SANDBOX_WORKDIR_PATH = SKILL_PROPERTIES.metadata["sandbox_workdir_path"]


LIST_ENVIRONMENTS_DESCRIPTION = """
Return a list of information about available sandbox environments

Call this tool before the first ``run`` or ``run_python`` of a turn: \
their ``environment_name`` argument accepts nothing but the names \
returned here.

Each entry will contain these fields:
- 'name' (string) pass this value to the ``run`` and ``run_python`` \
tools to run the tool in the environment.
- 'description' (string) describes the purposes for which the environment is \
configured.
- 'dependencies' (list of string): names of Python projects on which the \
environment depends.
"""

AllowedEnvironments = list[str] | None


async def skill_list_environments(
    *,
    bwrap_sandbox: bs_sandbox.BwrapSandbox,
    allowed_environments: AllowedEnvironments = None,
) -> list[bs_models.EnvironmentInfo]:
    candidates = bwrap_sandbox.config.list_environments()
    if allowed_environments is not None:
        return [env for env in candidates if env.name in allowed_environments]
    else:
        return candidates


class UnknownEnvironment(pydantic_ai.ModelRetry):
    def __init__(self, name, choices):
        self.name = name
        self.choices = choices
        c_list = ", ".join(repr(name) for name in choices)
        super().__init__(
            f"{name!r} is not an available sandbox environment. "
            "Environment names cannot be guessed or copied from examples: "
            "call 'list_environments' and pass one of the names it returns. "
            f"Available environments: {c_list}."
        )


class NoEnvironmentsConfigured(pydantic_ai.ToolFailed):
    def __init__(self, name):
        self.name = name
        super().__init__(
            f"{name!r} is not an available sandbox environment, "
            "and this room has none configured. "
            "Tell the user the sandbox skill is not configured."
        )


async def check_environment_name(
    *,
    bwrap_sandbox: bs_sandbox.BwrapSandbox,
    environment_name: str | None,
    allowed_environments: AllowedEnvironments = None,
) -> None:
    """Reject an 'environment_name' the model invented, before anything runs.

    Guards 'run' / 'run_python' against a name the model guessed rather than
    read from a 'list_environments' result. Without it, an unknown name
    aborts the whole agent run, and a name which exists but is *not* in
    'allowed_environments' runs anyway -- 'allowed_environments' otherwise
    only filters what 'list_environments' reports.

    The two failures differ in whether the model can do anything about them,
    so they are reported differently. A name outside the choices is fixable
    by calling 'list_environments' and passing one of them, which is what
    'ModelRetry' asks for (and matches how 'pydantic_ai' itself reports an
    unknown *tool* name). A room with no environments at all is the
    operator's to fix: 'ToolFailed' shows the model a failed call to report
    rather than one to retry, and spends none of the tool's retry budget.

    'None' passes through unchecked: it selects the environment the skill was
    configured with, which is the operator's choice rather than the model's.
    """
    if environment_name is None:
        return

    available = [
        env.name
        for env in await skill_list_environments(
            bwrap_sandbox=bwrap_sandbox,
            allowed_environments=allowed_environments,
        )
    ]

    if environment_name in available:
        return

    if not available:
        raise NoEnvironmentsConfigured(name=environment_name)

    raise UnknownEnvironment(
        name=environment_name,
        choices=available,
    )


def _environment_label(environment_name):
    """Name the environment a run asked for, without leaking host paths.

    'bubble_sandbox' builds its messages from the resolved filesystem path
    ("Environment not found: PosixPath('/app/sandbox/environments/...')"),
    which is meaningless inside the sandbox and not something to put in
    front of the model. The requested name says the same thing.
    """
    if environment_name is None:
        return "the environment this room uses by default"
    return f"the {environment_name!r} environment"


class EnvironmentMissing(pydantic_ai.ToolFailed):
    def __init__(self, environment_name):
        self.environment_name = environment_name
        super().__init__(
            f"The sandbox cannot run: {_environment_label(environment_name)} "
            "is not installed on this server. Report this to the user as a "
            "sandbox configuration problem; retrying will not fix it."
        )


class EnvironmentNotBuilt(pydantic_ai.ToolFailed):
    def __init__(self, environment_name):
        self.environment_name = environment_name
        super().__init__(
            f"The sandbox cannot run: {_environment_label(environment_name)} "
            "is installed but its Python virtualenv is missing. Report this "
            "to the user as a sandbox configuration problem; retrying will "
            "not fix it."
        )


class EnvironmentNameInvalid(pydantic_ai.ToolFailed):
    def __init__(self, environment_name):
        self.environment_name = environment_name
        super().__init__(
            f"The sandbox cannot run: {_environment_label(environment_name)} "
            "is not a usable environment name. Report this to the user as a "
            "sandbox configuration problem; retrying will not fix it."
        )


class SandboxUnavailable(pydantic_ai.ToolFailed):
    def __init__(self, environment_name, reason):
        self.environment_name = environment_name
        self.reason = reason
        super().__init__(
            "The sandbox could not be started in "
            f"{_environment_label(environment_name)}: {reason}. Report this "
            "to the user; retrying will not fix it."
        )


# 'bubble_sandbox' reports a bad environment name with 'ValueError' and
# 'FileNotFoundError' subclasses, not 'RuntimeError'; letting one escape
# aborts the agent run (soliplex#1306) instead of handing the model an
# error it can act on.
EXECUTION_ERRORS = (
    RuntimeError,
    OSError,
    bs_config.InvalidEnvironmentName,
)


def translate_execution_error(exc, *, environment_name):
    """Return the error the model should see for a failed sandbox start.

    Every case here is the operator's to fix rather than the model's --
    'check_environment_name' has already rejected any name the model could
    have chosen differently -- so each maps to a 'ToolFailed' subclass: the
    model sees a failed call to report, spends none of the tool's retry
    budget, and is told plainly that retrying will not help.
    """
    if isinstance(exc, bs_config.EnvironmentNotFound):
        return EnvironmentMissing(environment_name)

    if isinstance(exc, bs_config.EnvironmentNotInitialized):
        return EnvironmentNotBuilt(environment_name)

    if isinstance(exc, bs_config.InvalidEnvironmentName):
        return EnvironmentNameInvalid(environment_name)

    return SandboxUnavailable(environment_name, str(exc))


RUN_DESCRIPTION = f"""\
Run a shell command inside the bubblewrap sandbox.

IMPORTANT: Prefer the ``run_python`` tool for anything that parses, \
filters, or aggregates data. Use this tool for quick inspection of an \
input file -- checking its size, type, or first few lines before \
writing a script against it.

## Usage
- To run a command needing shell features (pipes, redirection, ``&&``), \
pass ``command`` as a single string; it is run via "sh -c".
- Otherwise pass ``command`` as a list of strings: the executable name \
or path first, then one element per argument. This form needs no \
quoting and is the safer default.
- ``environment_name`` selects the environment to run in. Pass only a \
``name`` that ``list_environments`` returned in this conversation -- \
never a guessed name, a package name, or a name copied from an example. \
Omit it to use the configured default.
- ``timeout`` caps the run in seconds; omit it to use the configured \
default.
- Paths must be absolute and sandbox-visible: read inputs from \
'{SANDBOX_VOLUMES_PATH}/thread/' or '{SANDBOX_VOLUMES_PATH}/room/', \
and write only under '{SANDBOX_WORKDIR_PATH}'. Host paths do not exist \
inside the sandbox.
- Quote any path containing spaces when using the string form.
- When running several independent commands, make separate ``run`` \
calls in a single response (parallel execution).

## Debugging
- Read the FULL error output when a command fails -- the root cause is \
often in the middle of a traceback, not the last line.
- Change one thing at a time; do not make multiple speculative fixes.
- If the same approach fails 3 times, STOP and report the error rather \
than retrying.
"""


LIST_VOLUME_FILES_DESCRIPTION = f"""\
Return the sandbox paths of the files in a sandbox volume.

Each entry is an absolute path as seen from inside the sandbox (for \
example '{SANDBOX_VOLUMES_PATH}/thread/orders.csv'), so it can be passed \
straight to the ``run`` and ``run_python`` tools. Returns an empty \
list when the volume holds no files or is not configured.
"""


async def skill_list_volume_files(
    *,
    volume: VolumeName,
    room_upload_path: pathlib.Path | None,
    thread_upload_path: pathlib.Path | None,
) -> list[str]:

    def _list_volume_files(volume_path: pathlib.Path | None) -> list[str]:
        if volume_path is None:
            return []

        # Report the path the sandbox sees, not the host path: the volume
        # is bind-mounted at '{SANDBOX_VOLUMES_PATH}/<volume>', so the host
        # path is both meaningless inside the sandbox and not something
        # to leak into the prompt.
        return [
            f"{SANDBOX_VOLUMES_PATH}/{volume}/{sub.name}"
            for sub in sorted(volume_path.glob("*"))
            if sub.is_file()
        ]

    if volume == "thread":
        return _list_volume_files(thread_upload_path)
    elif volume == "room":
        return _list_volume_files(room_upload_path)
    else:
        return []


async def skill_run(
    *,
    bwrap_sandbox: bs_sandbox.BwrapSandbox,
    command: str | list[str],
    environment_name: str | None = None,
    workdir: pathlib.Path | None = None,
    timeout: float | None = None,  # seconds
    extra_volumes: bs_models.VolumeMap = None,
) -> str:
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

    output = result.output
    if result.truncated:
        output += "\n\n... (output truncated)"

    if result.exit_code is not None and result.exit_code != 0:
        return f"Command failed (exit code {result.exit_code}):\n{output}"

    return str(output)


RUN_PYTHON_DESCRIPTION = f"""\
Execute a Python script in the sandbox environment.

IMPORTANT: The ``script`` parameter must be valid Python source code. \
Do NOT pass shell commands — use the ``run`` tool for those.

## Usage
- Pass a complete, self-contained Python script as the ``script`` string.
- The script runs via the Python interpreter built into the chosen \
environment, with access to its pre-installed packages.
- Call ``list_environments`` first to discover available environments \
and their installed packages. ``environment_name`` must be one of the \
``name`` values it returned -- never a guessed name, a package name, or \
a name copied from an example. Omit it to use the configured default.
- ``timeout`` caps the run in seconds; omit it to use the configured \
default.
- Print results to stdout — the output is captured and returned.
- Use absolute paths (e.g. ``{SANDBOX_WORKDIR_PATH}/data.csv``) when \
reading or writing files.
- Inputs under '{SANDBOX_VOLUMES_PATH}/thread/' and \
'{SANDBOX_VOLUMES_PATH}/room/' are read-only; write only under \
'{SANDBOX_WORKDIR_PATH}'. Host paths do not exist inside the sandbox.

## Debugging
- Read the FULL error output when a script fails — the root cause is \
often in the middle of a traceback, not the last line.
- Fix one thing at a time — don't make multiple speculative fixes.
- If something fails 3 times with the same approach, STOP and try a \
completely different strategy.

## Safety
- Be careful not to introduce command injection vulnerabilities.
- Be careful with destructive commands (`rm -rf`, `drop table`, etc.) — \
verify the target path/object before executing.
"""


async def skill_run_python(
    *,
    bwrap_sandbox: bs_sandbox.BwrapSandbox,
    script: str,
    environment_name: str | None = None,
    workdir: pathlib.Path | None = None,
    timeout: float | None = None,  # seconds
    extra_volumes: bs_models.VolumeMap = None,
) -> str:
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
            timeout=timeout,
            extra_volumes=extra_volumes,
        )
    except EXECUTION_ERRORS as exc:
        raise translate_execution_error(
            exc,
            environment_name=environment_name,
        ) from exc

    output = result.output
    if result.truncated:
        output += "\n\n... (output truncated)"

    if result.exit_code is not None and result.exit_code != 0:
        return f"Command failed (exit code {result.exit_code}):\n{output}"

    return str(output)


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
    run_id: str | None,
):
    if (
        workdirs_path is not None
        and room_id is not None
        and thread_id is not None
        and run_id is not None
    ):
        workdir = _check_subdirs(
            workdirs_path,
            [room_id, str(thread_id), str(run_id)],
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


def write_transcript(
    transcripts_path: pathlib.Path | None,
    room_id: str | None,
    thread_id: str | None,
    run_id: str | None,
    *,
    content: str,
    suffix: str,
) -> str | None:
    """Save a command / script transcript for auditing; return its host path.

    Written under '<transcripts_path>/<room_id>/<thread_id>/<run_id>/' with a
    UUID-based filename and owner-only ('0600') permissions. This directory is
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
        target = run_dir / f"{uuid.uuid4()}{suffix}"
        target.write_text(content, encoding="utf-8")
        target.chmod(0o600)

        return str(target)
    else:
        return None


def create_sandbox_toolset(
    *,
    id: str | None = None,
    default_environment: str = "bare",
    allowed_environments: AllowedEnvironments = None,
    sandbox_config: bs_config.Config | None = None,
    volumes: bs_models.VolumeMap | None = None,
    max_retries: int = 1,
    installation_config=None,  # noqa F821 cycles
) -> ai_toolests.FunctionToolset:
    """Create a sandbox toolset for shell / script execution.

    This toolset provides tools for executing shell commands and Python
    scripts.

    Args:
        id: Optional unique ID for the toolset.

        default_environment: name of default configured environment

        sandbox_config: bubble_sandbox configuration

        volumes: bubble_sandbox volume map

        max_retries: Maximum number of retries for each tool during a run.
            When the model sends invalid arguments (e.g. missing required
            fields), the validation error is fed back and the model can retry
            up to this many times. Defaults to 1.

    Returns:
        FunctionToolset with these tools:
        'list_environments, 'list_volume_files', 'run' and 'run_python'.
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
        default_environment=default_environment,
        config=sandbox_config,
        volumes=volumes,
    )

    toolset = ai_toolests.FunctionToolset(id=id, max_retries=max_retries)

    @toolset.tool(description=LIST_ENVIRONMENTS_DESCRIPTION)
    async def list_environments(
        ctx: pydantic_ai.RunContext,
    ) -> list[bs_models.EnvironmentInfo]:
        return await skill_list_environments(
            bwrap_sandbox=bwrap_sandbox,
            allowed_environments=allowed_environments,
        )

    @toolset.tool(description=LIST_VOLUME_FILES_DESCRIPTION)
    async def list_volume_files(
        ctx: pydantic_ai.RunContext,
        volume: VolumeName,
    ) -> list[str]:
        if installation_config is None:
            return []

        else:
            deps = ctx.deps
            room_id = deps.room_id
            thread_id = deps.thread_id

            return await skill_list_volume_files(
                volume=volume,
                room_upload_path=(
                    _check_subdirs(rooms_upload_path, [room_id])
                    if (rooms_upload_path is not None and room_id is not None)
                    else None
                ),
                thread_upload_path=(
                    _check_subdirs(threads_upload_path, [thread_id])
                    if (
                        threads_upload_path is not None
                        and thread_id is not None
                    )
                    else None
                ),
            )

    @toolset.tool(description=RUN_DESCRIPTION)
    async def run(
        ctx: pydantic_ai.RunContext,
        command: str | list[str],
        environment_name: str | None = None,
        timeout: float | None = None,  # seconds
    ) -> str:
        await check_environment_name(
            bwrap_sandbox=bwrap_sandbox,
            environment_name=environment_name,
            allowed_environments=allowed_environments,
        )

        deps = ctx.deps
        workdir = get_workdir(
            workdirs_path,
            deps.room_id,
            deps.thread_id,
            deps.run_id,
        )

        extra_volumes = get_extra_volumes(
            rooms_upload_path,
            threads_upload_path,
            deps.room_id,
            deps.thread_id,
        )

        with sandbox_audit.audit_sandbox_exec(
            deps,
            action=loggers.AUDIT_SANDBOX_ACTION_RUN,
            environment=environment_name,
            workdir=workdir,
        ) as access:
            ref = write_transcript(
                transcripts_path,
                deps.room_id,
                deps.thread_id,
                deps.run_id,
                content=(
                    command
                    if isinstance(command, str)
                    else json.dumps(command)
                ),
                suffix=".txt",
            )
            if ref is not None:
                access.record_ref(ref)

            return await skill_run(
                bwrap_sandbox=bwrap_sandbox,
                command=command,
                environment_name=environment_name,
                workdir=workdir,
                timeout=timeout,
                extra_volumes=extra_volumes,
            )

    @toolset.tool(description=RUN_PYTHON_DESCRIPTION)
    async def run_python(
        ctx: pydantic_ai.RunContext,
        script: str,
        environment_name: str | None = None,
        timeout: float | None = None,  # seconds
    ) -> str:
        await check_environment_name(
            bwrap_sandbox=bwrap_sandbox,
            environment_name=environment_name,
            allowed_environments=allowed_environments,
        )

        deps = ctx.deps
        workdir = get_workdir(
            workdirs_path,
            deps.room_id,
            deps.thread_id,
            deps.run_id,
        )

        extra_volumes = get_extra_volumes(
            rooms_upload_path,
            threads_upload_path,
            deps.room_id,
            deps.thread_id,
        )

        with sandbox_audit.audit_sandbox_exec(
            deps,
            action=loggers.AUDIT_SANDBOX_ACTION_RUN_PYTHON,
            environment=environment_name,
            workdir=workdir,
        ) as access:
            ref = write_transcript(
                transcripts_path,
                deps.room_id,
                deps.thread_id,
                deps.run_id,
                content=script,
                suffix=".py",
            )
            if ref is not None:
                access.record_ref(ref)

            return await skill_run_python(
                bwrap_sandbox=bwrap_sandbox,
                script=script,
                environment_name=environment_name,
                workdir=workdir,
                timeout=timeout,
                extra_volumes=extra_volumes,
            )

    return toolset


def _instructions() -> str:
    text = (pathlib.Path(__file__).parent / "SKILL.md").read_text(
        encoding="utf-8"
    )
    return text.split("---", 2)[-1].strip()


@dataclasses.dataclass
class SandboxCapability(ai_capabilities.AbstractCapability[typing.Any]):
    default_environment: str = "bare"
    allowed_environments: AllowedEnvironments = None
    sandbox_config: bs_config.Config | None = None
    volumes: bs_models.VolumeMap | None = None
    max_retries: int = 1
    installation_config: typing.Any = None

    def get_instructions(self) -> str:
        return _instructions()

    def get_toolset(self) -> ai_toolests.FunctionToolset:
        return create_sandbox_toolset(
            id=self.id,
            default_environment=self.default_environment,
            allowed_environments=self.allowed_environments,
            sandbox_config=self.sandbox_config,
            volumes=self.volumes,
            max_retries=self.max_retries,
            installation_config=self.installation_config,
        )


def create_bwrap_sandbox_capability(
    id: str | None = None,
    *,
    default_environment: str = "bare",
    allowed_environments: AllowedEnvironments = None,
    sandbox_config: bs_config.Config | None = None,
    volumes: bs_models.VolumeMap | None = None,
    max_retries: int = 1,
    installation_config=None,  # noqa F821 cycles
    defer_loading: bool = False,
) -> SandboxCapability:
    return SandboxCapability(
        id=id or SKILL_PROPERTIES.name,
        description=SKILL_PROPERTIES.description.strip(),
        defer_loading=defer_loading,
        default_environment=default_environment,
        allowed_environments=allowed_environments,
        sandbox_config=sandbox_config,
        volumes=volumes,
        max_retries=max_retries,
        installation_config=installation_config,
    )
