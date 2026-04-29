import pathlib
import typing

import pydantic
import pydantic_ai
from bubble_sandbox import config as bs_config
from bubble_sandbox import models as bs_models
from bubble_sandbox import sandbox as bs_sandbox
from haiku.skills import models as hs_models
from haiku.skills import parser as hs_parser
from haiku.skills import state as hs_state
from pydantic_ai import toolsets as ai_toolests

VolumeName = typing.Literal["thread"] | typing.Literal["room"]

SKILL_NAME = "bubble-sandbox"
SKILL_DESCRIPTION = """\
Write and execute Python code in a bubblewrap sandbox
"""
SKILL_METADATA = hs_models.SkillMetadata(
    name=SKILL_NAME,
    description=SKILL_DESCRIPTION,
)


EnvironmentInfo = dict[str, str]


class SandboxState(pydantic.BaseModel):
    room_id: str | None = None
    thread_id: str | None = None
    run_id: str | None = None


STATE_TYPE = SandboxState
STATE_NAMESPACE = SKILL_NAME

LIST_ENVIRONMENTS_DESCRIPTION = """
Return a list of information about available sandbox environments

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
) -> list[EnvironmentInfo]:
    candidates = bwrap_sandbox.config.list_environments()
    if allowed_environments is not None:
        return [env for env in candidates if env.name in allowed_environments]
    else:
        return candidates


RUN_DESCRIPTION = """\
Execute a shell command in the working directory.

IMPORTANT: This tool is for operations that REQUIRE a real shell — \
running tests, builds, git commands, package installs, running scripts.

## Usage
- To run a command requiring shell support, pass the command as a single \
string; the skill will then pass it to a shell via "sh -c".
- To run a command which does not require shell support, pass a list of \
strings, where the first element is the name or path of the executable \
to run, and the remaining elements are arguments to that executable.
- Always quote file paths containing spaces with double quotes.
- Prefer absolute paths over relative paths.
- When running multiple independent commands, make separate `execute` calls \
in a single response (parallel execution).
- When commands depend on each other, chain with `&&` in a single call \
(e.g., `cd /project && make test`).
- For long-running commands (builds, large test suites), increase the timeout.

## Debugging
- Read the FULL error output when a command fails — the root cause is often \
in the middle of a traceback, not the last line.
- Reproduce the error before attempting a fix.
- Change one thing at a time — don't make multiple speculative fixes.
- If something fails 3 times with the same approach, STOP and try a \
completely different strategy.

## Safety
- Be careful not to introduce command injection vulnerabilities.
- Be careful with destructive commands (`rm -rf`, `drop table`, etc.) — \
verify the target path/object before executing.
"""


LIST_VOLUME_FILES_DESCRIPTION = """
Return a list of absolute filenames of files in a sandbox volume
"""


async def skill_list_volume_files(
    *,
    volume: VolumeName,
    room_upload_path: pathlib.Path,
    thread_upload_path: pathlib.Path,
) -> list[str]:

    def _list_volume_files(volume_path: pathlib.Path) -> list[str]:
        return [
            sub.absolute().name
            for sub in volume_path.glob("*")
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
    environment_name: str = None,
    workdir: pathlib.Path | None = None,
    timeout: float = None,  # seconds
    extra_volumes: bs_models.VolumeMap = None,
) -> str:
    """Execute a shell command in the working directory.

    Args:
        command: Shell command to execute.
        environment_name: name of sandbox environment (defaults to 'bare')
        workdir: path on host system to mount as the working directory
        timeout: Maximum execution time in seconds. Defaults to the value
            in the 'buuble_sandbox.config.Config' used to construct
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
    except RuntimeError as e:
        return f"Error: {e}"

    output = result.output
    if result.truncated:
        output += "\n\n... (output truncated)"

    if result.exit_code is not None and result.exit_code != 0:
        return f"Command failed (exit code {result.exit_code}):\n{output}"

    return str(output)


RUN_PYTHON_DESCRIPTION = """\
Execute a Python script in the sandbox environment.

IMPORTANT: The ``script`` parameter must be valid Python source code. \
Do NOT pass shell commands — use the ``execute`` tool for shell commands.

## Usage
- Pass a complete, self-contained Python script as the ``script`` string.
- The script runs via the Python interpreter built into the chosen \
environment, with access to its pre-installed packages.
- Use ``list_environments`` first to discover available environments \
and their installed packages.
- Print results to stdout — the output is captured and returned.
- Use absolute paths (e.g. ``/sandbox/work/data.csv``) when \
reading or writing files.

## Debugging
- Read the FULL error output when a script fails — the root cause is \
often in the middle of a traceback, not the last line.
- Fix one thing at a time — don't make multiple speculative fixes.
- If something fails 3 times with the same approach, STOP and try a \
completely different strategy.
"""


async def skill_run_python(
    *,
    bwrap_sandbox: bs_sandbox.BwrapSandbox,
    script: str,
    environment_name: str = None,
    workdir: pathlib.Path | None = None,
    timeout: float = None,  # seconds
    extra_volumes: bs_models.VolumeMap = None,
) -> str:
    """Execute a python script in the working directory.

    Args:
        script: Python script to execute.
        environment_name: name of sandbox environment (defaults to 'bare')
        workdir: path on host system to mount as the working directory
        timeout: Maximum execution time in seconds. Defaults to the value
            in the 'buuble_sandbox.config.Config' used to construct
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
    except RuntimeError as e:
        return f"Error: {e}"

    output = result.output
    if result.truncated:
        output += "\n\n... (output truncated)"

    if result.exit_code is not None and result.exit_code != 0:
        return f"Command failed (exit code {result.exit_code}):\n{output}"

    return str(output)


def get_workdir(
    workdirs_path: pathlib.Path | None,
    room_id: str,
    thread_id: str,
    run_id: str,
):
    if workdirs_path is not None:
        workdir = workdirs_path / room_id / str(thread_id) / str(run_id)
        workdir.mkdir(parents=True, exist_ok=True)
    else:
        workdir = None

    return workdir


def get_extra_volumes(
    rooms_upload_path: pathlib.Path | None,
    threads_upload_path: pathlib.Path | None,
    room_id: str,
    thread_id: str,
):
    result = {}

    if rooms_upload_path is not None:
        room_dir = rooms_upload_path / room_id
        if room_dir.exists():
            result["room"] = bs_models.VolumeInfo(
                host_path=room_dir,
                writable=False,
            )
        else:
            result["room"] = bs_models.VolumeInfo(
                host_path=None,
                writable=False,
            )

    if threads_upload_path is not None:
        thread_dir = threads_upload_path / str(thread_id)
        if thread_dir.exists():
            result["thread"] = bs_models.VolumeInfo(
                host_path=thread_dir,
                writable=False,
            )
        else:
            result["thread"] = bs_models.VolumeInfo(
                host_path=None,
                writable=False,
            )

    return result


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
        FunctionToolset with thses tools:
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
    else:
        workdirs_path = None
        threads_upload_path = None
        rooms_upload_path = None

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
    ) -> list[EnvironmentInfo]:
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
            state = ctx.deps.state
            room_id = state.room_id or ""
            thread_id = state.thread_id or ""

            return await skill_list_volume_files(
                volume=volume,
                room_upload_path=rooms_upload_path / room_id,
                thread_upload_path=threads_upload_path / thread_id,
            )

    @toolset.tool(description=RUN_DESCRIPTION)
    async def run(
        ctx: pydantic_ai.RunContext,
        command: str | list[str],
        environment_name: str = None,
        timeout: float = None,  # seconds
    ) -> str:
        state = ctx.deps.state
        workdir = get_workdir(
            workdirs_path,
            state.room_id or "",
            state.thread_id or "",
            state.run_id or "",
        )

        extra_volumes = get_extra_volumes(
            rooms_upload_path,
            threads_upload_path,
            state.room_id or "",
            state.thread_id or "",
        )

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
        environment_name: str = None,
        timeout: float = None,  # seconds
    ) -> str:
        state = ctx.deps.state
        workdir = get_workdir(
            workdirs_path,
            state.room_id or "",
            state.thread_id or "",
            state.run_id or "",
        )

        extra_volumes = get_extra_volumes(
            rooms_upload_path,
            threads_upload_path,
            state.room_id or "",
            state.thread_id or "",
        )

        return await skill_run_python(
            bwrap_sandbox=bwrap_sandbox,
            script=script,
            environment_name=environment_name,
            workdir=workdir,
            timeout=timeout,
            extra_volumes=extra_volumes,
        )

    return toolset


def create_bwrap_sandbox_skill(
    id: str = None,
    *,
    default_environment: str = "bare",
    allowed_environments: AllowedEnvironments = None,
    sandbox_config: bs_config.Config | None = None,
    volumes: bs_models.VolumeMap | None = None,
    max_retries: int = 1,
    installation_config=None,  # noqa F821 cycles
) -> hs_models.Skill:

    skill_path = pathlib.Path(__file__).parent
    skill_md_path = skill_path / "SKILL.md"
    metadata, instructions = hs_parser.parse_skill_md(skill_md_path)

    toolset = create_sandbox_toolset(
        id=id,
        default_environment=default_environment,
        allowed_environments=allowed_environments,
        sandbox_config=sandbox_config,
        volumes=volumes,
        max_retries=max_retries,
        installation_config=installation_config,
    )

    return hs_models.Skill(
        metadata=metadata,
        instructions=instructions,
        path=skill_path,
        toolsets=[toolset],
        state_type=STATE_TYPE,
        state_namespace=STATE_NAMESPACE,
        deps_type=hs_state.SkillRunDeps,
    )
