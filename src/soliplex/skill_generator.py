import pathlib
import shutil

from cookiecutter.main import cookiecutter
from haiku.skills import SkillMetadata
from pydantic import ValidationError

_TEMPLATE_DIR = pathlib.Path(__file__).parent / "templates" / "skill"

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


def render_template(
    output_dir: pathlib.Path,
    name: str,
    description: str,
    tool_names: list[str],
) -> pathlib.Path:
    result = cookiecutter(
        str(_TEMPLATE_DIR),
        no_input=True,
        output_dir=str(output_dir),
        extra_context={
            "name": name,
            "description": description,
            "tool_names": " ".join(tool_names),
        },
    )
    result_path = pathlib.Path(result)

    # Remove tool modules not in the selected tool set
    pkg_dir = result_path / f"soliplex_skill_{name}"
    for module in pkg_dir.glob("_*.py"):
        if module.name == "__init__.py":
            continue
        if module.stem.lstrip("_") not in tool_names:
            module.unlink()

    return result_path


def generate_skill(
    db_path: pathlib.Path,
    output_dir: pathlib.Path,
    name: str,
    description: str,
    tool_names: list[str],
    rag_config: pathlib.Path | None = None,
) -> pathlib.Path:
    validate_metadata(name, description)
    validate_tools(tool_names)
    validate_db_path(db_path)
    validate_output_dir(output_dir, name)

    result = render_template(
        output_dir=output_dir,
        name=name,
        description=description,
        tool_names=tool_names,
    )

    assets_dir = result / f"soliplex_skill_{name}" / "assets"
    shutil.copytree(db_path, assets_dir / f"{name}.lancedb")

    if rag_config is not None:
        shutil.copy2(rag_config, assets_dir / "haiku.rag.yaml")

    return result
