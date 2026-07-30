import pathlib

import pytest
from pydantic_ai import Agent
from pydantic_ai import ModelRetry
from pydantic_ai.messages import ModelResponse
from pydantic_ai.messages import TextPart
from pydantic_ai.messages import ToolCallPart
from pydantic_ai.models.function import FunctionModel

from soliplex.capabilities import filesystem as cap_fs


def _write_skill(
    path: pathlib.Path,
    *,
    name: str | None = None,
    description: str = "A test capability",
    instructions: str = "Follow the test instructions.",
):
    path.mkdir(parents=True, exist_ok=True)
    name = name or path.name
    (path / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n"
        f"{instructions}\n",
        encoding="utf-8",
    )


def test_discover_single_capability_path(temp_dir):
    path = temp_dir / "test-capability"
    _write_skill(path)

    capabilities, errors = cap_fs.discover_filesystem_capabilities([path])

    assert errors == []
    (capability,) = capabilities
    assert capability.id == "test-capability"
    assert capability.description == "A test capability"
    assert capability.defer_loading is True
    assert capability.path == path
    assert capability.get_instructions() == "Follow the test instructions."


def test_discover_capability_children_ignores_unrelated_entries(temp_dir):
    _write_skill(temp_dir / "alpha")
    _write_skill(temp_dir / "beta")
    _write_skill(temp_dir / ".hidden")
    (temp_dir / "plain.txt").write_text("not a capability")
    (temp_dir / "empty").mkdir()

    capabilities, errors = cap_fs.discover_filesystem_capabilities([temp_dir])

    assert errors == []
    assert [capability.id for capability in capabilities] == ["alpha", "beta"]


def test_discover_missing_path(temp_dir):
    path = temp_dir / "missing"

    capabilities, errors = cap_fs.discover_filesystem_capabilities([path])

    assert capabilities == []
    assert len(errors) == 1
    assert errors[0].path == path
    assert "does not exist" in str(errors[0])


@pytest.mark.parametrize(
    "text, message",
    [
        ("not frontmatter", "must start"),
        ("---\nname: broken", "no closing"),
        ("---\n: invalid\n---\nBody", "while parsing"),
        (
            "---\nname: Invalid_Name\ndescription: Test\n---\nBody",
            "lowercase letters",
        ),
        (
            "---\nname: other\ndescription: Test\n---\nBody",
            "does not match",
        ),
        (
            "---\nname: broken\ndescription: Test\n---\n",
            "contains no instructions",
        ),
    ],
)
def test_discover_reports_invalid_skill_files(temp_dir, text, message):
    path = temp_dir / "broken"
    path.mkdir()
    (path / "SKILL.md").write_text(text)

    capabilities, errors = cap_fs.discover_filesystem_capabilities([path])

    assert capabilities == []
    assert len(errors) == 1
    assert errors[0].path == path
    assert message in str(errors[0])


def test_discover_reports_read_error(temp_dir, monkeypatch):
    path = temp_dir / "broken"
    _write_skill(path)

    def fail_read(*args, **kwargs):
        raise OSError("unreadable")

    monkeypatch.setattr(pathlib.Path, "read_text", fail_read)

    capabilities, errors = cap_fs.discover_filesystem_capabilities([path])

    assert capabilities == []
    assert "unreadable" in str(errors[0])


@pytest.mark.anyio
async def test_capability_uses_native_deferred_loading(temp_dir):
    path = temp_dir / "test-capability"
    _write_skill(path)
    capabilities, _ = cap_fs.discover_filesystem_capabilities([path])
    requests = []

    def model_function(messages, info):
        requests.append(messages)
        if len(requests) == 1:
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        "load_capability",
                        {"id": "test-capability"},
                    )
                ]
            )
        return ModelResponse(parts=[TextPart("done")])

    agent = Agent(FunctionModel(model_function), capabilities=capabilities)

    result = await agent.run("Use the test capability")

    assert result.output == "done"
    assert len(requests) == 2
    assert "Follow the test instructions." in str(requests[-1])


def test_filesystem_capability_error_retains_path(temp_dir):
    error = cap_fs.FilesystemCapabilityError("bad", temp_dir)

    assert error.path == temp_dir
    assert str(error) == "bad"


def _capability(path):
    capabilities, errors = cap_fs.discover_filesystem_capabilities([path])
    assert errors == []
    (capability,) = capabilities
    return capability


def test_instruction_only_capability_has_no_toolset(temp_dir):
    path = temp_dir / "test-capability"
    _write_skill(path)

    assert _capability(path).get_toolset() is None


@pytest.mark.parametrize(
    "dirnames, tool_names",
    [
        (["resources"], ["read_resource"]),
        (["scripts"], ["run_script"]),
        (["resources", "scripts"], ["read_resource", "run_script"]),
    ],
)
def test_toolset_matches_bundled_directories(temp_dir, dirnames, tool_names):
    path = temp_dir / "test-capability"
    _write_skill(path)
    for dirname in dirnames:
        (path / dirname).mkdir()

    toolset = _capability(path).get_toolset()

    assert sorted(toolset.tools) == tool_names


@pytest.mark.anyio
async def test_read_resource_returns_file_content(temp_dir):
    path = temp_dir / "test-capability"
    _write_skill(path)
    (path / "resources").mkdir()
    (path / "resources" / "poem.md").write_text("Verse\n", encoding="utf-8")

    content = await _capability(path).read_resource("resources/poem.md")

    assert content == "Verse\n"


@pytest.mark.anyio
async def test_read_resource_rejects_path_escape(temp_dir):
    path = temp_dir / "test-capability"
    _write_skill(path)
    (path / "resources").mkdir()

    with pytest.raises(ModelRetry, match="not under 'resources/'"):
        await _capability(path).read_resource("../SKILL.md")


@pytest.mark.anyio
async def test_read_resource_missing_file(temp_dir):
    path = temp_dir / "test-capability"
    _write_skill(path)
    (path / "resources").mkdir()

    with pytest.raises(ModelRetry, match="No such resource"):
        await _capability(path).read_resource("resources/missing.md")


def _write_script(path, name, body):
    (path / "scripts").mkdir(exist_ok=True)
    (path / "scripts" / name).write_text(body, encoding="utf-8")


@pytest.mark.anyio
async def test_run_script_returns_stdout(temp_dir):
    path = temp_dir / "test-capability"
    _write_skill(path)
    _write_script(
        path,
        "echo.py",
        "import sys\nprint(' '.join(sys.argv[1:]))\n",
    )

    output = await _capability(path).run_script(
        "scripts/echo.py", "stanza jabberwocky --stanza 3"
    )

    assert output == "stanza jabberwocky --stanza 3\n"


@pytest.mark.anyio
async def test_run_script_reports_stderr_and_exit_status(temp_dir):
    path = temp_dir / "test-capability"
    _write_skill(path)
    _write_script(
        path,
        "fail.py",
        "import sys\nprint('partial')\nsys.stderr.write('boom\\n')\n"
        "sys.exit(3)\n",
    )

    output = await _capability(path).run_script("scripts/fail.py", "")

    assert "partial" in output
    assert "boom" in output
    assert "exit status: 3" in output


@pytest.mark.anyio
async def test_run_script_rejects_path_escape(temp_dir):
    path = temp_dir / "test-capability"
    _write_skill(path)
    (path / "scripts").mkdir()

    with pytest.raises(ModelRetry, match="not under 'scripts/'"):
        await _capability(path).run_script("../../evil.py", "")


@pytest.mark.anyio
async def test_run_script_missing_script(temp_dir):
    path = temp_dir / "test-capability"
    _write_skill(path)
    (path / "scripts").mkdir()

    with pytest.raises(ModelRetry, match="No such script"):
        await _capability(path).run_script("scripts/missing.py", "")


@pytest.mark.anyio
async def test_run_script_rejects_malformed_arguments(temp_dir):
    path = temp_dir / "test-capability"
    _write_skill(path)
    _write_script(path, "echo.py", "print('hi')\n")

    with pytest.raises(ModelRetry, match="Malformed arguments"):
        await _capability(path).run_script("scripts/echo.py", "'unbalanced")


@pytest.mark.anyio
async def test_run_script_times_out(temp_dir, monkeypatch):
    monkeypatch.setattr(cap_fs, "_SCRIPT_TIMEOUT_SECONDS", 0.2)
    path = temp_dir / "test-capability"
    _write_skill(path)
    _write_script(path, "slow.py", "import time\ntime.sleep(30)\n")

    output = await _capability(path).run_script("scripts/slow.py", "")

    assert "TIMED OUT" in output


@pytest.mark.anyio
async def test_agent_runs_capability_tools(temp_dir):
    path = temp_dir / "test-capability"
    _write_skill(path)
    (path / "resources").mkdir()
    (path / "resources" / "poem.md").write_text("Verse\n", encoding="utf-8")
    capabilities, _ = cap_fs.discover_filesystem_capabilities([path])
    requests = []

    def model_function(messages, info):
        requests.append(messages)
        if len(requests) == 1:
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        "load_capability",
                        {"id": "test-capability"},
                    )
                ]
            )
        if len(requests) == 2:
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        "read_resource",
                        {"path": "resources/poem.md"},
                    )
                ]
            )
        return ModelResponse(parts=[TextPart("done")])

    agent = Agent(FunctionModel(model_function), capabilities=capabilities)

    result = await agent.run("Read the poem")

    assert result.output == "done"
    assert "Verse" in str(requests[-1])
