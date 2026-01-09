import base64
import io

import fastapi
from fastapi import responses
from fastapi import security
from haiku.rag import client as rag_client

from soliplex import authn
from soliplex import authz as authz_package
from soliplex import installation
from soliplex import mcp_auth
from soliplex import models
from soliplex import util

router = fastapi.APIRouter(tags=["rooms"])

depend_the_installation = installation.depend_the_installation
depend_the_room_authz = authz_package.depend_the_room_authz


@util.logfire_span("GET /v1/rooms")
@router.get("/v1/rooms", summary="Get available rooms")
async def get_rooms(
    request: fastapi.Request,
    the_installation: installation.Installation = depend_the_installation,
    the_room_authz: authz_package.RoomAuthorization = depend_the_room_authz,
    token: security.HTTPAuthorizationCredentials = authn.oauth2_predicate,
) -> models.ConfiguredRooms:
    """Return a manifest of the rooms available to the user"""
    user = authn.authenticate(the_installation, token)
    room_configs = await the_installation.get_room_configs(
        user=user,
        the_room_authz=the_room_authz,
    )

    def _key(item):
        key, value = item
        return value.sort_key

    rc_items = sorted(room_configs.items(), key=_key)

    return {
        room_id: models.Room.from_config(room) for room_id, room in rc_items
    }


@util.logfire_span("GET /v1/rooms/{room_id}")
@router.get("/v1/rooms/{room_id}")
async def get_room(
    request: fastapi.Request,
    room_id: str,
    the_installation: installation.Installation = depend_the_installation,
    the_room_authz: authz_package.RoomAuthorization = depend_the_room_authz,
    token: security.HTTPAuthorizationCredentials = authn.oauth2_predicate,
) -> models.Room:
    """Return a single room's configuration"""
    user = authn.authenticate(the_installation, token)

    try:
        room_config = await the_installation.get_room_config(
            room_id=room_id,
            user=user,
            the_room_authz=the_room_authz,
        )
    except KeyError:
        raise fastapi.HTTPException(
            status_code=404,
            detail=f"No such room: {room_id}",
        ) from None

    return models.Room.from_config(room_config)


@util.logfire_span("GET /v1/rooms/{room_id}/bg_image")
@router.get(
    "/v1/rooms/{room_id}/bg_image",
    response_class=responses.FileResponse,
)
async def get_room_bg_image(
    request: fastapi.Request,
    room_id: str,
    the_installation: installation.Installation = depend_the_installation,
    the_room_authz: authz_package.RoomAuthorization = depend_the_room_authz,
    token: security.HTTPAuthorizationCredentials = authn.oauth2_predicate,
) -> str:  # file path, converted to file response by FastAPI
    """Return a room's background image"""
    user = authn.authenticate(the_installation, token)

    try:
        room_config = await the_installation.get_room_config(
            room_id=room_id,
            user=user,
            the_room_authz=the_room_authz,
        )
    except KeyError:
        raise fastapi.HTTPException(
            status_code=404,
            detail=f"No such room: {room_id}",
        ) from None

    logo_image = room_config.get_logo_image()

    if logo_image is None:
        raise fastapi.HTTPException(
            status_code=404,
            detail="No image for room",
        )

    return str(logo_image)


@util.logfire_span("GET /v1/rooms/{room_id}/mcp_token")
@router.get("/v1/rooms/{room_id}/mcp_token")
async def get_room_mcp_token(
    request: fastapi.Request,
    room_id: str,
    the_installation: installation.Installation = depend_the_installation,
    the_room_authz: authz_package.RoomAuthorization = depend_the_room_authz,
    token: security.HTTPAuthorizationCredentials = authn.oauth2_predicate,
) -> models.MCPToken:
    """Return a token for use in an MCP client addressing the room"""
    user = authn.authenticate(the_installation, token)

    try:
        _room_config = await the_installation.get_room_config(
            room_id=room_id,
            user=user,
            the_room_authz=the_room_authz,
        )
    except ValueError as e:
        raise fastapi.HTTPException(
            status_code=404,
            detail=str(e),
        ) from None

    secret = the_installation.get_secret("URL_SAFE_TOKEN_SECRET")
    token = mcp_auth.generate_url_safe_token(secret, room_id, **user)
    return models.MCPToken(room_id=room_id, mcp_token=token)


@util.logfire_span("GET /v1/rooms/{room_id}/documents")
@router.get("/v1/rooms/{room_id}/documents")
async def get_room_documents(
    request: fastapi.Request,
    room_id: str,
    the_installation: installation.Installation = depend_the_installation,
    the_room_authz: authz_package.RoomAuthorization = depend_the_room_authz,
    token: security.HTTPAuthorizationCredentials = authn.oauth2_predicate,
) -> models.RoomDocuments:
    """Return a list of the documents in the room's RAG database"""
    user = authn.authenticate(the_installation, token)

    try:
        room_config = await the_installation.get_room_config(
            room_id=room_id,
            user=user,
            the_room_authz=the_room_authz,
        )
    except KeyError:
        raise fastapi.HTTPException(
            status_code=404,
            detail=f"No such room: {room_id}",
        ) from None

    document_set = {}

    for tool_config in room_config.tool_configs.values():
        hr_config = getattr(tool_config, "haiku_rag_config", None)

        if hr_config is not None:
            hr_client_kw = {
                "db_path": tool_config.rag_lancedb_path,
                "config": hr_config,
            }

            async with rag_client.HaikuRAG(**hr_client_kw) as rag:
                results = await rag.list_documents()

            for document in results:
                document_set[document.id] = models.RAGDocument(
                    id=document.id,
                    uri=document.uri,
                    title=document.title,
                    metadata=document.metadata,
                    created_at=document.created_at,
                    updated_at=document.updated_at,
                )

    return models.RoomDocuments(
        room_id=room_id,
        document_set=document_set,
    )


@util.logfire_span("GET /v1/rooms/{room_id}/chunk/{chunk_id}")
@router.get("/v1/rooms/{room_id}/chunk/{chunk_id}")
async def get_chunk_visualization(
    request: fastapi.Request,
    room_id: str,
    chunk_id: str,
    the_installation: installation.Installation = depend_the_installation,
    the_room_authz: authz_package.RoomAuthorization = depend_the_room_authz,
    token: security.HTTPAuthorizationCredentials = authn.oauth2_predicate,
) -> models.ChunkVisualization:
    """Return a set of page images for a chunk, highlighting the chunk text"""
    user = authn.authenticate(the_installation, token)

    try:
        room_config = await the_installation.get_room_config(
            room_id=room_id,
            user=user,
            the_room_authz=the_room_authz,
        )
    except KeyError:
        raise fastapi.HTTPException(
            status_code=404,
            detail=f"No such room: {room_id}",
        ) from None

    images = None

    for tool_config in room_config.tool_configs.values():
        hr_config = getattr(tool_config, "haiku_rag_config", None)

        if hr_config is not None:
            hr_client_kw = {
                "db_path": tool_config.rag_lancedb_path,
                "config": hr_config,
            }

            async with rag_client.HaikuRAG(**hr_client_kw) as rag:
                chunk = await rag.chunk_repository.get_by_id(chunk_id)

                if not chunk:
                    raise fastapi.HTTPException(
                        status_code=404, detail=f"Chunk not found: {chunk_id}"
                    ) from None

                images = await rag.visualize_chunk(chunk)

            break

    # Convert PIL images to base64
    base64_images = []

    if not images:
        raise fastapi.HTTPException(
            status_code=404, detail=f"Chunk images not available: {chunk_id}"
        ) from None

    for img in images:
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        base64_images.append(base64.b64encode(buffer.read()).decode("utf-8"))

    return models.ChunkVisualization(
        chunk_id=chunk_id,
        document_uri=chunk.document_uri,
        images_base_64=base64_images,
    )
