import contextlib
import json
import os
import pathlib
import uuid
from unittest import mock

import pydantic_ai
import pytest
from bubble_sandbox import config as bs_config
from bubble_sandbox import models as bs_models
from bubble_sandbox import sandbox as bs_sandbox
from pydantic_ai import toolsets as ai_toolsets

from soliplex import loggers
from soliplex.config import installation as config_installation
from soliplex.skills import bwrap_sandbox as skills_bwrap_sandbox

ROOM_ID = "test_room"
THREAD_ID = uuid.uuid4()
THREAD_ID_STR = str(THREAD_ID)
RUN_ID = uuid.uuid4()
RUN_ID_STR = str(RUN_ID)
USERNAME = "phreddy"
SANDBOX_VOLUMES_PATH = skills_bwrap_sandbox.SANDBOX_VOLUMES_PATH
SANDBOX_WORKDIR_PATH = skills_bwrap_sandbox.SANDBOX_WORKDIR_PATH

# 'write_transcript' requests owner-only '0600', which every POSIX host
# honours -- Linux and macOS (APFS / HFS+) alike, as 'os.name' is 'posix'
# on both ('sys.platform' is what distinguishes 'darwin'). Windows is the
# lone exception: it has no POSIX mode bits, and 'os.chmod' there only
# toggles the read-only flag, so a writable file reports '0666' however
# it was chmod'ed.
EXPECTED_TRANSCRIPT_MODE = 0o666 if os.name == "nt" else 0o600

ONE_ENVIRONMENT = mock.create_autospec(bs_models.EnvironmentInfo)
ONE_ENVIRONMENT.name = "one"  # mock quirk

ANOTHER_ENVIRONMENT = mock.create_autospec(bs_models.EnvironmentInfo)
ANOTHER_ENVIRONMENT.name = "another"  # mock quirk

ALL_ENVIRONMENTS = [ONE_ENVIRONMENT, ANOTHER_ENVIRONMENT]

# 'bubble_sandbox' signals a bad environment name with a 'ValueError' or a
# 'FileNotFoundError' subclass rather than a 'RuntimeError'. Each must come
# back as an error string the model can act on: one escaping the tool aborts
# the whole agent run (soliplex#1306).
EXECUTION_ERROR_CASES = [
    (
        bs_config.EnvironmentNotFound(pathlib.Path("/environments/pandas")),
        skills_bwrap_sandbox.EnvironmentMissing,
    ),
    (
        bs_config.EnvironmentNotInitialized(
            "one", pathlib.Path("/environments/one/.venv/bin/python")
        ),
        skills_bwrap_sandbox.EnvironmentNotBuilt,
    ),
    (
        bs_config.InvalidEnvironmentName("../escape"),
        skills_bwrap_sandbox.EnvironmentNameInvalid,
    ),
    (RuntimeError("test"), skills_bwrap_sandbox.SandboxUnavailable),
]


@pytest.fixture
def ctx_w_deps():
    ctx = mock.Mock(spec_set=["deps"])
    user = mock.Mock()
    user.model_dump.return_value = {"preferred_username": USERNAME}
    ctx.deps = mock.Mock(
        spec_set=["room_id", "thread_id", "run_id", "user"],
        room_id=ROOM_ID,
        thread_id=THREAD_ID_STR,
        run_id=RUN_ID_STR,
        user=user,
    )
    return ctx


@pytest.fixture
def bwrap_sandbox(temp_dir):
    config = mock.create_autospec(
        bs_config.Config,
        environments_path=temp_dir,
    )
    return mock.create_autospec(bs_sandbox.BwrapSandbox, config=config)


@pytest.fixture
def workdirs_path(temp_dir):
    result = temp_dir / "sandbox" / "workdirs"
    result.mkdir(parents=True)
    return result


@pytest.fixture
def environments_path(temp_dir):
    result = temp_dir / "sandbox" / "environments"
    result.mkdir(parents=True)
    return result


@pytest.fixture
def transcripts_path(temp_dir):
    result = temp_dir / "sandbox" / "transcripts"
    result.mkdir(parents=True)
    return result


@pytest.fixture
def s_config(
    workdirs_path,
    environments_path,
    transcripts_path,
):
    return mock.create_autospec(
        config_installation.SandboxConfig,
        environments_path=environments_path,
        workdirs_path=workdirs_path,
        transcripts_path=transcripts_path,
    )


@pytest.fixture
def rooms_upload_path(temp_dir):
    result = temp_dir / "uploads" / "rooms"
    result.mkdir(parents=True)
    return result


@pytest.fixture
def threads_upload_path(temp_dir):
    result = temp_dir / "uploads" / "threads"
    result.mkdir(parents=True)
    return result


@pytest.fixture
def i_config(
    s_config,
    rooms_upload_path,
    threads_upload_path,
):
    return mock.create_autospec(
        config_installation.InstallationConfig,
        sandbox_config=s_config,
        rooms_upload_path=rooms_upload_path,
        threads_upload_path=threads_upload_path,
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "kwargs, expected",
    [
        ({}, ALL_ENVIRONMENTS),
        ({"allowed_environments": ["one"]}, [ONE_ENVIRONMENT]),
    ],
)
async def test_skill_list_environments(
    bwrap_sandbox,
    kwargs,
    expected,
):
    bwrap_sandbox.config.list_environments.return_value = ALL_ENVIRONMENTS

    found = await skills_bwrap_sandbox.skill_list_environments(
        bwrap_sandbox=bwrap_sandbox,
        **kwargs,
    )

    assert found == expected


@pytest.mark.anyio
@pytest.mark.parametrize(
    "w_environments, w_name, w_allowed",
    [
        (ALL_ENVIRONMENTS, None, None),
        (ALL_ENVIRONMENTS, "one", None),
        (ALL_ENVIRONMENTS, "one", ["one"]),
    ],
)
async def test_check_environment_name_w_usable_name(
    bwrap_sandbox,
    w_environments,
    w_name,
    w_allowed,
):
    bwrap_sandbox.config.list_environments.return_value = w_environments

    found = await skills_bwrap_sandbox.check_environment_name(
        bwrap_sandbox=bwrap_sandbox,
        environment_name=w_name,
        allowed_environments=w_allowed,
    )

    assert found is None


@pytest.mark.anyio
@pytest.mark.parametrize(
    "w_name, w_allowed, exp_choices",
    [
        # A name the room does not allow is refused even though it exists:
        # 'allowed_environments' otherwise only filters 'list_environments'.
        ("another", ["one"], ["one"]),
        ("pandas", None, ["one", "another"]),
    ],
)
async def test_check_environment_name_w_guessed_name(
    bwrap_sandbox,
    w_name,
    w_allowed,
    exp_choices,
):
    bwrap_sandbox.config.list_environments.return_value = ALL_ENVIRONMENTS

    with pytest.raises(pydantic_ai.ModelRetry) as exc_info:
        await skills_bwrap_sandbox.check_environment_name(
            bwrap_sandbox=bwrap_sandbox,
            environment_name=w_name,
            allowed_environments=w_allowed,
        )

    assert isinstance(exc_info.value, skills_bwrap_sandbox.UnknownEnvironment)
    assert exc_info.value.name == w_name
    assert exc_info.value.choices == exp_choices


@pytest.mark.anyio
async def test_check_environment_name_wo_any_environment(bwrap_sandbox):
    bwrap_sandbox.config.list_environments.return_value = []

    with pytest.raises(pydantic_ai.ToolFailed) as exc_info:
        await skills_bwrap_sandbox.check_environment_name(
            bwrap_sandbox=bwrap_sandbox,
            environment_name="pandas",
            allowed_environments=None,
        )

    assert isinstance(
        exc_info.value,
        skills_bwrap_sandbox.NoEnvironmentsConfigured,
    )
    assert exc_info.value.name == "pandas"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "volume, expected",
    [
        ("thread", [f"{SANDBOX_VOLUMES_PATH}/thread/thread_file.txt"]),
        ("room", [f"{SANDBOX_VOLUMES_PATH}/room/room_file.txt"]),
        ("nonesuch", []),
    ],
)
async def test_skill_list_volume_files(
    temp_dir,
    rooms_upload_path,
    threads_upload_path,
    bwrap_sandbox,
    volume,
    expected,
):
    room_upload_path = rooms_upload_path / str(ROOM_ID)
    room_upload_path.mkdir(parents=True)
    room_file = room_upload_path / "room_file.txt"
    room_file.write_text("ROOM FILE")

    thread_upload_path = threads_upload_path / THREAD_ID_STR
    thread_upload_path.mkdir(parents=True)
    thread_file = thread_upload_path / "thread_file.txt"
    thread_file.write_text("THREAD FILE")

    found = await skills_bwrap_sandbox.skill_list_volume_files(
        volume=volume,
        room_upload_path=room_upload_path,
        thread_upload_path=thread_upload_path,
    )

    assert found == expected


@pytest.mark.anyio
@pytest.mark.parametrize("volume", ["room", "thread"])
async def test_skill_list_volume_files_wo_configured_path(volume):
    found = await skills_bwrap_sandbox.skill_list_volume_files(
        volume=volume,
        room_upload_path=None,
        thread_upload_path=None,
    )

    assert found == []


@pytest.mark.asyncio
@pytest.mark.parametrize("w_exit_code", [0, None, 42])
@pytest.mark.parametrize("w_truncated", [False, True])
@pytest.mark.parametrize(
    "w_command, exp_cmd_args",
    [
        ("echo 'foo'", ["sh", "-c", "echo 'foo'"]),
        (["/bin/true"], ["/bin/true"]),
    ],
)
async def test_skill_run_w_exit_code_truncation(
    ctx_w_deps,
    bwrap_sandbox,
    w_command,
    exp_cmd_args,
    w_truncated,
    w_exit_code,
):
    bwrap_sandbox.execute.return_value = mock.create_autospec(
        bs_models.ExecuteResult,
        output="test output",
        exit_code=w_exit_code,
        truncated=w_truncated,
    )
    if w_truncated:
        expected = "test output\n\n... (output truncated)"
    else:
        expected = "test output"

    if w_exit_code not in [None, 0]:
        expected = f"Command failed (exit code {w_exit_code}):\n{expected}"

    found = await skills_bwrap_sandbox.skill_run(
        bwrap_sandbox=bwrap_sandbox,
        command=w_command,
    )

    assert found == expected

    bwrap_sandbox.execute.assert_awaited_once_with(
        command=exp_cmd_args,
        environment_name=None,
        workdir=None,
        timeout=None,
        extra_volumes=None,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("w_error, exp_klass", EXECUTION_ERROR_CASES)
async def test_skill_run_w_execution_error(
    bwrap_sandbox,
    w_error,
    exp_klass,
):
    bwrap_sandbox.execute.side_effect = w_error

    with pytest.raises(exp_klass) as exc_info:
        await skills_bwrap_sandbox.skill_run(
            bwrap_sandbox=bwrap_sandbox,
            command=["/bin/true"],
            environment_name="one",
        )

    assert exc_info.value.__cause__ is w_error
    assert exc_info.value.environment_name == "one"
    # The host path 'bubble_sandbox' reports must not reach the model.
    assert "/environments/" not in exc_info.value.message


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "w_kw",
    [
        {"environment_name": "test-environment"},
        {"workdir": "/tmp/foo"},
        {"timeout": 17},
        {
            "extra_volumes": {
                "test-volume": bs_models.VolumeInfo(
                    host_path="/tmp/bar",
                    writable=True,
                ),
            },
        },
    ],
)
@pytest.mark.parametrize(
    "w_command, exp_cmd_args",
    [
        ("echo 'foo'", ["sh", "-c", "echo 'foo'"]),
        (["/bin/true"], ["/bin/true"]),
    ],
)
async def test_skill_run_w_extra_args(
    ctx_w_deps,
    bwrap_sandbox,
    w_command,
    exp_cmd_args,
    w_kw,
):
    bwrap_sandbox.execute.return_value = mock.create_autospec(
        bs_models.ExecuteResult,
        output="test output",
        exit_code=None,
        truncated=False,
    )
    expected = "test output"

    found = await skills_bwrap_sandbox.skill_run(
        bwrap_sandbox=bwrap_sandbox,
        command=w_command,
        **w_kw,
    )

    assert found == expected

    exp_kw = {
        "environment_name": None,
        "workdir": None,
        "timeout": None,
        "extra_volumes": None,
    } | w_kw

    bwrap_sandbox.execute.assert_awaited_once_with(
        command=exp_cmd_args,
        **exp_kw,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("w_exit_code", [0, None, 42])
@pytest.mark.parametrize("w_truncated", [False, True])
async def test_skill_run_python_w_exit_code_truncation(
    ctx_w_deps,
    bwrap_sandbox,
    w_truncated,
    w_exit_code,
):
    bwrap_sandbox.execute_python.return_value = mock.create_autospec(
        bs_models.ExecuteResult,
        output="test output",
        exit_code=w_exit_code,
        truncated=w_truncated,
    )
    if w_truncated:
        expected = "test output\n\n... (output truncated)"
    else:
        expected = "test output"

    if w_exit_code not in [None, 0]:
        expected = f"Command failed (exit code {w_exit_code}):\n{expected}"

    found = await skills_bwrap_sandbox.skill_run_python(
        bwrap_sandbox=bwrap_sandbox,
        script="print('hello')",
    )

    assert found == expected

    bwrap_sandbox.execute_python.assert_awaited_once_with(
        script="print('hello')",
        environment_name=None,
        workdir=None,
        timeout=None,
        extra_volumes=None,
    )


@pytest.mark.asyncio
async def test_skill_run_w_execution_error_wo_environment_name(
    bwrap_sandbox,
):
    # The room's configured default is the operator's choice, so the model
    # is told which environment failed without being handed a name it never
    # passed -- nor the host path 'bubble_sandbox' names.
    bwrap_sandbox.execute.side_effect = bs_config.EnvironmentNotFound(
        pathlib.Path("/environments/bare")
    )

    with pytest.raises(skills_bwrap_sandbox.EnvironmentMissing) as exc_info:
        await skills_bwrap_sandbox.skill_run(
            bwrap_sandbox=bwrap_sandbox,
            command=["/bin/true"],
        )

    assert exc_info.value.environment_name is None
    assert "this room uses by default" in exc_info.value.message
    assert "/environments/" not in exc_info.value.message


@pytest.mark.asyncio
@pytest.mark.parametrize("w_error, exp_klass", EXECUTION_ERROR_CASES)
async def test_skill_run_python_w_execution_error(
    bwrap_sandbox,
    w_error,
    exp_klass,
):
    bwrap_sandbox.execute_python.side_effect = w_error

    with pytest.raises(exp_klass) as exc_info:
        await skills_bwrap_sandbox.skill_run_python(
            bwrap_sandbox=bwrap_sandbox,
            script="print('hello')",
            environment_name="one",
        )

    assert exc_info.value.__cause__ is w_error
    assert exc_info.value.environment_name == "one"
    # The host path 'bubble_sandbox' reports must not reach the model.
    assert "/environments/" not in exc_info.value.message


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "w_kw",
    [
        {"environment_name": "test-environment"},
        {"workdir": "/tmp/foo"},
        {"timeout": 17},
        {
            "extra_volumes": {
                "test-volume": bs_models.VolumeInfo(
                    host_path="/tmp/bar",
                    writable=True,
                ),
            },
        },
    ],
)
async def test_skill_run_python_w_extra_args(
    ctx_w_deps,
    bwrap_sandbox,
    w_kw,
):
    bwrap_sandbox.execute_python.return_value = mock.create_autospec(
        bs_models.ExecuteResult,
        output="test output",
        exit_code=None,
        truncated=False,
    )
    expected = "test output"

    found = await skills_bwrap_sandbox.skill_run_python(
        bwrap_sandbox=bwrap_sandbox,
        script="print('hello')",
        **w_kw,
    )

    assert found == expected

    exp_kw = {
        "environment_name": None,
        "workdir": None,
        "timeout": None,
        "extra_volumes": None,
    } | w_kw

    bwrap_sandbox.execute_python.assert_awaited_once_with(
        script="print('hello')",
        **exp_kw,
    )


no_raise = contextlib.nullcontext()
invalid_subdir = pytest.raises(skills_bwrap_sandbox.InvalidSubdir)


@pytest.mark.parametrize(
    "subpath, expectation",
    [
        ("foo", no_raise),
        ("\x00", invalid_subdir),
        ("/", invalid_subdir),
        (".", invalid_subdir),
        ("..", invalid_subdir),
        ("foo/..", invalid_subdir),
        ("foo/bar", invalid_subdir),
        ("foo/./bar", invalid_subdir),
        ("../foo", invalid_subdir),
        ("", invalid_subdir),
        ("/tmp/foo", invalid_subdir),
    ],
)
def test__check_is_subdir(temp_dir, subpath, expectation):
    with expectation:
        skills_bwrap_sandbox._check_is_subdir(temp_dir / subpath, temp_dir)


@pytest.mark.parametrize(
    "paths, expectation",
    [
        ([], no_raise),
        (["foo"], no_raise),
        (["foo", "bar"], no_raise),
        (["../foo", "bar"], invalid_subdir),
        (["foo", "../bar"], invalid_subdir),
    ],
)
def test__check_subdirs(temp_dir, paths, expectation):
    with expectation as exc:
        found = skills_bwrap_sandbox._check_subdirs(temp_dir, paths)

    if not isinstance(exc, pytest.ExceptionInfo):
        expected = temp_dir
        for path in paths:
            expected /= path

        assert found == expected


@pytest.mark.parametrize(
    "w_wd_path, w_room_id, w_thread_id, w_run_id, exp_path",
    [
        (False, True, True, True, False),
        (True, False, True, True, False),
        (True, True, False, True, False),
        (True, True, True, False, False),
        (True, True, True, True, True),
    ],
)
def test_get_workdir(
    workdirs_path,
    w_wd_path,
    w_room_id,
    w_thread_id,
    w_run_id,
    exp_path,
):
    if w_wd_path:
        wd_path = workdirs_path
    else:
        wd_path = None

    if exp_path:
        expected = workdirs_path / ROOM_ID / THREAD_ID_STR / RUN_ID_STR
    else:
        expected = None

    found = skills_bwrap_sandbox.get_workdir(
        wd_path,
        ROOM_ID if w_room_id else None,
        THREAD_ID_STR if w_thread_id else None,
        RUN_ID_STR if w_run_id else None,
    )

    assert found == expected

    if expected is not None:
        assert expected.is_dir()


@pytest.mark.parametrize(
    "w_upload_path, w_volume_id, w_exists, exp_hp",
    [
        (False, False, None, None),
        (True, False, None, None),
        (False, True, None, None),
        (True, True, False, False),
        (True, True, True, True),
    ],
)
def test__get_upload_volume(
    temp_dir,
    w_upload_path,
    w_volume_id,
    w_exists,
    exp_hp,
):

    if w_upload_path:
        upload_path = temp_dir
    else:
        upload_path = None

    if w_volume_id:
        volume_id = "test-vol"
    else:
        volume_id = None

    exp_vol_info = w_upload_path and w_volume_id

    if exp_vol_info:
        v_path = upload_path / volume_id

        if w_exists:
            v_path.mkdir()

    found = skills_bwrap_sandbox._get_upload_volume(upload_path, volume_id)

    if exp_vol_info:
        assert isinstance(found, bs_models.VolumeInfo)
        assert not (found.writable)

        if exp_hp:
            assert found.host_path == v_path
        else:
            assert found.host_path is None

    else:
        assert found is None


@pytest.mark.parametrize("w_thread_volume", [False, True])
@pytest.mark.parametrize("w_room_volume", [False, True])
@mock.patch("soliplex.skills.bwrap_sandbox._get_upload_volume")
def test_get_extra_volumes(
    _guv,
    rooms_upload_path,
    threads_upload_path,
    w_room_volume,
    w_thread_volume,
):
    expected = {}
    vols = []
    room_volume = mock.Mock(spec_set=())
    thread_volume = mock.Mock(spec_set=())

    if w_room_volume:
        expected["room"] = room_volume
        vols.append(room_volume)
    else:
        vols.append(None)

    if w_thread_volume:
        expected["thread"] = thread_volume
        vols.append(thread_volume)
    else:
        vols.append(None)

    _guv.side_effect = vols

    found = skills_bwrap_sandbox.get_extra_volumes(
        rooms_upload_path,
        threads_upload_path,
        ROOM_ID,
        THREAD_ID,
    )

    assert found == expected

    room_call, thread_call = _guv.call_args_list

    assert room_call == mock.call(rooms_upload_path, ROOM_ID)
    assert thread_call == mock.call(threads_upload_path, str(THREAD_ID))


@pytest.mark.parametrize(
    "w_tx_path, w_room_id, w_thread_id, w_run_id",
    [
        (False, True, True, True),
        (True, False, True, True),
        (True, True, False, True),
        (True, True, True, False),
    ],
)
def test_write_transcript_wo_transcripts_path(
    transcripts_path,
    w_tx_path,
    w_room_id,
    w_thread_id,
    w_run_id,
):
    found = skills_bwrap_sandbox.write_transcript(
        transcripts_path if w_tx_path else None,
        ROOM_ID if w_room_id else None,
        THREAD_ID_STR if w_thread_id else None,
        RUN_ID_STR if w_run_id else None,
        content="print('hi')",
        suffix=".py",
    )

    assert found is None


@pytest.mark.parametrize(
    "content, suffix",
    [
        ("print('hi')", ".py"),
        ('["/bin/true"]', ".txt"),
    ],
)
def test_write_transcript(transcripts_path, content, suffix):
    found = skills_bwrap_sandbox.write_transcript(
        transcripts_path,
        ROOM_ID,
        THREAD_ID_STR,
        RUN_ID_STR,
        content=content,
        suffix=suffix,
    )

    found_path = pathlib.Path(found)
    assert found_path.parent == (
        transcripts_path / ROOM_ID / THREAD_ID_STR / RUN_ID_STR
    )
    assert found_path.suffix == suffix
    assert found_path.read_text(encoding="utf-8") == content
    assert (found_path.stat().st_mode & 0o777) == EXPECTED_TRANSCRIPT_MODE


@pytest.mark.parametrize("w_iconfig", [False, True])
@pytest.mark.parametrize(
    "w_kwargs",
    [
        {},
        {"id": "test-toolset-id"},
        {"max_retries": 17},
        {"default_environment": "test-environment"},
        {"sandbox_config": bs_config.Config(max_output_chars=100)},
        {
            "volumes": {
                "test-volume": bs_models.VolumeInfo(
                    host_path="/tmp/bar",
                    writable=True,
                ),
            },
        },
        {"allowed_environments": ["one"]},
    ],
)
@mock.patch("bubble_sandbox.sandbox.BwrapSandbox")
def test_create_sandbox_toolset(
    bs_klass,
    i_config,
    environments_path,
    w_kwargs,
    w_iconfig,
):

    if w_iconfig:
        iconfig_kwargs = {"installation_config": i_config}
    else:
        iconfig_kwargs = {}

    found = skills_bwrap_sandbox.create_sandbox_toolset(
        **w_kwargs,
        **iconfig_kwargs,
    )

    assert isinstance(found, ai_toolsets.FunctionToolset)
    assert found.id == w_kwargs.pop("id", None)
    assert found.max_retries == w_kwargs.pop("max_retries", 1)

    sandbox_config = w_kwargs.pop("sandbox_config", bs_config.Config())
    if w_iconfig:
        exp_config = sandbox_config.model_copy(
            update={"environments_pathname": environments_path}
        )
    else:
        exp_config = sandbox_config

    exp_sandbox_kw = {
        "default_environment": "bare",
        "config": exp_config,
        "volumes": {},
    } | {
        key: value
        for key, value in w_kwargs.items()
        if key != "allowed_environments"
    }

    bs_klass.assert_called_once_with(**exp_sandbox_kw)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "w_kwargs, exp_allowed_environments",
    [
        ({}, None),
        ({"allowed_environments": ["one"]}, ["one"]),
    ],
)
@mock.patch("soliplex.skills.bwrap_sandbox.skill_list_environments")
@mock.patch("bubble_sandbox.sandbox.BwrapSandbox")
async def test_create_sandbox_toolset_list_environments(
    bs_klass,
    skill_list_environments,
    ctx_w_deps,
    w_kwargs,
    exp_allowed_environments,
):
    toolset = skills_bwrap_sandbox.create_sandbox_toolset(**w_kwargs)
    sandbox = bs_klass.return_value
    tool = toolset.tools["list_environments"]

    found = await tool.function(ctx=ctx_w_deps)

    assert found is skill_list_environments.return_value
    skill_list_environments.assert_called_once_with(
        bwrap_sandbox=sandbox,
        allowed_environments=exp_allowed_environments,
    )


@pytest.mark.anyio
@pytest.mark.parametrize("w_iconfig", [False, True])
@mock.patch("soliplex.skills.bwrap_sandbox.skill_list_volume_files")
async def test_create_sandbox_toolset_list_volume_files(
    skill_list_volume_files,
    i_config,
    ctx_w_deps,
    rooms_upload_path,
    threads_upload_path,
    w_iconfig,
):
    if w_iconfig:
        toolset = skills_bwrap_sandbox.create_sandbox_toolset(
            installation_config=i_config,
        )
    else:
        toolset = skills_bwrap_sandbox.create_sandbox_toolset()

    tool = toolset.tools["list_volume_files"]

    found = await tool.function(ctx=ctx_w_deps, volume="foo")

    if w_iconfig:
        assert found is skill_list_volume_files.return_value
        skill_list_volume_files.assert_called_once_with(
            volume="foo",
            room_upload_path=rooms_upload_path / str(ROOM_ID),
            thread_upload_path=threads_upload_path / THREAD_ID_STR,
        )
    else:
        assert found == []


@pytest.mark.anyio
@mock.patch("soliplex.skills.bwrap_sandbox.skill_list_volume_files")
async def test_create_sandbox_toolset_list_volume_files_wo_upload_paths(
    skill_list_volume_files,
    s_config,
    ctx_w_deps,
):
    i_config = mock.create_autospec(
        config_installation.InstallationConfig,
        sandbox_config=s_config,
        rooms_upload_path=None,
        threads_upload_path=None,
    )
    toolset = skills_bwrap_sandbox.create_sandbox_toolset(
        installation_config=i_config,
    )
    tool = toolset.tools["list_volume_files"]

    found = await tool.function(ctx=ctx_w_deps, volume="foo")

    assert found is skill_list_volume_files.return_value
    skill_list_volume_files.assert_called_once_with(
        volume="foo",
        room_upload_path=None,
        thread_upload_path=None,
    )


@pytest.mark.anyio
@pytest.mark.parametrize("w_iconfig", [False, True])
@pytest.mark.parametrize(
    "w_kw",
    [
        {},
        {"environment_name": "one"},
        {"timeout": 17},
    ],
)
@mock.patch("soliplex.skills.bwrap_sandbox.get_extra_volumes")
@mock.patch("soliplex.skills.bwrap_sandbox.get_workdir")
@mock.patch("soliplex.skills.bwrap_sandbox.skill_run")
@mock.patch("bubble_sandbox.sandbox.BwrapSandbox")
async def test_create_sandbox_toolset_run(
    bs_klass,
    skill_run,
    gw,
    gev,
    ctx_w_deps,
    i_config,
    workdirs_path,
    rooms_upload_path,
    threads_upload_path,
    transcripts_path,
    w_kw,
    w_iconfig,
    audit_records,
):
    bs_klass.return_value.config.list_environments.return_value = (
        ALL_ENVIRONMENTS
    )
    if w_iconfig:
        toolset = skills_bwrap_sandbox.create_sandbox_toolset(
            installation_config=i_config,
        )
    else:
        toolset = skills_bwrap_sandbox.create_sandbox_toolset()

    sandbox = bs_klass.return_value
    tool = toolset.tools["run"]

    found = await tool.function(
        ctx=ctx_w_deps,
        command=["/bin/true"],
        **w_kw,
    )

    assert found is skill_run.return_value

    exp_kw = {
        "environment_name": None,
        "timeout": None,
        "workdir": gw.return_value,
        "extra_volumes": gev.return_value,
    } | w_kw

    skill_run.assert_called_once_with(
        bwrap_sandbox=sandbox,
        command=["/bin/true"],
        **exp_kw,
    )

    record = audit_records[-1]
    assert record.action == loggers.AUDIT_SANDBOX_ACTION_RUN
    assert record.outcome == loggers.AUDIT_OUTCOME_SUCCESS
    assert record.workdir == str(gw.return_value)
    assert record.environment == w_kw.get("environment_name")
    assert record.claims == {"preferred_username": USERNAME}
    assert record.room_id == ROOM_ID
    assert record.thread_id == THREAD_ID_STR
    assert record.run_id == RUN_ID_STR

    if w_iconfig:
        (ref,) = record.refs
        ref_path = pathlib.Path(ref)
        assert ref_path.parent == (
            transcripts_path / ROOM_ID / THREAD_ID_STR / RUN_ID_STR
        )
        assert ref_path.suffix == ".txt"
        assert ref_path.read_text(encoding="utf-8") == json.dumps(
            ["/bin/true"]
        )
    else:
        assert record.refs == []

    if w_iconfig:
        gw.assert_called_once_with(
            workdirs_path,
            ROOM_ID,
            THREAD_ID_STR,
            RUN_ID_STR,
        )
        gev.assert_called_once_with(
            rooms_upload_path,
            threads_upload_path,
            ROOM_ID,
            THREAD_ID_STR,
        )
    else:
        gw.assert_called_once_with(
            None,
            ROOM_ID,
            THREAD_ID_STR,
            RUN_ID_STR,
        )
        gev.assert_called_once_with(
            None,
            None,
            ROOM_ID,
            THREAD_ID_STR,
        )


@pytest.mark.anyio
@pytest.mark.parametrize("w_iconfig", [False, True])
@pytest.mark.parametrize(
    "w_kw",
    [
        {},
        {"environment_name": "one"},
        {"timeout": 17},
    ],
)
@mock.patch("soliplex.skills.bwrap_sandbox.get_extra_volumes")
@mock.patch("soliplex.skills.bwrap_sandbox.get_workdir")
@mock.patch("soliplex.skills.bwrap_sandbox.skill_run_python")
@mock.patch("bubble_sandbox.sandbox.BwrapSandbox")
async def test_create_sandbox_toolset_run_python(
    bs_klass,
    skill_run_python,
    gw,
    gev,
    ctx_w_deps,
    i_config,
    workdirs_path,
    rooms_upload_path,
    threads_upload_path,
    transcripts_path,
    w_kw,
    w_iconfig,
    audit_records,
):
    bs_klass.return_value.config.list_environments.return_value = (
        ALL_ENVIRONMENTS
    )
    if w_iconfig:
        toolset = skills_bwrap_sandbox.create_sandbox_toolset(
            installation_config=i_config,
        )
    else:
        toolset = skills_bwrap_sandbox.create_sandbox_toolset()

    sandbox = bs_klass.return_value
    tool = toolset.tools["run_python"]

    found = await tool.function(
        ctx=ctx_w_deps,
        script="print('hello')",
        **w_kw,
    )

    assert found is skill_run_python.return_value

    exp_kw = {
        "environment_name": None,
        "timeout": None,
        "workdir": gw.return_value,
        "extra_volumes": gev.return_value,
    } | w_kw

    skill_run_python.assert_called_once_with(
        bwrap_sandbox=sandbox,
        script="print('hello')",
        **exp_kw,
    )

    record = audit_records[-1]
    assert record.action == loggers.AUDIT_SANDBOX_ACTION_RUN_PYTHON
    assert record.outcome == loggers.AUDIT_OUTCOME_SUCCESS
    assert record.workdir == str(gw.return_value)
    assert record.environment == w_kw.get("environment_name")
    assert record.claims == {"preferred_username": USERNAME}

    if w_iconfig:
        (ref,) = record.refs
        ref_path = pathlib.Path(ref)
        assert ref_path.parent == (
            transcripts_path / ROOM_ID / THREAD_ID_STR / RUN_ID_STR
        )
        assert ref_path.suffix == ".py"
        assert ref_path.read_text(encoding="utf-8") == "print('hello')"
    else:
        assert record.refs == []

    if w_iconfig:
        gw.assert_called_once_with(
            workdirs_path,
            ROOM_ID,
            THREAD_ID_STR,
            RUN_ID_STR,
        )
        gev.assert_called_once_with(
            rooms_upload_path,
            threads_upload_path,
            ROOM_ID,
            THREAD_ID_STR,
        )
    else:
        gw.assert_called_once_with(
            None,
            ROOM_ID,
            THREAD_ID_STR,
            RUN_ID_STR,
        )
        gev.assert_called_once_with(
            None,
            None,
            ROOM_ID,
            THREAD_ID_STR,
        )


@pytest.mark.anyio
@mock.patch("soliplex.skills.bwrap_sandbox.skill_run")
@mock.patch("bubble_sandbox.sandbox.BwrapSandbox")
async def test_create_sandbox_toolset_run_w_disallowed_environment(
    bs_klass,
    skill_run,
    ctx_w_deps,
    audit_records,
):
    bs_klass.return_value.config.list_environments.return_value = (
        ALL_ENVIRONMENTS
    )
    toolset = skills_bwrap_sandbox.create_sandbox_toolset(
        allowed_environments=["one"],
    )
    tool = toolset.tools["run"]

    with pytest.raises(pydantic_ai.ModelRetry) as exc_info:
        await tool.function(
            ctx=ctx_w_deps,
            command=["/bin/true"],
            environment_name="another",
        )

    assert isinstance(exc_info.value, skills_bwrap_sandbox.UnknownEnvironment)
    assert exc_info.value.name == "another"
    assert exc_info.value.choices == ["one"]

    skill_run.assert_not_called()
    assert audit_records == []


@pytest.mark.anyio
@mock.patch("soliplex.skills.bwrap_sandbox.skill_run_python")
@mock.patch("bubble_sandbox.sandbox.BwrapSandbox")
async def test_create_sandbox_toolset_run_python_w_disallowed_environment(
    bs_klass,
    skill_run_python,
    ctx_w_deps,
    audit_records,
):
    bs_klass.return_value.config.list_environments.return_value = (
        ALL_ENVIRONMENTS
    )
    toolset = skills_bwrap_sandbox.create_sandbox_toolset(
        allowed_environments=["one"],
    )
    tool = toolset.tools["run_python"]

    with pytest.raises(pydantic_ai.ModelRetry) as exc_info:
        await tool.function(
            ctx=ctx_w_deps,
            script="print('hello')",
            environment_name="another",
        )

    assert isinstance(exc_info.value, skills_bwrap_sandbox.UnknownEnvironment)
    assert exc_info.value.name == "another"
    assert exc_info.value.choices == ["one"]

    skill_run_python.assert_not_called()
    assert audit_records == []


@pytest.mark.parametrize("w_iconfig", [False, True])
@pytest.mark.parametrize(
    "w_kwargs",
    [
        {},
        {"id": "test-toolset-id"},
        {"max_retries": 17},
        {"default_environment": "test-environment"},
        {"sandbox_config": bs_config.Config(max_output_chars=100)},
        {
            "volumes": {
                "test-volume": bs_models.VolumeInfo(
                    host_path="/tmp/bar",
                    writable=True,
                ),
            },
        },
    ],
)
@mock.patch("soliplex.skills.bwrap_sandbox.create_sandbox_toolset")
def test_create_bwrap_sandbox_capability(
    csts,
    w_kwargs,
    w_iconfig,
    i_config,
):
    if w_iconfig:
        iconfig_kwargs = {"installation_config": i_config}
        exp_iconfig_args = iconfig_kwargs
    else:
        iconfig_kwargs = {}
        exp_iconfig_args = {"installation_config": None}

    capability = skills_bwrap_sandbox.create_bwrap_sandbox_capability(
        **w_kwargs,
        **iconfig_kwargs,
    )

    assert isinstance(capability, skills_bwrap_sandbox.SandboxCapability)
    assert capability.id == w_kwargs.get(
        "id", skills_bwrap_sandbox.SKILL_PROPERTIES.name
    )
    assert capability.defer_loading is False
    assert "sandbox" in capability.get_instructions().lower()
    assert capability.get_toolset() is csts.return_value

    exp_toolset_kw = (
        {
            "id": capability.id,
            "default_environment": "bare",
            "allowed_environments": None,
            "sandbox_config": None,
            "volumes": None,
            "max_retries": 1,
        }
        | w_kwargs
        | exp_iconfig_args
    )

    csts.assert_called_once_with(**exp_toolset_kw)


@pytest.mark.parametrize("w_defer_loading", [True, False])
@mock.patch("soliplex.skills.bwrap_sandbox.create_sandbox_toolset")
def test_create_bwrap_sandbox_capability_defer_loading(
    csts,
    w_defer_loading,
):
    capability = skills_bwrap_sandbox.create_bwrap_sandbox_capability(
        defer_loading=w_defer_loading,
    )

    assert capability.defer_loading is w_defer_loading


@pytest.mark.anyio
@mock.patch("soliplex.skills.bwrap_sandbox.get_extra_volumes")
@mock.patch("soliplex.skills.bwrap_sandbox.get_workdir")
@mock.patch("soliplex.skills.bwrap_sandbox.skill_run")
@mock.patch("bubble_sandbox.sandbox.BwrapSandbox")
async def test_create_sandbox_toolset_run_audits_failure(
    bs_klass,
    skill_run,
    gw,
    gev,
    ctx_w_deps,
    i_config,
    transcripts_path,
    audit_records,
):
    # An exception escaping the tool body is recorded as a failure and
    # re-raised -- which is now the live path for a sandbox that cannot
    # start, since 'skill_run' translates those into 'ToolFailed' subclasses
    # rather than swallowing them. The transcript is written before
    # execution, so its ref still lands on the failure record.
    skill_run.side_effect = RuntimeError("boom")
    toolset = skills_bwrap_sandbox.create_sandbox_toolset(
        installation_config=i_config,
    )
    tool = toolset.tools["run"]

    with pytest.raises(RuntimeError):
        await tool.function(ctx=ctx_w_deps, command=["/bin/true"])

    record = audit_records[-1]
    assert record.action == loggers.AUDIT_SANDBOX_ACTION_RUN
    assert record.outcome == loggers.AUDIT_OUTCOME_ERROR
    assert record.reason == "RuntimeError"
    assert record.workdir == str(gw.return_value)
    assert record.claims == {"preferred_username": USERNAME}

    (ref,) = record.refs
    ref_path = pathlib.Path(ref)
    assert ref_path.parent == (
        transcripts_path / ROOM_ID / THREAD_ID_STR / RUN_ID_STR
    )
    assert ref_path.read_text(encoding="utf-8") == json.dumps(["/bin/true"])
