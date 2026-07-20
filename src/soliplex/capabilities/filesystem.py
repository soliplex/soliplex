import dataclasses
import pathlib
import re
import typing

import pydantic
import yaml
from pydantic_ai import capabilities as ai_capabilities

_SKILL_FILENAME = "SKILL.md"
_FRONTMATTER_DELIMITER = "---"
_NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class FilesystemCapabilityError(ValueError):
    """A malformed filesystem capability and the path that defined it."""

    def __init__(self, message: str, path: pathlib.Path):
        self.path = path
        super().__init__(message)


class _CapabilityMetadata(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="ignore")

    name: typing.Annotated[str, pydantic.Field(min_length=1, max_length=64)]
    description: typing.Annotated[
        str,
        pydantic.Field(min_length=1, max_length=1024),
    ]

    @pydantic.field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not _NAME_PATTERN.fullmatch(value):
            raise ValueError(  # noqa: TRY003
                "name must contain lowercase letters, numbers, and single "
                "hyphens only"
            )
        return value


@dataclasses.dataclass
class FilesystemCapability(ai_capabilities.AbstractCapability[typing.Any]):
    """Deferred instructions loaded from an Agent Skills ``SKILL.md`` file."""

    instructions: str
    path: pathlib.Path

    def get_instructions(self) -> str:
        return self.instructions


def _parse_skill_file(
    skill_path: pathlib.Path,
) -> FilesystemCapability:
    skill_file = skill_path / _SKILL_FILENAME
    try:
        text = skill_file.read_text(encoding="utf-8")
    except OSError as exc:
        raise FilesystemCapabilityError(str(exc), skill_path) from exc

    lines = text.splitlines()
    if not lines or lines[0].strip() != _FRONTMATTER_DELIMITER:
        raise FilesystemCapabilityError(  # noqa: TRY003
            f"{_SKILL_FILENAME} must start with YAML frontmatter",
            skill_path,
        )

    try:
        end = next(
            index
            for index, line in enumerate(lines[1:], start=1)
            if line.strip() == _FRONTMATTER_DELIMITER
        )
    except StopIteration as exc:
        raise FilesystemCapabilityError(  # noqa: TRY003
            f"{_SKILL_FILENAME} has no closing frontmatter delimiter",
            skill_path,
        ) from exc

    try:
        metadata = _CapabilityMetadata.model_validate(
            yaml.safe_load("\n".join(lines[1:end])) or {}
        )
    except (pydantic.ValidationError, yaml.YAMLError) as exc:
        raise FilesystemCapabilityError(str(exc), skill_path) from exc

    if metadata.name != skill_path.name:
        raise FilesystemCapabilityError(  # noqa: TRY003
            f"Capability name '{metadata.name}' does not match directory "
            f"name '{skill_path.name}'",
            skill_path,
        )

    instructions = "\n".join(lines[end + 1 :]).strip()
    if not instructions:
        raise FilesystemCapabilityError(  # noqa: TRY003
            f"{_SKILL_FILENAME} contains no instructions",
            skill_path,
        )

    return FilesystemCapability(
        id=metadata.name,
        description=metadata.description,
        defer_loading=True,
        instructions=instructions,
        path=skill_path,
    )


def discover_filesystem_capabilities(
    paths: typing.Iterable[pathlib.Path],
) -> tuple[list[FilesystemCapability], list[FilesystemCapabilityError]]:
    """Discover instruction-only capabilities below configured paths."""
    capabilities = []
    errors = []

    for path in paths:
        if not path.exists():
            errors.append(
                FilesystemCapabilityError(
                    f"Capability path does not exist: {path}",
                    path,
                )
            )
            continue

        candidates = (
            [path]
            if (path / _SKILL_FILENAME).is_file()
            else [
                child
                for child in sorted(path.iterdir())
                if not child.name.startswith(".")
                and child.is_dir()
                and (child / _SKILL_FILENAME).is_file()
            ]
        )
        for candidate in candidates:
            try:
                capabilities.append(_parse_skill_file(candidate))
            except FilesystemCapabilityError as exc:
                errors.append(exc)

    return capabilities, errors


__all__ = [
    "FilesystemCapability",
    "FilesystemCapabilityError",
    "discover_filesystem_capabilities",
]
