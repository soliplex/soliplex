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
    hr_client_kws = list(room_config.list_haiku_rag_client_kw())

    if hr_client_kws:
        return hr_client_kws[0]
    else:
        return None


@util.logfire_span("GET /v1/rooms/{room_id}/documents")
@router.get("/v1/rooms/{room_id}/documents")
async def get_room_documents(
    room_id: str,
    the_installation: installation.Installation = depend_the_installation,
    the_authz_policy: authz_package.AuthorizationPolicy = depend_the_authz,
    the_user_claims: authn.UserClaims = depend_the_user_claims,
    the_logger: loggers.LogWrapper = depend_the_logger,
) -> models.RoomRAGDocuments:
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

    for hr_client_kw in room_config.list_haiku_rag_client_kw(
        include_source=True,
    ):
        source_tag = hr_client_kw.pop("source")
        source = models.RAGSource.from_source_tag(source_tag)

        async with rag_client.HaikuRAG(**hr_client_kw) as rag:
            results = await rag.list_documents()

        for document in results:
            document_set[document.id] = models.RAGDocument(
                source=source,
                id=document.id,
                uri=document.uri,
                title=document.title,
                metadata=document.metadata,
                created_at=document.created_at,
                updated_at=document.updated_at,
            )

    return models.RoomRAGDocuments(
        room_id=room_id,
        document_set=document_set,
    )


@util.logfire_span("GET /v1/rooms/{room_id}/chunk/{chunk_id}")
@router.get("/v1/rooms/{room_id}/chunk/{chunk_id}")
async def get_chunk_visualization(
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
    for hr_client_kw in room_config.list_haiku_rag_client_kw():
        source_tag = hr_client_kw.pop("source")
        source = models.RAGSource.from_source_tag(source_tag)

        async with rag_client.HaikuRAG(**hr_client_kw) as rag:
            chunk = await rag.chunk_repository.get_by_id(chunk_id)

            if chunk:
                images = await rag.visualize_chunk(chunk)
                break  # first hit wins

    else:
        the_logger.error(loggers.ROOM_UNKNOWN_CHUNK_ID, chunk_id)
        raise fastapi.HTTPException(
            status_code=404,
            detail=loggers.ROOM_UNKNOWN_CHUNK_ID % chunk_id,
        ) from None

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
        source=source,
        chunk_id=chunk_id,
        document_uri=chunk.document_uri,
        images_base_64=base64_images,
    )


@util.logfire_span("GET /v1/rooms/{room_id}/search")
@router.get("/v1/rooms/{room_id}/search")
async def get_search(
    query: str,
    room_id: str,
    search_type: models.SearchType = "hybrid",
    the_installation: installation.Installation = depend_the_installation,
    the_authz_policy: authz_package.AuthorizationPolicy = depend_the_authz,
    the_user_claims: authn.UserClaims = depend_the_user_claims,
    the_logger: loggers.LogWrapper = depend_the_logger,
) -> models.SearchResults:
    """Return a set of page images for a chunk, highlighting the chunk text"""
    the_logger.debug(loggers.ROOM_GET_SEARCH)

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

    aggregate_hits = []

    for hr_client_kw in room_config.list_haiku_rag_client_kw(
        include_source=True,
    ):
        source_tag = hr_client_kw.pop("source")
        source = models.RAGSource.from_source_tag(source_tag)

        async with rag_client.HaikuRAG(**hr_client_kw) as rag:
            hits = await rag.search(
                query=query,
                search_type=search_type,
            )

        for hit in hits:
            aggregate_hits.append(
                models.SearchHit(
                    source=source,
                    content=hit.content,
                    score=hit.score,
                    chunk_id=hit.chunk_id,
                    document_id=hit.document_id,
                    document_uri=hit.document_uri,
                    document_title=hit.document_title,
                    headings=hit.headings,
                    page_numbers=hit.page_numbers,
                    labels=hit.labels,
                )
            )

    return models.SearchResults(
        query=query,
        search_type=search_type,
        hits=aggregate_hits,
    )
