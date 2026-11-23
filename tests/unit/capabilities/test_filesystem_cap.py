import hashlib
import json
import pathlib
import re

import pytest
from pydantic_ai import Agent
from pydantic_ai import ModelRetry
from pydantic_ai import RunContext
from pydantic_ai.messages import ModelResponse
from pydantic_ai.messages import TextPart
from pydantic_ai.messages import ToolCallPart
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.models.test import TestModel
from pydantic_ai.usage import RunUsage

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
@pytest.mark.parametrize("capability_id", [None, "custom-id", "A_" + "x" * 48])
@pytest.mark.anyio
async def test_toolset_matches_bundled_directories(
    temp_dir, dirnames, tool_names, capability_id
):
    path = temp_dir / "test-capability"
    _write_skill(path)
    for dirname in dirnames:
        (path / dirname).mkdir()

    capability = _capability(path)
    capability.id = capability_id
    toolset = capability.get_toolset()
    tools = await toolset.get_tools(
        RunContext(deps=None, model=TestModel(), usage=RunUsage())
    )

    prefix = capability_id or path.name
    assert sorted(tools) == [f"{prefix}_{name}" for name in tool_names]


@pytest.mark.parametrize(
    "capability_id", [None, "a" * 51, "a" * 64, "custom.id"]
)
@pytest.mark.anyio
async def test_toolset_hashes_invalid_or_long_prefixes(
    temp_dir, capability_id
):
    prefixes = []
    for name in ("a" * 64, "b" * 64):
        path = temp_dir / name
        _write_skill(path)
        (path / "resources").mkdir()
        (path / "scripts").mkdir()
        capability = _capability(path)
        capability.id = capability_id

        tools = await capability.get_toolset().get_tools(
            RunContext(deps=None, model=TestModel(), usage=RunUsage())
        )

        prefix = (
            "skill_"
            + hashlib.sha256((capability_id or name).encode()).hexdigest()[:12]
        )
        assert sorted(tools) == [
            f"{prefix}_read_resource",
            f"{prefix}_run_script",
        ]
        for tool_name in tools:
            assert len(tool_name) <= 64
            assert re.fullmatch(r"[A-Za-z0-9_-]+", tool_name)
        prefixes.append(prefix)

    assert (prefixes[0] != prefixes[1]) == (capability_id is None)


@pytest.mark.parametrize("defer_loading", [False, True])
@pytest.mark.parametrize("tool_kind", ["resource", "script"])
@pytest.mark.anyio
async def test_agent_runs_two_capability_tools(
    temp_dir, defer_loading, tool_kind
):
    capabilities = []
    for name in ("alpha", "beta"):
        path = temp_dir / name
        _write_skill(path)
        (path / "resources").mkdir()
        (path / "resources" / "shared.md").write_text(name, encoding="utf-8")
        _write_script(path, "shared.py", f"print({name!r})")
        capability = _capability(path)
        capability.defer_loading = defer_loading
        capabilities.append(capability)
    requests = []
    suffix = "read_resource" if tool_kind == "resource" else "run_script"
    arguments = (
        {"path": "resources/shared.md"}
        if tool_kind == "resource"
        else {"script": "scripts/shared.py"}
    )

    def model_function(messages, info):
        requests.append(messages)
        if defer_loading and len(requests) == 1:
            return ModelResponse(
                parts=[
                    ToolCallPart("load_capability", {"id": name})
                    for name in ("alpha", "beta")
                ]
            )
        if len(requests) == 1 + int(defer_loading):
            exposed = {tool.name for tool in info.function_tools}
            assert {f"alpha_{suffix}", f"beta_{suffix}"} <= exposed
            return ModelResponse(
                parts=[
                    ToolCallPart(f"{name}_{suffix}", arguments)
                    for name in ("alpha", "beta")
                ]
            )
        return ModelResponse(parts=[TextPart("done")])

    result = await Agent(
        FunctionModel(model_function), capabilities=capabilities
    ).run("Use both capabilities")

    assert result.output == "done"
    returns = {
        part.tool_name: part.content.replace("\r\n", "\n")
        for part in requests[-1][-1].parts
    }
    newline = "" if tool_kind == "resource" else "\n"
    assert returns == {
        f"alpha_{suffix}": f"alpha{newline}",
        f"beta_{suffix}": f"beta{newline}",
    }


@pytest.mark.anyio
async def test_stanzas_instructions_reference_registered_tools():
    path = pathlib.Path(__file__).resolve().parents[3]
    capability = _capability(path / "example" / "skills" / "stanzas")
    tools = await capability.get_toolset().get_tools(
        RunContext(deps=None, model=TestModel(), usage=RunUsage())
    )
    documented = re.findall(
        r"`([a-z_]+)(?:`|\(script=)", capability.get_instructions()
    )
    documented_tools = [
        name
        for name in documented
        if name.endswith(("read_resource", "run_script"))
    ]
    assert len(documented_tools) == 3
    assert set(documented_tools) <= tools.keys()


@pytest.mark.parametrize("capability_id", ["first", "second"])
@pytest.mark.anyio
async def test_prefixed_resource_tool_reads_own_skill(
    temp_dir, monkeypatch, capability_id
):
    capabilities = []
    for name, name_id in (("alpha", "first"), ("beta", "second")):
        path = temp_dir / name
        _write_skill(path)
        (path / "resources").mkdir()
        (path / "resources" / "shared.md").write_text(name, encoding="utf-8")
        capability = _capability(path)
        capability.id = name_id
        capability.defer_loading = False
        capabilities.append(capability)
    tool_name = f"{capability_id}_read_resource"
    model = TestModel(call_tools=[tool_name])
    monkeypatch.setattr(
        model, "gen_tool_args", lambda tool: {"path": "resources/shared.md"}
    )
    agent = Agent(model, capabilities=capabilities)

    result = await agent.run("Read the resource")

    assert json.loads(result.output) == {
        tool_name: {"first": "alpha", "second": "beta"}[capability_id]
    }


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

    # On Windows the child Python's own text-mode stdout writes '\r\n'
    # onto the pipe. Universal newlines does not undo that here: it is a
    # *text-mode* feature, and 'anyio.run_process' has no text mode --
    # it hands back bytes, which 'run_script' turns into str with
    # '.decode()', a codec call that leaves newlines untouched.
    assert output.replace("\r\n", "\n") == "stanza jabberwocky --stanza 3\n"


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
                        "test-capability_read_resource",
                        {"path": "resources/poem.md"},
                    )
                ]
            )
        return ModelResponse(parts=[TextPart("done")])

    agent = Agent(FunctionModel(model_function), capabilities=capabilities)

    result = await agent.run("Read the poem")

    assert result.output == "done"
    assert "Verse" in str(requests[-1])
