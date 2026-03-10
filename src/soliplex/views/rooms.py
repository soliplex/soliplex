import base64
import io

import fastapi
from fastapi import responses
from haiku.rag import client as rag_client

from soliplex import authn
from soliplex import authz as authz_package
from soliplex import installation
from soliplex import loggers
from soliplex import mcp_auth
from soliplex import models
from soliplex import util
from soliplex import views
from soliplex.config import rooms as config_rooms

router = fastapi.APIRouter(tags=["rooms"])

depend_the_installation = installation.depend_the_installation
depend_the_authz = authz_package.depend_the_authz_policy
depend_the_user_claims = views.depend_the_user_claims
depend_the_logger = views.depend_the_logger


@util.logfire_span("GET /v1/rooms")
@router.get("/v1/rooms", summary="Get available rooms")
async def get_rooms(
    request: fastapi.Request,
    the_installation: installation.Installation = depend_the_installation,
    the_authz_policy: authz_package.AuthorizationPolicy = depend_the_authz,
    the_user_claims: authn.UserClaims = depend_the_user_claims,
    the_logger: loggers.LogWrapper = depend_the_logger,
) -> models.ConfiguredRooms:
    """Return a manifest of the rooms available to the user"""
    the_logger.debug(loggers.ROOM_GET_ROOMS)

    room_configs = await the_installation.get_room_configs(
        user=the_user_claims,
        the_authz_policy=the_authz_policy,
        the_logger=the_logger,
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
    the_authz_policy: authz_package.AuthorizationPolicy = depend_the_authz,
    the_user_claims: authn.UserClaims = depend_the_user_claims,
    the_logger: loggers.LogWrapper = depend_the_logger,
) -> models.Room:
    """Return a single room's configuration"""
    the_logger.debug(loggers.ROOM_GET_ROOM)

    try:
        room_config = await the_installation.get_room_config(
            room_id=room_id,
            user=the_user_claims,
            the_authz_policy=the_authz_policy,
            the_logger=the_logger,
        )
    except KeyError:
        # auth error logged in 'get_room_config'
        # but this could be just a missing room
        the_logger.exception(loggers.ROOM_UNKNOWN_ROOM_ID, room_id)
        raise fastapi.HTTPException(
            status_code=404,
            detail=loggers.ROOM_UNKNOWN_ROOM_ID % room_id,
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
    the_authz_policy: authz_package.AuthorizationPolicy = depend_the_authz,
    the_user_claims: authn.UserClaims = depend_the_user_claims,
    the_logger: loggers.LogWrapper = depend_the_logger,
) -> str:  # file path, converted to file response by FastAPI
    """Return a room's background image"""
    the_logger.debug(loggers.ROOM_GET_ROOM_BG_IMAGE)

    try:
        room_config = await the_installation.get_room_config(
            room_id=room_id,
            user=the_user_claims,
            the_authz_policy=the_authz_policy,
            the_logger=the_logger,
        )
    except KeyError:
        # auth error logged in 'get_room_config'
        # but this could be just a missing room
        the_logger.exception(loggers.ROOM_UNKNOWN_ROOM_ID, room_id)
        raise fastapi.HTTPException(
            status_code=404,
            detail=loggers.ROOM_UNKNOWN_ROOM_ID % room_id,
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
    the_authz_policy: authz_package.AuthorizationPolicy = depend_the_authz,
    the_user_claims: authn.UserClaims = depend_the_user_claims,
    the_logger: loggers.LogWrapper = depend_the_logger,
) -> models.MCPToken:
    """Return a token for use in an MCP client addressing the room"""
    the_logger.debug(loggers.ROOM_GET_ROOM_MCP_TOKEN)

    try:
        _room_config = await the_installation.get_room_config(
            room_id=room_id,
            user=the_user_claims,
            the_authz_policy=the_authz_policy,
            the_logger=the_logger,
        )
    except KeyError:
        # auth error logged in 'get_room_config'
        # but this could be just a missing room
        the_logger.exception(loggers.ROOM_UNKNOWN_ROOM_ID, room_id)
        raise fastapi.HTTPException(
            status_code=404,
            detail=loggers.ROOM_UNKNOWN_ROOM_ID % room_id,
        ) from None

    secret = the_installation.get_secret("URL_SAFE_TOKEN_SECRET")
    mcp_token = mcp_auth.generate_url_safe_token(
        secret,
        room_id,
        **the_user_claims,
    )
    return models.MCPToken(room_id=room_id, mcp_token=mcp_token)


def _get_haiku_rag_client_kw(room_config: config_rooms.RoomConfig):
    candidates = (
        [room_config.agent_config]
        + list(room_config.tool_configs.values())
        + list(room_config.skills.skill_configs.values())
    )

    for cfg in candidates:
        hr_config = getattr(cfg, "haiku_rag_config", None)

        if hr_config is not None:
            return {
                "db_path": cfg.rag_lancedb_path,
                "config": hr_config,
                "read_only": True,
            }


@util.logfire_span("GET /v1/rooms/{room_id}/documents")
@router.get("/v1/rooms/{room_id}/documents")
async def get_room_documents(
    request: fastapi.Request,
    room_id: str,
    the_installation: installation.Installation = depend_the_installation,
    the_authz_policy: authz_package.AuthorizationPolicy = depend_the_authz,
    the_user_claims: authn.UserClaims = depend_the_user_claims,
    the_logger: loggers.LogWrapper = depend_the_logger,
) -> models.RoomDocuments:
    """Return a list of the documents in the room's RAG database"""
    the_logger.debug(loggers.ROOM_GET_ROOM_DOCUMENTS)

    try:
        room_config = await the_installation.get_room_config(
            room_id=room_id,
            user=the_user_claims,
            the_authz_policy=the_authz_policy,
            the_logger=the_logger,
        )
    except KeyError:
        # auth error logged in 'get_room_config'
        # but this could be just a missing room
        the_logger.exception(loggers.ROOM_UNKNOWN_ROOM_ID, room_id)
        raise fastapi.HTTPException(
            status_code=404,
            detail=loggers.ROOM_UNKNOWN_ROOM_ID % room_id,
        ) from None

    document_set = {}
    hr_client_kw = _get_haiku_rag_client_kw(room_config)

    if hr_client_kw is not None:
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
    the_authz_policy: authz_package.AuthorizationPolicy = depend_the_authz,
    the_user_claims: authn.UserClaims = depend_the_user_claims,
    the_logger: loggers.LogWrapper = depend_the_logger,
) -> models.ChunkVisualization:
    """Return a set of page images for a chunk, highlighting the chunk text"""
    the_logger.debug(loggers.ROOM_GET_CHUNK_VISUALIZATION)

    try:
        room_config = await the_installation.get_room_config(
            room_id=room_id,
            user=the_user_claims,
            the_authz_policy=the_authz_policy,
            the_logger=the_logger,
        )
    except KeyError:
        # auth error logged in 'get_room_config'
        # but this could be just a missing room
        the_logger.exception(loggers.ROOM_UNKNOWN_ROOM_ID, room_id)
        raise fastapi.HTTPException(
            status_code=404,
            detail=loggers.ROOM_UNKNOWN_ROOM_ID % room_id,
        ) from None

    images = None
    hr_client_kw = _get_haiku_rag_client_kw(room_config)

    if hr_client_kw is not None:
        async with rag_client.HaikuRAG(**hr_client_kw) as rag:
            chunk = await rag.chunk_repository.get_by_id(chunk_id)

            if not chunk:
                the_logger.error(
                    loggers.ROOM_UNKNOWN_CHUNK_ID,
                    chunk_id,
                )
                raise fastapi.HTTPException(
                    status_code=404,
                    detail=loggers.ROOM_UNKNOWN_CHUNK_ID % chunk_id,
                ) from None

            images = await rag.visualize_chunk(chunk)

    # Convert PIL images to base64
    base64_images = []

    if not images:
        the_logger.error(loggers.ROOM_CHUNK_IMAGES_NOT_AVAILALBE, chunk_id)
        raise fastapi.HTTPException(
            status_code=404,
            detail=loggers.ROOM_CHUNK_IMAGES_NOT_AVAILALBE % chunk_id,
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
