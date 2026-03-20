import pathlib

from haiku.skills import SkillMetadata
from pydantic import ValidationError

AVAILABLE_TOOLS: set[str] = {
    "list_documents",
    "get_document",
    "search",
    "ask",
    "research",
}


def validate_metadata(name: str, description: str) -> None:
    try:
        SkillMetadata(name=name, description=description)
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc
    if not name.isidentifier():
        raise ValueError(  # noqa: TRY003
            f"{name!r} is not a valid Python identifier"
        )


def validate_tools(tools: list[str]) -> None:
    if not tools:
        raise ValueError(  # noqa: TRY003
            "tools must contain at least one tool"
        )
    unknown = set(tools) - AVAILABLE_TOOLS
    if unknown:
        raise ValueError(  # noqa: TRY003
            f"Unknown tools: {', '.join(sorted(unknown))}."
            f" Available: {', '.join(sorted(AVAILABLE_TOOLS))}"
        )


def validate_db_path(db_path: pathlib.Path) -> None:
    if not db_path.exists():
        raise ValueError(  # noqa: TRY003
            f"db_path does not exist: {db_path}"
        )
    if not db_path.is_dir():
        raise ValueError(  # noqa: TRY003
            f"db_path is not a directory: {db_path}"
        )


def validate_output_dir(output_dir: pathlib.Path, name: str) -> None:
    if not output_dir.exists():
        raise ValueError(  # noqa: TRY003
            f"output_dir does not exist: {output_dir}"
        )
    target = output_dir / f"soliplex-skill-{name}"
    if target.exists():
        raise ValueError(  # noqa: TRY003
            f"Target directory already exists: {target}"
        )
