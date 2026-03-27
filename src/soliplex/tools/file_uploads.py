"""Tools for managing files uploaded to an AGUI thread"""

import pathlib

import pydantic_ai

from soliplex import agents


class UploadsPathNotConfigured(ValueError):
    def __init__(self):
        super().__init__(
            "'SOLIPLEX_UPLOADS_PATH' not configured "
            "in installation environment"
        )


class UploadsPathNotADirectory(ValueError):
    def __init__(self, uploads_dir):
        self.uploads_dir = uploads_dir
        super().__init__(f"Uploads path not a directory: {uploads_dir}")


async def list_thread_file_uploads(
    ctx: pydantic_ai.RunContext[agents.AgentDependencies],
) -> list[str]:
    """List names of files uploaded to the current thread"""
    the_installation = ctx.deps.the_installation
    thread_id = ctx.deps.thread_id
    uploads_dir = the_installation.get_environment("SOLIPLEX_UPLOADS_PATH")

    if uploads_dir is None:
        raise UploadsPathNotConfigured()

    uploads_dir = pathlib.Path(uploads_dir)

    if not uploads_dir.is_dir():
        raise UploadsPathNotADirectory(uploads_dir)

    thread_dir = uploads_dir / thread_id

    return [sub.name for sub in thread_dir.glob("*") if sub.is_file()]
