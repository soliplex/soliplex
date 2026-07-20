import pathlib

import pytest
from pydantic_ai import Agent
from pydantic_ai.messages import ModelResponse
from pydantic_ai.messages import TextPart
from pydantic_ai.messages import ToolCallPart
from pydantic_ai.models.function import FunctionModel

from soliplex.capabilities import FilesystemCapabilityError
from soliplex.capabilities import discover_filesystem_capabilities


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

    capabilities, errors = discover_filesystem_capabilities([path])

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

    capabilities, errors = discover_filesystem_capabilities([temp_dir])

    assert errors == []
    assert [capability.id for capability in capabilities] == ["alpha", "beta"]


def test_discover_missing_path(temp_dir):
    path = temp_dir / "missing"

    capabilities, errors = discover_filesystem_capabilities([path])

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

    capabilities, errors = discover_filesystem_capabilities([path])

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

    capabilities, errors = discover_filesystem_capabilities([path])

    assert capabilities == []
    assert "unreadable" in str(errors[0])


@pytest.mark.anyio
async def test_capability_uses_native_deferred_loading(temp_dir):
    path = temp_dir / "test-capability"
    _write_skill(path)
    capabilities, _ = discover_filesystem_capabilities([path])
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
    error = FilesystemCapabilityError("bad", temp_dir)

    assert error.path == temp_dir
    assert str(error) == "bad"
