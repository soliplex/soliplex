import base64
import contextlib
import io
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
from PIL import Image as PIL_Image
from pydantic_ai import messages as ai_messages
from pydantic_ai import toolsets as ai_toolsets

from soliplex import loggers
from soliplex.config import installation as config_installation
from soliplex.skills import bwrap_sandbox as skills_bwrap_sandbox
from tests import _platform

pytestmark = _platform.requires_posix_sandbox

ROOM_ID = "test_room"
THREAD_ID = uuid.uuid4()
THREAD_ID_STR = str(THREAD_ID)
RUN_ID = uuid.uuid4()
RUN_ID_STR = str(RUN_ID)
USERNAME = "phreddy"
SANDBOX_VOLUMES_PATH = skills_bwrap_sandbox.SANDBOX_VOLUMES_PATH
SANDBOX_WORKDIR_PATH = skills_bwrap_sandbox.SANDBOX_WORKDIR_PATH

# Windows has no POSIX mode bits: 'os.chmod' there only toggles the
# read-only flag, so a writable file reports '0666' however it was set.
EXPECTED_TRANSCRIPT_MODE = 0o666 if os.name == "nt" else 0o600

ONE_ENVIRONMENT = mock.create_autospec(bs_models.EnvironmentInfo)
ONE_ENVIRONMENT.name = "one"  # mock quirk

ANOTHER_ENVIRONMENT = mock.create_autospec(bs_models.EnvironmentInfo)
ANOTHER_ENVIRONMENT.name = "another"  # mock quirk

ALL_ENVIRONMENTS = [ONE_ENVIRONMENT, ANOTHER_ENVIRONMENT]

EXEC_OUTPUT = "test output"
EXEC_RENDERED = f"stdout:\n{EXEC_OUTPUT}"


def _execute_result(exit_code=0, output=EXEC_OUTPUT, truncated=False):
    return bs_models.ExecuteResult(
        stdout=output,
        exit_code=exit_code,
        truncated=truncated,
    )


EXECUTION_ERROR_CASES = [
    (
        bs_config.EnvironmentNotFound(pathlib.Path("/environments/pandas")),
        "not installed",
    ),
    (
        bs_config.EnvironmentNotInitialized(
            "one", pathlib.Path("/environments/one/.venv/bin/python")
        ),
        "virtualenv is missing",
    ),
    (
        bs_config.InvalidEnvironmentName("../escape"),
        "name is not usable",
    ),
    (RuntimeError("test"), "test"),
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
        sandbox_workdirs_path=s_config.workdirs_path,
        sandbox_transcripts_path=s_config.transcripts_path,
        rooms_upload_path=rooms_upload_path,
        threads_upload_path=threads_upload_path,
    )


def _result(**kwargs):
    return bs_models.ExecuteResult(**kwargs)


def test_format_execute_result_labels_each_stream():
    found = skills_bwrap_sandbox.format_execute_result(
        _result(stdout="the answer\n", stderr="a warning\n", exit_code=0)
    )

    assert "stdout:\nthe answer" in found
    assert "stderr:\na warning" in found


def test_format_execute_result_w_one_stream():
    found = skills_bwrap_sandbox.format_execute_result(
        _result(stdout="the answer\n", exit_code=0)
    )

    assert "stdout:\nthe answer" in found
    assert "stderr" not in found


def test_format_execute_result_wo_output():
    found = skills_bwrap_sandbox.format_execute_result(_result(exit_code=0))

    assert found == "The command produced no output."


@pytest.mark.parametrize("w_exit_code", [1, 127, -9])
def test_format_execute_result_w_failure(w_exit_code):
    found = skills_bwrap_sandbox.format_execute_result(
        _result(stderr="boom\n", exit_code=w_exit_code)
    )

    assert found.startswith(f"Command failed (exit code {w_exit_code}):")
    assert "boom" in found


def test_format_execute_result_w_truncation():
    found = skills_bwrap_sandbox.format_execute_result(
        _result(stdout="X" * 10, truncated=True, max_output_chars=10)
    )

    assert "10 characters" in found
    assert SANDBOX_WORKDIR_PATH in found


def test_format_execute_result_w_timeout():
    found = skills_bwrap_sandbox.format_execute_result(
        _result(timed_out=True, timeout_seconds=30.0)
    )

    assert "after 30 seconds" in found
    assert "less work" in found
    assert found != ""


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "w_command, exp_cmd_args",
    [
        ("echo 'foo'", ["sh", "-c", "echo 'foo'"]),
        (["/bin/true"], ["/bin/true"]),
    ],
)
async def test_skill_run(
    ctx_w_deps,
    bwrap_sandbox,
    w_command,
    exp_cmd_args,
):
    """The result travels up whole, so the caller can audit its status"""
    found = await skills_bwrap_sandbox.skill_run(
        bwrap_sandbox=bwrap_sandbox,
        command=w_command,
    )

    assert found is bwrap_sandbox.execute.return_value

    bwrap_sandbox.execute.assert_awaited_once_with(
        command=exp_cmd_args,
        environment_name=None,
        workdir=None,
        timeout=None,
        extra_volumes=None,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("w_error, exp_reason", EXECUTION_ERROR_CASES)
async def test_skill_run_w_execution_error(
    bwrap_sandbox,
    w_error,
    exp_reason,
):
    bwrap_sandbox.execute.side_effect = w_error

    with pytest.raises(skills_bwrap_sandbox.SandboxUnavailable) as exc_info:
        await skills_bwrap_sandbox.skill_run(
            bwrap_sandbox=bwrap_sandbox,
            command=["/bin/true"],
            environment_name="one",
        )

    assert exc_info.value.__cause__ is w_error
    assert exc_info.value.environment == "one"
    assert exp_reason in exc_info.value.message
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
    w_kw,
    ctx_w_deps,
    bwrap_sandbox,
    w_command,
    exp_cmd_args,
):
    found = await skills_bwrap_sandbox.skill_run(
        bwrap_sandbox=bwrap_sandbox,
        command=w_command,
        **w_kw,
    )

    assert found is bwrap_sandbox.execute.return_value

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
async def test_skill_run_python(ctx_w_deps, bwrap_sandbox):
    """The result travels up whole, so the caller can audit its status"""
    found = await skills_bwrap_sandbox.skill_run_python(
        bwrap_sandbox=bwrap_sandbox,
        script="print('hello')",
    )

    assert found is bwrap_sandbox.execute_python.return_value

    bwrap_sandbox.execute_python.assert_awaited_once_with(
        script="print('hello')",
        environment_name=None,
        workdir=None,
        script_path="script.py",
        timeout=None,
        extra_volumes=None,
    )


@pytest.mark.asyncio
async def test_skill_run_w_execution_error_names_environment(
    bwrap_sandbox,
):
    # The model is told which environment failed, not the host path
    # 'bubble_sandbox' names, which means nothing inside the sandbox.
    bwrap_sandbox.execute.side_effect = bs_config.EnvironmentNotFound(
        pathlib.Path("/environments/bare")
    )

    with pytest.raises(skills_bwrap_sandbox.SandboxUnavailable) as exc_info:
        await skills_bwrap_sandbox.skill_run(
            bwrap_sandbox=bwrap_sandbox,
            command=["/bin/true"],
            environment_name="bare",
        )

    assert exc_info.value.environment == "bare"
    assert "the 'bare' environment" in exc_info.value.message
    assert "/environments/" not in exc_info.value.message


@pytest.mark.asyncio
@pytest.mark.parametrize("w_error, exp_reason", EXECUTION_ERROR_CASES)
async def test_skill_run_python_w_execution_error(
    bwrap_sandbox,
    w_error,
    exp_reason,
):
    bwrap_sandbox.execute_python.side_effect = w_error

    with pytest.raises(skills_bwrap_sandbox.SandboxUnavailable) as exc_info:
        await skills_bwrap_sandbox.skill_run_python(
            bwrap_sandbox=bwrap_sandbox,
            script="print('hello')",
            environment_name="one",
        )

    assert exc_info.value.__cause__ is w_error
    assert exc_info.value.environment == "one"
    assert exp_reason in exc_info.value.message
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
    w_kw,
    ctx_w_deps,
    bwrap_sandbox,
):
    found = await skills_bwrap_sandbox.skill_run_python(
        bwrap_sandbox=bwrap_sandbox,
        script="print('hello')",
        **w_kw,
    )

    assert found is bwrap_sandbox.execute_python.return_value

    exp_kw = {
        "environment_name": None,
        "workdir": None,
        "script_path": "script.py",
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
    "w_wd_path, w_room_id, w_thread_id, exp_path",
    [
        (False, True, True, False),
        (True, False, True, False),
        (True, True, False, False),
        (True, True, True, True),
    ],
)
def test_get_workdir(
    workdirs_path,
    w_wd_path,
    w_room_id,
    w_thread_id,
    exp_path,
):
    if w_wd_path:
        wd_path = workdirs_path
    else:
        wd_path = None

    if exp_path:
        expected = workdirs_path / ROOM_ID / THREAD_ID_STR
    else:
        expected = None

    found = skills_bwrap_sandbox.get_workdir(
        wd_path,
        ROOM_ID if w_room_id else None,
        THREAD_ID_STR if w_thread_id else None,
    )

    assert found == expected

    if expected is not None:
        assert expected.is_dir()


def test_get_workdir_is_reused_across_runs(workdirs_path):
    first = skills_bwrap_sandbox.get_workdir(
        workdirs_path, ROOM_ID, THREAD_ID_STR
    )
    (first / "earlier.txt").write_text("kept", encoding="utf-8")

    second = skills_bwrap_sandbox.get_workdir(
        workdirs_path, ROOM_ID, THREAD_ID_STR
    )

    assert second == first
    assert (second / "earlier.txt").read_text(encoding="utf-8") == "kept"


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
        call_id=uuid.uuid4(),
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
        call_id=uuid.uuid4(),
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
        {"environment": "test-environment"},
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
        "default_environment": w_kwargs.pop("environment", "bare"),
        "config": exp_config,
        "volumes": {},
    } | w_kwargs

    bs_klass.assert_called_once_with(**exp_sandbox_kw)


@pytest.mark.anyio
@pytest.mark.parametrize("w_iconfig", [False, True])
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
    w_iconfig,
    audit_records,
):
    bs_klass.return_value.config.list_environments.return_value = (
        ALL_ENVIRONMENTS
    )
    skill_run.return_value = _execute_result(exit_code=0)

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
    )

    assert found == EXEC_RENDERED

    exp_kw = {
        "environment_name": "bare",
        "workdir": gw.return_value,
        "extra_volumes": gev.return_value,
    }

    skill_run.assert_called_once_with(
        bwrap_sandbox=sandbox,
        command=["/bin/true"],
        **exp_kw,
    )

    record = audit_records[-1]
    assert record.action == loggers.AUDIT_SANDBOX_ACTION_RUN
    assert record.outcome == loggers.AUDIT_OUTCOME_SUCCESS
    assert record.exit_code == 0
    assert record.workdir == str(gw.return_value)
    assert record.environment == "bare"
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
        )
        gev.assert_called_once_with(
            None,
            None,
            ROOM_ID,
            THREAD_ID_STR,
        )


@pytest.mark.anyio
@pytest.mark.parametrize("w_iconfig", [False, True])
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
    w_iconfig,
    audit_records,
):
    bs_klass.return_value.config.list_environments.return_value = (
        ALL_ENVIRONMENTS
    )
    skill_run_python.return_value = _execute_result(exit_code=0)

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
    )

    assert found == EXEC_RENDERED

    exp_kw = {
        "environment_name": "bare",
        "workdir": gw.return_value,
        "extra_volumes": gev.return_value,
    }

    ((_, found_kw),) = skill_run_python.call_args_list
    snapshot = found_kw.pop("script_path")
    assert snapshot.startswith(f"{skills_bwrap_sandbox.EXECUTIONS_SUBDIR}/")
    assert (
        found_kw
        == {
            "bwrap_sandbox": sandbox,
            "script": "print('hello')",
        }
        | exp_kw
    )

    record = audit_records[-1]
    assert record.action == loggers.AUDIT_SANDBOX_ACTION_RUN_PYTHON
    assert record.outcome == loggers.AUDIT_OUTCOME_SUCCESS
    assert record.exit_code == 0
    assert record.workdir == str(gw.return_value)
    assert record.environment == "bare"
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
        )
        gev.assert_called_once_with(
            None,
            None,
            ROOM_ID,
            THREAD_ID_STR,
        )


@pytest.mark.parametrize("w_iconfig", [False, True])
@pytest.mark.parametrize(
    "w_kwargs",
    [
        {},
        {"id": "test-toolset-id"},
        {"max_retries": 17},
        {"environment": "test-environment"},
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
    static, _runtime = capability.get_instructions()
    assert "sandbox" in static.lower()
    assert capability.get_toolset() is csts.return_value

    exp_toolset_kw = (
        {
            "id": capability.id,
            "environment": "bare",
            "sandbox_config": None,
            "volumes": None,
            "max_retries": 1,
            "multimodal": False,
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
@pytest.mark.parametrize("w_exit_code", [42, -1])
@pytest.mark.parametrize(
    "w_tool, w_helper, w_action, w_arg",
    [
        (
            "run",
            "skill_run",
            loggers.AUDIT_SANDBOX_ACTION_RUN,
            {"command": ["/bin/true"]},
        ),
        (
            "run_python",
            "skill_run_python",
            loggers.AUDIT_SANDBOX_ACTION_RUN_PYTHON,
            {"script": "print('hello')"},
        ),
    ],
)
@mock.patch("soliplex.skills.bwrap_sandbox.get_extra_volumes")
@mock.patch("soliplex.skills.bwrap_sandbox.get_workdir")
@mock.patch("bubble_sandbox.sandbox.BwrapSandbox")
async def test_create_sandbox_toolset_audits_failing_exit_code(
    bs_klass,
    gw,
    gev,
    ctx_w_deps,
    i_config,
    audit_records,
    w_tool,
    w_helper,
    w_action,
    w_arg,
    w_exit_code,
):
    """A bad exit fails the record, though the tool still returns text"""
    toolset = skills_bwrap_sandbox.create_sandbox_toolset(
        installation_config=i_config,
    )
    tool = toolset.tools[w_tool]
    result = _execute_result(exit_code=w_exit_code)

    with mock.patch.object(
        skills_bwrap_sandbox, w_helper, return_value=result
    ):
        found = await tool.function(ctx=ctx_w_deps, **w_arg)

    assert found == (
        f"Command failed (exit code {w_exit_code}):\n{EXEC_RENDERED}"
    )

    record = audit_records[-1]
    assert record.action == w_action
    assert record.outcome == loggers.AUDIT_OUTCOME_ERROR
    assert record.reason == loggers.AUDIT_SANDBOX_REASON_EXIT_CODE
    assert record.exit_code == w_exit_code
    assert record.workdir == str(gw.return_value)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "w_tool, w_helper, w_action, w_arg",
    [
        (
            "run",
            "skill_run",
            loggers.AUDIT_SANDBOX_ACTION_RUN,
            {"command": ["/bin/true"]},
        ),
        (
            "run_python",
            "skill_run_python",
            loggers.AUDIT_SANDBOX_ACTION_RUN_PYTHON,
            {"script": "print('hello')"},
        ),
    ],
)
@mock.patch("soliplex.skills.bwrap_sandbox.get_extra_volumes")
@mock.patch("soliplex.skills.bwrap_sandbox.get_workdir")
@mock.patch("bubble_sandbox.sandbox.BwrapSandbox")
async def test_create_sandbox_toolset_audits_timeout(
    bs_klass,
    gw,
    gev,
    ctx_w_deps,
    i_config,
    audit_records,
    w_tool,
    w_helper,
    w_action,
    w_arg,
):
    toolset = skills_bwrap_sandbox.create_sandbox_toolset(
        installation_config=i_config,
    )
    tool = toolset.tools[w_tool]
    result = bs_models.ExecuteResult(timed_out=True, timeout_seconds=30.0)

    with mock.patch.object(
        skills_bwrap_sandbox, w_helper, return_value=result
    ):
        found = await tool.function(ctx=ctx_w_deps, **w_arg)

    assert "after 30 seconds" in found

    record = audit_records[-1]
    assert record.action == w_action
    assert record.outcome == loggers.AUDIT_OUTCOME_ERROR
    assert record.reason == loggers.AUDIT_SANDBOX_REASON_TIMEOUT
    assert record.timeout_seconds == 30.0
    assert record.exit_code is None


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


def test_script_snapshot_path():
    call_id = uuid.uuid4()

    found = skills_bwrap_sandbox.script_snapshot_path(RUN_ID_STR, call_id)

    assert found == (f".soliplex/executions/script-{RUN_ID_STR}-{call_id}.py")
    # Not at the workspace root, which the download listing serves.
    assert "/" in found


def test_script_snapshot_path_wo_run_id():
    call_id = uuid.uuid4()

    found = skills_bwrap_sandbox.script_snapshot_path(None, call_id)

    assert found == f".soliplex/executions/script-{call_id}.py"


def test_write_transcript_uses_the_call_id(transcripts_path):
    call_id = uuid.uuid4()

    found = skills_bwrap_sandbox.write_transcript(
        transcripts_path,
        ROOM_ID,
        THREAD_ID_STR,
        RUN_ID_STR,
        call_id=call_id,
        content="print(1)",
        suffix=".py",
    )

    assert pathlib.Path(found).stem == str(call_id)


@pytest.mark.anyio
@mock.patch("soliplex.skills.bwrap_sandbox.get_extra_volumes")
@mock.patch("soliplex.skills.bwrap_sandbox.get_workdir")
@mock.patch("soliplex.skills.bwrap_sandbox.skill_run_python")
@mock.patch("bubble_sandbox.sandbox.BwrapSandbox")
async def test_run_python_snapshots_the_source_per_call(
    bs_klass,
    skill_run_python,
    gw,
    gev,
    ctx_w_deps,
    i_config,
    transcripts_path,
):
    skill_run_python.return_value = _execute_result(exit_code=0)
    toolset = skills_bwrap_sandbox.create_sandbox_toolset(
        installation_config=i_config,
    )
    tool = toolset.tools["run_python"]

    await tool.function(ctx=ctx_w_deps, script="print(1)")

    ((_, kwargs),) = skill_run_python.call_args_list
    script_path = kwargs["script_path"]
    assert script_path.startswith(f".soliplex/executions/script-{RUN_ID_STR}-")

    (transcript,) = [
        path
        for path in (
            transcripts_path / ROOM_ID / THREAD_ID_STR / RUN_ID_STR
        ).glob("*.py")
    ]
    assert transcript.stem in script_path


def _volume(host_path=None, writable=False):
    return bs_models.VolumeInfo(host_path=host_path, writable=writable)


def test_effective_volumes_matches_the_sandbox():
    """'BwrapSandbox.build_bwrap_command' merges runtime over static, and
    the table and the sandbox must not disagree about what is mounted."""
    static = {"repo": _volume("/srv/repo"), "room": _volume("/srv/static")}
    runtime = {"room": _volume("/srv/runtime")}

    found = skills_bwrap_sandbox.effective_volumes(static, runtime)

    assert found["repo"].host_path == pathlib.Path("/srv/repo")
    assert found["room"].host_path == pathlib.Path("/srv/runtime")


@pytest.mark.parametrize(
    "w_specs, exp_line",
    [
        ([], "empty"),
        (["a.csv"], "1 file"),
        (["a.csv", "b.csv"], "2 files"),
    ],
)
def test_render_mount_table_counts_volume_files(
    temp_dir,
    w_specs,
    exp_line,
):
    volume_dir = temp_dir / "room"
    volume_dir.mkdir()
    for name in w_specs:
        (volume_dir / name).write_text("x", encoding="utf-8")

    found = skills_bwrap_sandbox.render_mount_table(
        workdir=None,
        volumes={"room": _volume(volume_dir)},
        dependencies=[],
    )

    assert f"{SANDBOX_VOLUMES_PATH}/room" in found
    assert exp_line in found
    # Counts, never names: a name is a disclosure with nothing recorded.
    for name in w_specs:
        assert name not in found


def test_render_mount_table_reports_writability(temp_dir):
    volume_dir = temp_dir / "scratch"
    volume_dir.mkdir()

    found = skills_bwrap_sandbox.render_mount_table(
        workdir=None,
        volumes={"scratch": _volume(volume_dir, writable=True)},
        dependencies=[],
    )

    assert "read-write" in found


def test_render_mount_table_counts_downloadable_workdir_files(temp_dir):
    workdir = temp_dir / "work"
    (workdir / skills_bwrap_sandbox.EXECUTIONS_SUBDIR).mkdir(parents=True)
    (workdir / "report.csv").write_text("x", encoding="utf-8")
    (workdir / "sub").mkdir()

    found = skills_bwrap_sandbox.render_mount_table(
        workdir=workdir,
        volumes={},
        dependencies=[],
    )

    # Only top-level regular files are downloadable, so only those count.
    assert "1 file" in found
    assert SANDBOX_WORKDIR_PATH in found


def test_render_mount_table_names_dependencies_wo_specifiers():
    found = skills_bwrap_sandbox.render_mount_table(
        workdir=None,
        volumes={},
        dependencies=["pandas>=3.0.1", "pillow", "numpy ; python_version>'3'"],
    )

    assert "pandas, pillow, numpy" in found
    assert ">=3.0.1" not in found


@pytest.mark.anyio
async def test_capability_instructions_carry_the_mount_table(
    ctx_w_deps,
    i_config,
    rooms_upload_path,
):
    (rooms_upload_path / ROOM_ID).mkdir()
    (rooms_upload_path / ROOM_ID / "rules.md").write_text(
        "x", encoding="utf-8"
    )

    capability = skills_bwrap_sandbox.create_bwrap_sandbox_capability(
        installation_config=i_config,
    )
    static, runtime = capability.get_instructions()

    assert "sandbox" in static.lower()

    found = await runtime(ctx_w_deps)

    assert f"{SANDBOX_VOLUMES_PATH}/room" in found
    assert "1 file" in found
    assert "rules.md" not in found


def test_render_mount_table_w_unparseable_dependency():
    found = skills_bwrap_sandbox.render_mount_table(
        workdir=None,
        volumes={},
        dependencies=["not a requirement!!"],
    )

    assert "not a requirement!!" in found


@pytest.mark.parametrize("w_iconfig", [False, True])
def test_capability_dependencies(environments_path, i_config, w_iconfig):
    env_dir = environments_path / "analysis"
    (env_dir / ".venv").mkdir(parents=True)
    (env_dir / "pyproject.toml").write_text(
        '[project]\nname = "analysis"\ndependencies = ["pandas>=3"]\n',
        encoding="utf-8",
    )

    kwargs = {"installation_config": i_config} if w_iconfig else {}
    capability = skills_bwrap_sandbox.create_bwrap_sandbox_capability(
        environment="analysis",
        sandbox_config=bs_config.Config(
            environments_pathname=str(environments_path),
        ),
        **kwargs,
    )

    assert capability._dependencies() == ["pandas>=3"]


def test_capability_dependencies_wo_a_matching_environment(
    environments_path,
):
    env_dir = environments_path / "analysis"
    (env_dir / ".venv").mkdir(parents=True)
    (env_dir / "pyproject.toml").write_text(
        '[project]\nname = "analysis"\ndependencies = ["pandas>=3"]\n',
        encoding="utf-8",
    )

    capability = skills_bwrap_sandbox.create_bwrap_sandbox_capability(
        environment="nonesuch",
        sandbox_config=bs_config.Config(
            environments_pathname=str(environments_path),
        ),
    )

    assert capability._dependencies() == []


@pytest.mark.anyio
async def test_capability_instructions_wo_installation_config(ctx_w_deps):
    capability = skills_bwrap_sandbox.create_bwrap_sandbox_capability()
    _static, runtime = capability.get_instructions()

    found = await runtime(ctx_w_deps)

    assert SANDBOX_WORKDIR_PATH in found


@pytest.mark.anyio
async def test_capability_wo_installation_sandbox_config(ctx_w_deps):
    i_config = config_installation.InstallationConfig(id="testing")
    assert i_config.sandbox_config is None
    capability = skills_bwrap_sandbox.create_bwrap_sandbox_capability(
        installation_config=i_config,
    )

    toolset = capability.get_toolset()
    _static, runtime = capability.get_instructions()
    found = await runtime(ctx_w_deps)

    assert set(toolset.tools) == {"run", "run_python"}
    assert "discarded after each command" in found


@pytest.mark.anyio
@pytest.mark.parametrize(
    "w_tool, w_helper, w_arg",
    [
        ("run", "skill_run", {"command": ["/bin/true"]}),
        ("run_python", "skill_run_python", {"script": "print(1)"}),
    ],
)
@mock.patch("bubble_sandbox.sandbox.BwrapSandbox")
async def test_tools_get_a_workspace_wo_workdirs_path(
    bs_klass,
    ctx_w_deps,
    w_tool,
    w_helper,
    w_arg,
):
    toolset = skills_bwrap_sandbox.create_sandbox_toolset()
    tool = toolset.tools[w_tool]

    with mock.patch.object(
        skills_bwrap_sandbox, w_helper, return_value=_execute_result()
    ) as helper:
        await tool.function(ctx=ctx_w_deps, **w_arg)

    ((_, kwargs),) = helper.call_args_list
    workdir = kwargs["workdir"]

    assert workdir is not None
    # Discarded once the call returns.
    assert not workdir.exists()


def test_render_mount_table_wo_a_persistent_workspace():
    found = skills_bwrap_sandbox.render_mount_table(
        workdir=None,
        persistent=False,
        volumes={},
        dependencies=[],
    )

    assert "discarded" in found
    assert "downloadable" not in found
    assert "kept for this thread" not in found


@pytest.mark.anyio
@mock.patch("bubble_sandbox.sandbox.BwrapSandbox")
async def test_run_python_reports_a_blocked_snapshot_path(
    bs_klass,
    ctx_w_deps,
):
    toolset = skills_bwrap_sandbox.create_sandbox_toolset()
    tool = toolset.tools["run_python"]
    bs_klass.return_value.execute_python.side_effect = (
        bs_sandbox.InvalidScriptPath(
            ".soliplex/executions/script-x.py", "not a directory"
        )
    )

    with pytest.raises(pydantic_ai.ModelRetry) as exc_info:
        await tool.function(ctx=ctx_w_deps, script="print(1)")

    assert SANDBOX_WORKDIR_PATH in exc_info.value.message


@pytest.mark.asyncio
async def test_skill_run_python_translates_a_blocked_snapshot_path(
    bwrap_sandbox,
):
    bwrap_sandbox.execute_python.side_effect = bs_sandbox.InvalidScriptPath(
        ".soliplex/executions/script-x.py", "not a directory"
    )

    with pytest.raises(skills_bwrap_sandbox.WorkspacePathBlocked):
        await skills_bwrap_sandbox.skill_run_python(
            bwrap_sandbox=bwrap_sandbox,
            script="print(1)",
            environment_name="bare",
        )


IMAGE_BYTES = base64.b64decode(
    # 1x1 PNG
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKm"
    "MIQAAAABJRU5ErkJggg=="
)


@pytest.fixture
def image_workdir(temp_dir):
    result = temp_dir / "work"
    result.mkdir()
    (result / "plot.png").write_bytes(IMAGE_BYTES)
    return result


def test_open_beneath_reads_a_regular_file(image_workdir):
    found = skills_bwrap_sandbox.read_beneath(image_workdir, "plot.png", 4096)

    assert found == IMAGE_BYTES


def test_open_beneath_reads_a_nested_file(image_workdir):
    nested = image_workdir / "figures"
    nested.mkdir()
    (nested / "plot.png").write_bytes(IMAGE_BYTES)

    found = skills_bwrap_sandbox.read_beneath(
        image_workdir, "figures/plot.png", 4096
    )

    assert found == IMAGE_BYTES


@pytest.mark.parametrize(
    "w_relative",
    ["/etc/passwd", "../escape.png", "figures/../../escape.png", "", "."],
)
def test_open_beneath_rejects_escaping_paths(image_workdir, w_relative):
    with pytest.raises(skills_bwrap_sandbox.UnreadablePath):
        skills_bwrap_sandbox.read_beneath(image_workdir, w_relative, 4096)


def test_open_beneath_rejects_a_symlinked_file(image_workdir, temp_dir):
    victim = temp_dir / "victim.png"
    victim.write_bytes(IMAGE_BYTES)
    (image_workdir / "sneaky.png").symlink_to(victim)

    with pytest.raises(skills_bwrap_sandbox.UnreadablePath):
        skills_bwrap_sandbox.read_beneath(image_workdir, "sneaky.png", 4096)


def test_open_beneath_rejects_a_symlinked_parent(image_workdir, temp_dir):
    outside = temp_dir / "outside"
    outside.mkdir()
    (outside / "plot.png").write_bytes(IMAGE_BYTES)
    (image_workdir / "figures").symlink_to(outside)

    with pytest.raises(skills_bwrap_sandbox.UnreadablePath):
        skills_bwrap_sandbox.read_beneath(
            image_workdir, "figures/plot.png", 4096
        )


def test_open_beneath_rejects_a_fifo(image_workdir):
    os.mkfifo(image_workdir / "pipe.png")

    with pytest.raises(skills_bwrap_sandbox.UnreadablePath):
        skills_bwrap_sandbox.read_beneath(image_workdir, "pipe.png", 4096)


def test_open_beneath_rejects_a_directory(image_workdir):
    (image_workdir / "sub.png").mkdir()

    with pytest.raises(skills_bwrap_sandbox.UnreadablePath):
        skills_bwrap_sandbox.read_beneath(image_workdir, "sub.png", 4096)


def test_open_beneath_rejects_an_oversized_file(image_workdir):
    with pytest.raises(skills_bwrap_sandbox.ImageTooLarge):
        skills_bwrap_sandbox.read_beneath(image_workdir, "plot.png", 4)


def test_open_beneath_rejects_a_missing_file(image_workdir):
    with pytest.raises(skills_bwrap_sandbox.UnreadablePath):
        skills_bwrap_sandbox.read_beneath(image_workdir, "nope.png", 4096)


def _png(size=(1, 1), fmt="PNG"):
    buffer = io.BytesIO()
    PIL_Image.new("RGB", size).save(buffer, format=fmt)
    return buffer.getvalue()


@pytest.mark.parametrize(
    "w_format, exp_media_type",
    [
        ("PNG", "image/png"),
        ("JPEG", "image/jpeg"),
        ("WEBP", "image/webp"),
        ("GIF", "image/gif"),
    ],
)
def test_decode_image_w_supported_formats(w_format, exp_media_type):
    found = skills_bwrap_sandbox.decode_image("x.img", _png(fmt=w_format))

    assert found.media_type == exp_media_type


def test_decode_image_takes_the_type_from_the_content(temp_dir):
    found = skills_bwrap_sandbox.decode_image("plot.jpg", _png(fmt="PNG"))

    assert found.media_type == "image/png"


@pytest.mark.parametrize(
    "w_bytes",
    [b"", b"not an image at all", _png()[:20]],
)
def test_decode_image_rejects_non_images(w_bytes):
    with pytest.raises(skills_bwrap_sandbox.NotAnImage):
        skills_bwrap_sandbox.decode_image("x.png", w_bytes)


def test_decode_image_rejects_an_unsupported_format():
    buffer = io.BytesIO()
    PIL_Image.new("RGB", (1, 1)).save(buffer, format="BMP")

    with pytest.raises(skills_bwrap_sandbox.NotAnImage):
        skills_bwrap_sandbox.decode_image("x.bmp", buffer.getvalue())


def test_decode_image_rejects_a_decompression_bomb(monkeypatch):
    monkeypatch.setattr(PIL_Image, "MAX_IMAGE_PIXELS", 4)

    with pytest.raises(skills_bwrap_sandbox.NotAnImage):
        skills_bwrap_sandbox.decode_image("x.png", _png(size=(64, 64)))


def test_image_label_says_it_is_tool_output():
    found = skills_bwrap_sandbox.image_label("/sandbox/work/plot.png")

    assert "/sandbox/work/plot.png" in found
    assert "tool output" in found.lower()
    # A thread volume holds the user's own uploads, so the label must not
    # claim the image did not come from them.
    assert "not provided by the user" not in found.lower()


def test_resolve_sandbox_path_w_the_workdir(temp_dir):
    found = skills_bwrap_sandbox.resolve_sandbox_path(
        f"{SANDBOX_WORKDIR_PATH}/plot.png",
        workdir=temp_dir,
        volumes={},
    )

    assert found == (temp_dir, "plot.png", "work")


def test_resolve_sandbox_path_w_a_volume(temp_dir):
    found = skills_bwrap_sandbox.resolve_sandbox_path(
        f"{SANDBOX_VOLUMES_PATH}/room/figures/a.png",
        workdir=None,
        volumes={"room": _volume(temp_dir)},
    )

    assert found == (temp_dir, "figures/a.png", "room")


@pytest.mark.parametrize(
    "w_path",
    [
        "/etc/passwd",
        "plot.png",
        f"{SANDBOX_VOLUMES_PATH}/nonesuch/a.png",
        SANDBOX_VOLUMES_PATH,
        f"{SANDBOX_WORKDIR_PATH}",
    ],
)
def test_resolve_sandbox_path_rejects_what_is_not_mounted(temp_dir, w_path):
    with pytest.raises(skills_bwrap_sandbox.UnreadablePath):
        skills_bwrap_sandbox.resolve_sandbox_path(
            w_path,
            workdir=temp_dir,
            volumes={"room": _volume(temp_dir)},
        )


def test_resolve_sandbox_path_wo_a_workdir():
    with pytest.raises(skills_bwrap_sandbox.UnreadablePath):
        skills_bwrap_sandbox.resolve_sandbox_path(
            f"{SANDBOX_WORKDIR_PATH}/plot.png",
            workdir=None,
            volumes={},
        )


def test_resolve_sandbox_path_w_an_empty_volume(temp_dir):
    with pytest.raises(skills_bwrap_sandbox.UnreadablePath):
        skills_bwrap_sandbox.resolve_sandbox_path(
            f"{SANDBOX_VOLUMES_PATH}/room/a.png",
            workdir=None,
            volumes={"room": _volume(None)},
        )


@pytest.mark.parametrize("w_multimodal", [False, True])
def test_read_image_is_gated_on_multimodal(w_multimodal):
    toolset = skills_bwrap_sandbox.create_sandbox_toolset(
        multimodal=w_multimodal,
    )

    assert ("read_image" in toolset.tools) is w_multimodal


@pytest.mark.anyio
@mock.patch("bubble_sandbox.sandbox.BwrapSandbox")
async def test_read_image_returns_labelled_content(
    bs_klass,
    ctx_w_deps,
    i_config,
    workdirs_path,
    audit_records,
):
    workdir = workdirs_path / ROOM_ID / THREAD_ID_STR
    workdir.mkdir(parents=True)
    (workdir / "plot.png").write_bytes(_png())

    toolset = skills_bwrap_sandbox.create_sandbox_toolset(
        installation_config=i_config,
        multimodal=True,
    )
    tool = toolset.tools["read_image"]

    found = await tool.function(
        ctx=ctx_w_deps,
        path=f"{SANDBOX_WORKDIR_PATH}/plot.png",
    )

    assert isinstance(found, ai_messages.ToolReturn)
    label, content = found.content
    assert f"{SANDBOX_WORKDIR_PATH}/plot.png" in label
    assert content.media_type == "image/png"

    record = audit_records[-1]
    assert record.action == loggers.AUDIT_SANDBOX_ACTION_READ_IMAGE
    assert record.outcome == loggers.AUDIT_OUTCOME_SUCCESS
    assert record.path == f"{SANDBOX_WORKDIR_PATH}/plot.png"
    assert record.volume == "work"
    assert record.media_type == "image/png"
    assert record.byte_count == len(_png())


@pytest.mark.anyio
@mock.patch("bubble_sandbox.sandbox.BwrapSandbox")
async def test_read_image_audits_a_refusal(
    bs_klass,
    ctx_w_deps,
    i_config,
    workdirs_path,
    audit_records,
):
    (workdirs_path / ROOM_ID / THREAD_ID_STR).mkdir(parents=True)
    toolset = skills_bwrap_sandbox.create_sandbox_toolset(
        installation_config=i_config,
        multimodal=True,
    )
    tool = toolset.tools["read_image"]

    with pytest.raises(skills_bwrap_sandbox.UnreadablePath):
        await tool.function(
            ctx=ctx_w_deps,
            path=f"{SANDBOX_WORKDIR_PATH}/nope.png",
        )

    record = audit_records[-1]
    assert record.action == loggers.AUDIT_SANDBOX_ACTION_READ_IMAGE
    assert record.outcome == loggers.AUDIT_OUTCOME_ERROR
    assert record.reason == "UnreadablePath"


def test_open_beneath_w_an_unreadable_root(temp_dir):
    with pytest.raises(skills_bwrap_sandbox.UnreadablePath):
        skills_bwrap_sandbox.read_beneath(
            temp_dir / "nonesuch", "plot.png", 4096
        )


@pytest.mark.parametrize("w_persistent", [False, True])
def test_format_execute_result_timeout_remedy_follows_the_workspace(
    w_persistent,
):
    found = skills_bwrap_sandbox.format_execute_result(
        _result(timed_out=True, timeout_seconds=30.0),
        persistent=w_persistent,
    )

    assert "after 30 seconds" in found
    assert (SANDBOX_WORKDIR_PATH in found) is w_persistent


@pytest.mark.parametrize("w_persistent", [False, True])
def test_format_execute_result_truncation_remedy_follows_the_workspace(
    w_persistent,
):
    found = skills_bwrap_sandbox.format_execute_result(
        _result(stdout="X", truncated=True, max_output_chars=1),
        persistent=w_persistent,
    )

    assert "1 character" in found
    assert (SANDBOX_WORKDIR_PATH in found) is w_persistent


@pytest.mark.parametrize("w_persistent", [False, True])
def test_image_too_large_remedy_follows_the_workspace(w_persistent):
    error = skills_bwrap_sandbox.ImageTooLarge(
        "/sandbox/volumes/room/big.png",
        99,
        10,
        persistent=w_persistent,
    )

    assert (SANDBOX_WORKDIR_PATH in error.message) is w_persistent
