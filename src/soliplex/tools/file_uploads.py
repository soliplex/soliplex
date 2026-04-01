"""Tools for managing files uploaded to an AGUI thread"""

import pydantic_ai

from soliplex import agents


class UploadsPathNotConfigured(ValueError):
    def __init__(self, which):
        self.which = which
        super().__init__(
            f"'{which}s_upload_path' not configured for installation"
        )


class UploadsPathNotADirectory(ValueError):
    def __init__(self, which, uploads_path):
        self.which = which
        self.uploads_path = uploads_path
        super().__init__(
            f"'{which}s_upload_path' not a directory: {uploads_path}"
        )


class UploadNotFound(ValueError):
    def __init__(self, which, filename):
        self.which = which
        self.filename = filename
        super().__init__(f"Upload not found in {which}: {filename}")


async def list_room_file_uploads(
    ctx: pydantic_ai.RunContext[agents.AgentDependencies],
) -> list[str]:
    """List names of files uploaded to the current room"""
    the_installation = ctx.deps.the_installation
    room_id = ctx.deps.room_id
    uploads_path = the_installation.rooms_upload_path

    if uploads_path is None:
        raise UploadsPathNotConfigured("room")

    if not uploads_path.is_dir():
        raise UploadsPathNotADirectory("room", uploads_path)

    room_dir = uploads_path / room_id

    return [sub.name for sub in room_dir.glob("*") if sub.is_file()]


async def get_room_file_upload(
    ctx: pydantic_ai.RunContext[agents.AgentDependencies],
    filename: str,
) -> bytes:
    """Get contents of a files uploaded to the current room

    Args:
      filename (str, required):
        the name of the uploaded file whose content is to be returned.
    """
    the_installation = ctx.deps.the_installation
    room_id = ctx.deps.room_id
    uploads_path = the_installation.rooms_upload_path

    if uploads_path is None:
        raise UploadsPathNotConfigured("room")

    if not uploads_path.is_dir():
        raise UploadsPathNotADirectory("room", uploads_path)

    room_dir = uploads_path / room_id
    file_path = room_dir / filename

    if not file_path.exists():
        raise UploadNotFound("room", filename)

    try:
        return file_path.read_text(errors="strict")
    except ValueError:
        return file_path.read_bytes()


async def list_thread_file_uploads(
    ctx: pydantic_ai.RunContext[agents.AgentDependencies],
) -> list[str]:
    """List names of files uploaded to the current thread"""
    the_installation = ctx.deps.the_installation
    thread_id = ctx.deps.thread_id
    uploads_path = the_installation.threads_upload_path

    if uploads_path is None:
        raise UploadsPathNotConfigured("thread")

    if not uploads_path.is_dir():
        raise UploadsPathNotADirectory("thread", uploads_path)

    thread_dir = uploads_path / thread_id

    return [sub.name for sub in thread_dir.glob("*") if sub.is_file()]


async def get_thread_file_upload(
    ctx: pydantic_ai.RunContext[agents.AgentDependencies],
    filename: str,
) -> bytes:
    """Get contents of a files uploaded to the current thread

    Args:
      filename (str, required):
        the name of the uploaded file whose content is to be returned.
    """
    the_installation = ctx.deps.the_installation
    thread_id = ctx.deps.thread_id
    uploads_path = the_installation.threads_upload_path

    if uploads_path is None:
        raise UploadsPathNotConfigured("thread")

    if not uploads_path.is_dir():
        raise UploadsPathNotADirectory("thread", uploads_path)

    thread_dir = uploads_path / thread_id
    file_path = thread_dir / filename

    if not file_path.exists():
        raise UploadNotFound("thread", filename)

    try:
        return file_path.read_text(errors="strict")
    except ValueError:
        return file_path.read_bytes()
