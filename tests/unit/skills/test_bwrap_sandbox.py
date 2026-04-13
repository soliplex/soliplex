import pathlib
import uuid
from unittest import mock

import pytest
from bubble_sandbox import config as bs_config
from bubble_sandbox import models as bs_models
from bubble_sandbox import sandbox as bs_sandbox
from haiku.skills import models as hs_models
from haiku.skills import state as hs_state
from pydantic_ai import toolsets as ai_toolsets

from soliplex.config import installation as config_installation
from soliplex.skills import bwrap_sandbox as skills_bwrap_sandbox

ROOM_ID = "test_room"
THREAD_ID = uuid.uuid4()
RUN_ID = uuid.uuid4()


@pytest.fixture
def ctx_w_deps():
    ctx = mock.Mock(spec_set=["deps"])
    ctx.deps = mock.Mock(
        spec_set=["state"],
        state=skills_bwrap_sandbox.SandboxState(
            room_id=ROOM_ID,
            thread_id=str(THREAD_ID),
            run_id=str(RUN_ID),
        ),
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
def s_config(
    workdirs_path,
    environments_path,
):
    return mock.create_autospec(
        config_installation.SandboxConfig,
        environments_path=environments_path,
        workdirs_path=workdirs_path,
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
    "w_env_names, w_exists, w_has_toml, w_has_venv, expected",
    [
        ([], [], [], [], []),
        (["nonesuch"], [False], [False], [False], []),
        (["empty"], [True], [False], [False], []),
        (["no_venv"], [True], [True], [False], []),
        (["no_toml"], [True], [False], [True], []),
        (
            ["valid"],
            [True],
            [True],
            [True],
            [{"name": "valid", "description": "Describe valid"}],
        ),
    ],
)
async def test_skill_list_environments(
    temp_dir,
    ctx_w_deps,
    bwrap_sandbox,
    w_env_names,
    w_exists,
    w_has_toml,
    w_has_venv,
    expected,
):

    for env_name, exists, has_toml, has_venv in zip(
        w_env_names,
        w_exists,
        w_has_toml,
        w_has_venv,
        strict=True,
    ):
        env_subdir = temp_dir / env_name
        if exists:
            env_subdir.mkdir()

            if has_toml:
                toml = "\n".join(
                    [
                        "[project]",
                        f'name = "{env_name}"',
                        f'description = "Describe {env_name}"',
                    ]
                )
                toml_file = env_subdir / "pyproject.toml"
                toml_file.write_text(toml)

            if has_venv:
                venv_dir = env_subdir / ".venv"
                venv_dir.mkdir()

    found = await skills_bwrap_sandbox.skill_list_environments(
        bwrap_sandbox=bwrap_sandbox,
    )

    assert found == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("w_att_rte", [False, True])
@pytest.mark.parametrize("w_exit_code", [0, None, 42])
@pytest.mark.parametrize("w_truncated", [False, True])
@pytest.mark.parametrize(
    "w_command, exp_cmd_args",
    [
        ("echo 'foo'", ["sh", "-c", "echo 'foo'"]),
        (["/bin/true"], ["/bin/true"]),
    ],
)
async def test_skill_execute_w_errors_truncation(
    ctx_w_deps,
    bwrap_sandbox,
    w_command,
    exp_cmd_args,
    w_truncated,
    w_exit_code,
    w_att_rte,
):
    if w_att_rte:
        bwrap_sandbox.execute.side_effect = RuntimeError("test")
        expected = "Error: test"
    else:
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

    found = await skills_bwrap_sandbox.skill_execute(
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
async def test_skill_execute_w_extra_args(
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

    found = await skills_bwrap_sandbox.skill_execute(
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
@pytest.mark.parametrize("w_att_rte", [False, True])
@pytest.mark.parametrize("w_exit_code", [0, None, 42])
@pytest.mark.parametrize("w_truncated", [False, True])
async def test_skill_execute_script_w_errors_truncation(
    ctx_w_deps,
    bwrap_sandbox,
    w_truncated,
    w_exit_code,
    w_att_rte,
):
    if w_att_rte:
        bwrap_sandbox.execute_script.side_effect = RuntimeError("test")
        expected = "Error: test"
    else:
        bwrap_sandbox.execute_script.return_value = mock.create_autospec(
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

    found = await skills_bwrap_sandbox.skill_execute_script(
        bwrap_sandbox=bwrap_sandbox,
        script="print('hello')",
    )

    assert found == expected

    bwrap_sandbox.execute_script.assert_awaited_once_with(
        script="print('hello')",
        environment_name=None,
        workdir=None,
        timeout=None,
        extra_volumes=None,
    )


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
async def test_skill_execute_script_w_extra_args(
    ctx_w_deps,
    bwrap_sandbox,
    w_kw,
):
    bwrap_sandbox.execute_script.return_value = mock.create_autospec(
        bs_models.ExecuteResult,
        output="test output",
        exit_code=None,
        truncated=False,
    )
    expected = "test output"

    found = await skills_bwrap_sandbox.skill_execute_script(
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

    bwrap_sandbox.execute_script.assert_awaited_once_with(
        script="print('hello')",
        **exp_kw,
    )


@pytest.mark.parametrize("w_wd_path", [False, True])
def test_get_workdir(workdirs_path, w_wd_path):
    if w_wd_path:
        wd_path = workdirs_path
        expected = workdirs_path / ROOM_ID / str(THREAD_ID) / str(RUN_ID)
    else:
        wd_path = None
        expected = None

    found = skills_bwrap_sandbox.get_workdir(
        wd_path,
        ROOM_ID,
        THREAD_ID,
        RUN_ID,
    )

    assert found == expected

    if expected is not None:
        assert expected.is_dir()


@pytest.mark.parametrize("w_thread_path", [None, False, True])
@pytest.mark.parametrize("w_room_path", [None, False, True])
def test_get_extra_volumes(
    rooms_upload_path,
    threads_upload_path,
    w_room_path,
    w_thread_path,
):
    expected = {}

    if w_room_path is not None:
        ru_path = rooms_upload_path
        if w_room_path:
            room_path = ru_path / ROOM_ID
            room_path.mkdir(parents=True)
            expected["room"] = bs_models.VolumeInfo(
                host_path=room_path,
                writable=False,
            )
    else:
        ru_path = None

    if w_thread_path is not None:
        tu_path = threads_upload_path
        if w_thread_path:
            thread_path = tu_path / str(THREAD_ID)
            thread_path.mkdir(parents=True)
            expected["thread"] = bs_models.VolumeInfo(
                host_path=thread_path,
                writable=False,
            )
    else:
        tu_path = None

    found = skills_bwrap_sandbox.get_extra_volumes(
        ru_path,
        tu_path,
        ROOM_ID,
        THREAD_ID,
    )

    assert found == expected


@pytest.mark.parametrize("w_iconfig", [False, True])
@pytest.mark.parametrize(
    "w_kwargs",
    [
        {},
        {"id": "test-toolset-id"},
        {"max_retries": 17},
        {"default_environment_name": "test-environment"},
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
        "default_environment_name": "bare",
        "config": exp_config,
        "volumes": {},
    } | w_kwargs

    bs_klass.assert_called_once_with(**exp_sandbox_kw)


@pytest.mark.anyio
@mock.patch("soliplex.skills.bwrap_sandbox.skill_list_environments")
@mock.patch("bubble_sandbox.sandbox.BwrapSandbox")
async def test_create_sandbox_toolset_list_environments(
    bs_klass,
    skill_list_environments,
    ctx_w_deps,
):
    found = skills_bwrap_sandbox.create_sandbox_toolset()
    sandbox = bs_klass.return_value
    tool = found.tools["list_environments"]

    found = await tool.function(ctx=ctx_w_deps)

    assert found is skill_list_environments.return_value
    skill_list_environments.assert_called_once_with(
        bwrap_sandbox=sandbox,
    )


@pytest.mark.anyio
@pytest.mark.parametrize("w_iconfig", [False, True])
@pytest.mark.parametrize(
    "w_kw",
    [
        {},
        {"environment_name": "test-environment"},
        {"timeout": 17},
    ],
)
@mock.patch("soliplex.skills.bwrap_sandbox.get_extra_volumes")
@mock.patch("soliplex.skills.bwrap_sandbox.get_workdir")
@mock.patch("soliplex.skills.bwrap_sandbox.skill_execute")
@mock.patch("bubble_sandbox.sandbox.BwrapSandbox")
async def test_create_sandbox_toolset_execute(
    bs_klass,
    skill_execute,
    gw,
    gev,
    ctx_w_deps,
    i_config,
    workdirs_path,
    rooms_upload_path,
    threads_upload_path,
    w_kw,
    w_iconfig,
):
    if w_iconfig:
        toolset = skills_bwrap_sandbox.create_sandbox_toolset(
            installation_config=i_config,
        )
    else:
        toolset = skills_bwrap_sandbox.create_sandbox_toolset()

    sandbox = bs_klass.return_value
    tool = toolset.tools["execute"]

    found = await tool.function(
        ctx=ctx_w_deps,
        command=["/bin/true"],
        **w_kw,
    )

    assert found is skill_execute.return_value

    exp_kw = {
        "environment_name": None,
        "timeout": None,
        "workdir": gw.return_value,
        "extra_volumes": gev.return_value,
    } | w_kw

    skill_execute.assert_called_once_with(
        bwrap_sandbox=sandbox,
        command=["/bin/true"],
        **exp_kw,
    )

    if w_iconfig:
        gw.assert_called_once_with(
            workdirs_path,
            ROOM_ID,
            str(THREAD_ID),
            str(RUN_ID),
        )
        gev.assert_called_once_with(
            rooms_upload_path,
            threads_upload_path,
            ROOM_ID,
            str(THREAD_ID),
        )
    else:
        gw.assert_called_once_with(
            None,
            ROOM_ID,
            str(THREAD_ID),
            str(RUN_ID),
        )
        gev.assert_called_once_with(
            None,
            None,
            ROOM_ID,
            str(THREAD_ID),
        )


@pytest.mark.anyio
@pytest.mark.parametrize("w_iconfig", [False, True])
@pytest.mark.parametrize(
    "w_kw",
    [
        {},
        {"environment_name": "test-environment"},
        {"timeout": 17},
    ],
)
@mock.patch("soliplex.skills.bwrap_sandbox.get_extra_volumes")
@mock.patch("soliplex.skills.bwrap_sandbox.get_workdir")
@mock.patch("soliplex.skills.bwrap_sandbox.skill_execute_script")
@mock.patch("bubble_sandbox.sandbox.BwrapSandbox")
async def test_create_sandbox_toolset_execute_script(
    bs_klass,
    skill_execute_script,
    gw,
    gev,
    ctx_w_deps,
    i_config,
    workdirs_path,
    rooms_upload_path,
    threads_upload_path,
    w_kw,
    w_iconfig,
):
    if w_iconfig:
        toolset = skills_bwrap_sandbox.create_sandbox_toolset(
            installation_config=i_config,
        )
    else:
        toolset = skills_bwrap_sandbox.create_sandbox_toolset()

    sandbox = bs_klass.return_value
    tool = toolset.tools["execute_script"]

    found = await tool.function(
        ctx=ctx_w_deps,
        script="print('hello')",
        **w_kw,
    )

    assert found is skill_execute_script.return_value

    exp_kw = {
        "environment_name": None,
        "timeout": None,
        "workdir": gw.return_value,
        "extra_volumes": gev.return_value,
    } | w_kw

    skill_execute_script.assert_called_once_with(
        bwrap_sandbox=sandbox,
        script="print('hello')",
        **exp_kw,
    )

    if w_iconfig:
        gw.assert_called_once_with(
            workdirs_path,
            ROOM_ID,
            str(THREAD_ID),
            str(RUN_ID),
        )
        gev.assert_called_once_with(
            rooms_upload_path,
            threads_upload_path,
            ROOM_ID,
            str(THREAD_ID),
        )
    else:
        gw.assert_called_once_with(
            None,
            ROOM_ID,
            str(THREAD_ID),
            str(RUN_ID),
        )
        gev.assert_called_once_with(
            None,
            None,
            ROOM_ID,
            str(THREAD_ID),
        )


@pytest.mark.parametrize("w_iconfig", [False, True])
@pytest.mark.parametrize(
    "w_kwargs",
    [
        {},
        {"id": "test-toolset-id"},
        {"max_retries": 17},
        {"default_environment_name": "test-environment"},
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
@mock.patch("haiku.skills.parser.parse_skill_md")
def test_create_bwrap_sandbox_skill(psm, csts, w_kwargs, w_iconfig, i_config):
    metadata = hs_models.SkillMetadata(
        name="test-skill",
        description="This is a test skill",
    )
    instructions = "You are a test"
    psm.return_value = metadata, instructions
    exp_path = pathlib.Path(skills_bwrap_sandbox.__file__).parent

    if w_iconfig:
        iconfig_kwargs = {"installation_config": i_config}
        exp_iconfig_args = iconfig_kwargs
    else:
        iconfig_kwargs = {}
        exp_iconfig_args = {"installation_config": None}

    skill = skills_bwrap_sandbox.create_bwrap_sandbox_skill(
        **w_kwargs,
        **iconfig_kwargs,
    )

    assert isinstance(skill, hs_models.Skill)
    assert skill.metadata == metadata
    assert skill.instructions == instructions
    assert skill.path == exp_path
    assert skill.state_type is skills_bwrap_sandbox.STATE_TYPE
    assert skill.state_namespace == skills_bwrap_sandbox.STATE_NAMESPACE
    assert skill.deps_type is hs_state.SkillRunDeps

    (toolset,) = skill.toolsets
    assert toolset is csts.return_value

    exp_toolset_kw = (
        {
            "id": None,
            "default_environment_name": "bare",
            "sandbox_config": None,
            "volumes": None,
            "max_retries": 1,
        }
        | w_kwargs
        | exp_iconfig_args
    )

    csts.assert_called_once_with(**exp_toolset_kw)
