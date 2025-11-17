import asyncio
import json
import logging
import os
import struct
import sys
import typing
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import anyio
import anyio.lowlevel
import docker
from anyio import get_cancelled_exc_class
from anyio.streams.memory import MemoryObjectReceiveStream
from anyio.streams.memory import MemoryObjectSendStream
from anyio.to_thread import run_sync
from docker.errors import ImageNotFound
from docker.models.containers import Container
from mcp import types as mcp_types
from mcp.shared.message import SessionMessage
from pydantic import BaseModel
from pydantic_ai import mcp as ai_mcp
from pydantic_core import CoreSchema
from pydantic_core import core_schema

logger = logging.getLogger(__name__)


def _filter_tools(offered_tools, allowed_tools):
    if allowed_tools:
        tools = [tool for tool in offered_tools if tool.name in allowed_tools]

    else:
        tools = offered_tools

    return tools


class JSONRPCMessage:
    @staticmethod
    def model_validate_json(line: str) -> typing.Any:  # pragma: NO COVER
        return json.loads(line)


async def read_multiplexed_stream_async(sock):  # pragma: NO COVER
    """
    Reads from a Docker multiplexed socket asynchronously.
    """
    async def read_blocking(size):
        return await run_sync(sock._sock.recv, size)

    while True:
        try:
            # Read the 8-byte header in a worker thread
            header = await read_blocking(8)
            if not header:
                break

            # Unpack the stream type and payload size
            stream_type, payload_size = struct.unpack('>BxxxL', header)

            # Read the payload in a worker thread
            payload = b''
            bytes_read = 0
            while bytes_read < payload_size:
                chunk = await read_blocking(payload_size - bytes_read)
                if not chunk:
                    break
                payload += chunk
                bytes_read += len(chunk)

            yield stream_type, payload

        except (BlockingIOError, get_cancelled_exc_class()):
            break
        except Exception as e:
            print(f"Error reading from socket: {e}")
            break


class DockerServerParameters(BaseModel):  # pragma: NO COVER

    image: str
    """The image to start the container with."""

    command: str | None = None
    """The executable to run when starting the container."""

    volumes: list[str] = []
    """
    A list of volume bindings for the container.
    Format is '/path/on/host:/app/data:rw'.
    """

    env: dict[str, str] | None = None
    """
    The environment to pass to the container.
    If not specified, the result of get_default_environment() will be used.
    """

    encoding: str = "utf-8"
    """
    The text encoding used when sending/receiving messages to the server
    defaults to utf-8
    """

    encoding_error_handler: (
        typing.Literal["strict", "ignore", "replace"]
    ) = "strict"
    """
    The text encoding error handler.
    See https://docs.python.org/3/library/codecs.html#codec-base-classes for
    explanations of possible values
    """

PROCESS_TERMINATION_TIMEOUT = 10.0


@asynccontextmanager
async def docker_stdio_client(
    server: DockerServerParameters,
    errlog: typing.TextIO = sys.stderr
):  # pragma: NO COVER
    """
    Client transport for stdio over a Docker container: this will start a
    container and communicate with it over stdin/stdout.
    """
    read_stream: MemoryObjectReceiveStream[SessionMessage | Exception]
    read_stream_writer: MemoryObjectSendStream[SessionMessage | Exception]

    write_stream: MemoryObjectSendStream[SessionMessage]
    write_stream_reader: MemoryObjectReceiveStream[SessionMessage]

    read_stream_writer, read_stream = anyio.create_memory_object_stream(0)
    write_stream, write_stream_reader = anyio.create_memory_object_stream(0)

    client = docker.from_env()
    container: Container | None = None
    raw_socket = None

    # Ensure the image is available locally; if not, pull it
    # from the registry.
    try:
        # docker-py blocking calls are executed in a worker thread to avoid
        # blocking the async event loop.
        await run_sync(client.images.get, server.image)
        logger.debug("Found Docker image %s locally", server.image)
    except ImageNotFound:
        logger.info(
            "Docker image %s not found locally; pulling...",
            server.image
        )
        try:
            await run_sync(client.images.pull, server.image)
        except Exception as e:
            err = f"Failed to pull Docker image {server.image}: {e}"
            logger.exception(err)
            raise RuntimeError(err) from e
    except Exception:
        # Non-fatal: log and proceed; the subsequent run() will surface
        # errors if the image is invalid
        logger.exception(
            f"Error while checking for Docker image {server.image}"
        )

    try:
        container = client.containers.run(
            image=server.image,
            command=server.command,
            detach=True,
            stdin_open=True,
            environment=server.env,
            volumes=server.volumes,
            tty=False,
        )
        # Give the container a moment to start up its process
        await asyncio.sleep(1)

        raw_socket = container.attach_socket(
            params={'stdin': 1, 'stream': 1, 'stdout': 1, 'stderr': 1}
        )

    except Exception as e:
        if raw_socket:
            raw_socket.close()
        if container:
            container.remove(force=True)
        await read_stream.aclose()
        await write_stream.aclose()
        await read_stream_writer.aclose()
        await write_stream_reader.aclose()
        err = f"Failed to start Docker container or attach socket: {e}"
        logger.exception(err)
        raise RuntimeError(err) from e

    async def stdout_reader_task():  # pragma: NO COVER
        try:
            mvj = mcp_types.JSONRPCMessage.model_validate_json
            async with read_stream_writer:
                buffer = ""
                async for stream_type, data in read_multiplexed_stream_async(
                    raw_socket
                ):
                    if not data:
                        continue
                    if stream_type == 1:  # stdout
                        text_chunk = data.decode(
                            server.encoding,
                            errors=server.encoding_error_handler
                        )
                        lines = (buffer + text_chunk).split("\n")
                        buffer = lines.pop()

                        for line in lines:
                            if not line:
                                continue
                            try:
                                message = mvj(line)
                            except Exception as exc:
                                logger.exception(
                                    "Failed to parse JSONRPC "
                                    "message from server"
                                )
                                await read_stream_writer.send(exc)
                                continue
                            session_message = SessionMessage(message)
                            await read_stream_writer.send(session_message)
        except anyio.ClosedResourceError:
            await anyio.lowlevel.checkpoint()
        except Exception:
            logger.exception("Error in stdout_reader")

    async def stdin_writer_task():  # pragma: NO COVER
        async with write_stream_reader:
            async for session_message in write_stream_reader:
                json_data = session_message.message.model_dump_json(
                    by_alias=True,
                    exclude_none=True
                )
                encoded_data = (
                    json_data + "\n"
                ).encode(
                    server.encoding,
                    errors=server.encoding_error_handler
                )

                try:
                    await run_sync(os.write, raw_socket.fileno(), encoded_data)
                except anyio.ClosedResourceError:
                    await anyio.lowlevel.checkpoint()
                except Exception:
                    logger.exception("Error writing to stdin")
                    break

    async with anyio.create_task_group() as tg:
        tg.start_soon(stdout_reader_task)
        tg.start_soon(stdin_writer_task)
        try:
            yield read_stream, write_stream
        finally:
            if container:
                container_id = container.id
                if container_id:
                    try:
                        with anyio.fail_after(PROCESS_TERMINATION_TIMEOUT):
                            while client.containers.get(
                                container_id
                            ).status != 'exited':
                                await anyio.sleep(0.1)
                    except TimeoutError:
                        container.stop(timeout=1)
                        await anyio.sleep(1)
                    except Exception:
                        pass
                    finally:
                        container.remove(force=True)

            await read_stream.aclose()
            await write_stream.aclose()
            await read_stream_writer.aclose()
            await write_stream_reader.aclose()


class Docker_MCP_Client_Toolset(ai_mcp.MCPServer):
    def __init__(
        self,
        image: str,
        env: dict[str, str] = None,
        command: str = None,
        volumes: list[str] = None,
        allowed_tools: list[str] = None,
    ):  # pragma: NO COVER
        super().__init__()
        self.image = image
        self.env = env
        self.command = command
        self.volumes = volumes or []
        self._allowed_tools = allowed_tools or ()

    @property
    def _params(self):  # pragma: NO COVER
        return {
            "image": self.image,
            "env": self.env,
            "command": self.command,
            "volumes": self.volumes,
            "allowed_tools": self.allowed_tools,
        }

    @property
    def allowed_tools(self) -> list[str] | None:  # pragma: NO COVER
        return list(self._allowed_tools)

    async def list_tools(self) -> list[mcp_types.Tool]:  # pragma: NO COVER
        """Retrieve tools that are currently active on the server.
        Filter the tools offered by the server using our list of allowed
        tools.
        Note:
        - We don't cache tools as they might change.
        - We also don't subscribe to the server to avoid complexity.
        """
        offered_tools = await super().list_tools()
        return _filter_tools(offered_tools, self.allowed_tools)


    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        _: typing.Any,
        __: typing.Any
    ) -> CoreSchema:  # pragma: NO COVER
        return core_schema.no_info_after_validator_function(
            lambda dct: Docker_MCP_Client_Toolset(**dct),
            core_schema.typed_dict_schema(
                {
                    'image': core_schema.typed_dict_field(
                        core_schema.list_schema(
                            core_schema.str_schema()
                        )
                    ),
                    'command': core_schema.typed_dict_field(
                        core_schema.str_schema()
                    ),
                    'env': core_schema.typed_dict_field(
                        core_schema.dict_schema(
                            core_schema.str_schema(),
                            core_schema.str_schema()
                        ),
                        required=False,
                    ),
                }
            ),
        )

    @asynccontextmanager
    async def client_streams(
        self,
    ) -> AsyncIterator[
        tuple[
            MemoryObjectReceiveStream[SessionMessage | Exception],
            MemoryObjectSendStream[SessionMessage],
        ]
    ]:  # pragma: NO COVER
        server = DockerServerParameters(
            image=self.image,
            command=self.command,
            env=self.env
        )
        async with docker_stdio_client(server=server) as (
            read_stream,
            write_stream
        ):
            yield read_stream, write_stream

    def __repr__(self) -> str:  # pragma: NO COVER
        repr_args = [
            f'image={self.image!r}',
            f'command={self.command!r}',
        ]
        if self.id:
            repr_args.append(f'id={self.id!r}')  # pragma: lax no cover
        return f'{self.__class__.__name__}({", ".join(repr_args)})'

    def __eq__(self, value: object, /) -> bool:  # pragma: NO COVER
        return (
            super().__eq__(value)
            and isinstance(value, Docker_MCP_Client_Toolset)
            and self.image == value.image
            and self.env == value.env
        )


class Stdio_MCP_Client_Toolset(ai_mcp.MCPServerStdio):
    def __init__(
        self,
        command: str,
        args: list[str],
        env: dict[str, str],
        allowed_tools: list[str] = None,
    ):  # pragma: NO COVER
        super().__init__(command=command, args=args, env=env)
        self._allowed_tools = allowed_tools or ()

    @property
    def _params(self):
        return {
            "command": self.command,
            "args": self.args,
            "env": self.env,
            "allowed_tools": self.allowed_tools,
        }

    @property
    def allowed_tools(self) -> list[str] | None:  # pragma: NO COVER
        return list(self._allowed_tools)

    async def list_tools(self) -> list[mcp_types.Tool]:  # pragma: NO COVER
        """Retrieve tools that are currently active on the server.

        Filter the tools offered by the server using our list of allowed
        tools.

        Note:
        - We don't cache tools as they might change.
        - We also don't subscribe to the server to avoid complexity.
        """
        offered_tools = await super().list_tools()
        return _filter_tools(offered_tools, self.allowed_tools)


class HTTP_MCP_Client_Toolset(ai_mcp.MCPServerStreamableHTTP):
    def __init__(
        self,
        url: str,
        headers: dict[str, typing.Any],
        allowed_tools: list[str] = None,
    ):  # pragma: NO COVER
        super().__init__(url=url, headers=headers)
        self._allowed_tools = allowed_tools or ()

    @property
    def _params(self):
        return {
            "url": self.url,
            "headers": self.headers,
            "allowed_tools": self.allowed_tools,
        }

    @property
    def allowed_tools(self) -> list[str] | None:  # pragma: NO COVER
        return list(self._allowed_tools)

    async def list_tools(self) -> list[mcp_types.Tool]:  # pragma: NO COVER
        """Retrieve tools that are currently active on the server.

        Filter the tools offered by the server using our list of allowed
        tools.

        Note:
        - We don't cache tools as they might change.
        - We also don't subscribe to the server to avoid complexity.
        """
        offered_tools = await super().list_tools()
        return _filter_tools(offered_tools, self.allowed_tools)


TOOLSET_CLASS_BY_KIND = {
    "stdio": Stdio_MCP_Client_Toolset,
    "docker": Docker_MCP_Client_Toolset,
    "http": HTTP_MCP_Client_Toolset,
}
