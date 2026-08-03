import base64
import io
import json

import fastapi
from fastapi import responses
from haiku.rag import client as hr_client
from haiku.rag.store.models import chunk as hr_chunk

from soliplex import authn
from soliplex import authz
from soliplex import installation
from soliplex import loggers
from soliplex import mcp_auth
from soliplex import models
from soliplex import util
from soliplex import views

router = fastapi.APIRouter(tags=["rooms"])

depend_the_installation = installation.depend_the_installation
depend_the_room_authz = views.depend_the_room_authz_policy
depend_the_user_claims = views.depend_the_user_claims
depend_the_logger = views.depend_the_logger


@util.logfire_span("GET /v1/rooms")
@router.get("/v1/rooms", summary="Get available rooms")
async def get_rooms(
    the_installation: installation.Installation = depend_the_installation,
    the_room_authz: authz.RoomAuthorizationPolicy = depend_the_room_authz,
    the_user_claims: authn.UserClaims = depend_the_user_claims,
    the_logger: loggers.LogWrapper = depend_the_logger,
) -> models.ConfiguredRooms:
    """Return a manifest of the rooms available to the user"""
    the_logger.debug(loggers.ROOM_GET_ROOMS)

    room_configs = await the_installation.get_room_configs(
        user=the_user_claims,
        the_room_authz=the_room_authz,
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
    the_room_authz: authz.RoomAuthorizationPolicy = depend_the_room_authz,
    the_user_claims: authn.UserClaims = depend_the_user_claims,
    the_logger: loggers.LogWrapper = depend_the_logger,
) -> models.Room:
    """Return a single room's configuration"""
    the_logger.debug(loggers.ROOM_GET_ROOM)

    try:
        room_config = await the_installation.get_room_config(
            room_id=room_id,
            user=the_user_claims,
            the_room_authz=the_room_authz,
            the_logger=the_logger,
        )
    except KeyError:
        # auth error logged in 'get_room_config'
        # but this could be just a missing room
        the_logger.exception(loggers.ROOM_UNKNOWN_ROOM_ID, room_id=room_id)
        raise fastapi.HTTPException(
            status_code=404,
            detail=f"{loggers.ROOM_UNKNOWN_ROOM_ID}: {room_id}",
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
    the_room_authz: authz.RoomAuthorizationPolicy = depend_the_room_authz,
    the_user_claims: authn.UserClaims = depend_the_user_claims,
    the_logger: loggers.LogWrapper = depend_the_logger,
) -> str:  # file path, converted to file response by FastAPI
    """Return a room's background image"""
    the_logger.debug(loggers.ROOM_GET_ROOM_BG_IMAGE)

    try:
        room_config = await the_installation.get_room_config(
            room_id=room_id,
            user=the_user_claims,
            the_room_authz=the_room_authz,
            the_logger=the_logger,
        )
    except KeyError:
        # auth error logged in 'get_room_config'
        # but this could be just a missing room
        the_logger.exception(loggers.ROOM_UNKNOWN_ROOM_ID, room_id=room_id)
        raise fastapi.HTTPException(
            status_code=404,
            detail=f"{loggers.ROOM_UNKNOWN_ROOM_ID}: {room_id}",
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
    the_room_authz: authz.RoomAuthorizationPolicy = depend_the_room_authz,
    the_user_claims: authn.UserClaims = depend_the_user_claims,
    the_logger: loggers.LogWrapper = depend_the_logger,
) -> models.MCPToken:
    """Return a token for use in an MCP client addressing the room"""
    the_logger.debug(loggers.ROOM_GET_ROOM_MCP_TOKEN)

    try:
        _room_config = await the_installation.get_room_config(
            room_id=room_id,
            user=the_user_claims,
            the_room_authz=the_room_authz,
            the_logger=the_logger,
        )
    except KeyError:
        # auth error logged in 'get_room_config'
        # but this could be just a missing room
        the_logger.exception(loggers.ROOM_UNKNOWN_ROOM_ID, room_id=room_id)
        raise fastapi.HTTPException(
            status_code=404,
            detail=f"{loggers.ROOM_UNKNOWN_ROOM_ID}: {room_id}",
        ) from None

    secret = the_installation.get_secret("URL_SAFE_TOKEN_SECRET")
    mcp_token = mcp_auth.generate_url_safe_token(
        secret,
        room_id,
        **the_user_claims,
    )
    return models.MCPToken(room_id=room_id, mcp_token=mcp_token)


@util.logfire_span("GET /v1/rooms/{room_id}/documents")
@router.get("/v1/rooms/{room_id}/documents")
async def get_room_documents(
    room_id: str,
    the_installation: installation.Installation = depend_the_installation,
    the_room_authz: authz.RoomAuthorizationPolicy = depend_the_room_authz,
    the_user_claims: authn.UserClaims = depend_the_user_claims,
    the_logger: loggers.LogWrapper = depend_the_logger,
) -> models.RoomRAGDocuments:
    """Return a list of the documents in the room's RAG database"""
    the_logger.debug(loggers.ROOM_GET_ROOM_DOCUMENTS)

    try:
        room_config = await the_installation.get_room_config(
            room_id=room_id,
            user=the_user_claims,
            the_room_authz=the_room_authz,
            the_logger=the_logger,
        )
    except KeyError:
        # auth error logged in 'get_room_config'
        # but this could be just a missing room
        the_logger.exception(loggers.ROOM_UNKNOWN_ROOM_ID, room_id=room_id)
        raise fastapi.HTTPException(
            status_code=404,
            detail=f"{loggers.ROOM_UNKNOWN_ROOM_ID}: {room_id}",
        ) from None

    audit = loggers.RAGAccessAuditLog(claims=the_user_claims, room_id=room_id)
    document_set = {}

    for hr_client_kw in room_config.list_haiku_rag_client_kw(
        include_source=True,
    ):
        source_tag = hr_client_kw.pop("source")
        source = models.RAGSource.from_source_tag(source_tag)
        db_path = str(hr_client_kw["db_path"])

        async with hr_client.HaikuRAG(**hr_client_kw) as rag:
            results = await rag.list_documents()

        audit.doc_list(db_path, [document.id for document in results])

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
    refs: str | None = None,
    expand: bool = False,
    the_installation: installation.Installation = depend_the_installation,
    the_room_authz: authz.RoomAuthorizationPolicy = depend_the_room_authz,
    the_user_claims: authn.UserClaims = depend_the_user_claims,
    the_logger: loggers.LogWrapper = depend_the_logger,
) -> models.ChunkVisualization:
    """Return a set of page images for a chunk, highlighting the chunk text.

    ``refs`` is an optional JSON-encoded list of the citation's
    ``doc_item_refs`` (the exact items the model saw); when given, the
    highlight matches the cited content instead of re-expanding. ``expand``
    (default true) re-expands the chunk's section when no refs are supplied;
    ``expand=false`` highlights only the chunk itself.
    """
    the_logger.debug(loggers.ROOM_GET_CHUNK_VISUALIZATION)

    doc_item_refs: list[str] | None = None
    if refs:
        try:
            parsed = json.loads(refs)
        except ValueError:
            parsed = None
        if isinstance(parsed, list):
            doc_item_refs = [str(r) for r in parsed]

    try:
        room_config = await the_installation.get_room_config(
            room_id=room_id,
            user=the_user_claims,
            the_room_authz=the_room_authz,
            the_logger=the_logger,
        )
    except KeyError:
        # auth error logged in 'get_room_config'
        # but this could be just a missing room
        the_logger.exception(loggers.ROOM_UNKNOWN_ROOM_ID, room_id=room_id)
        raise fastapi.HTTPException(
            status_code=404,
            detail=f"{loggers.ROOM_UNKNOWN_ROOM_ID}: {room_id}",
        ) from None

    audit = loggers.RAGAccessAuditLog(claims=the_user_claims, room_id=room_id)
    images = None
    for hr_client_kw in room_config.list_haiku_rag_client_kw(
        include_source=True,
    ):
        source_tag = hr_client_kw.pop("source")
        source = models.RAGSource.from_source_tag(source_tag)
        db_path = str(hr_client_kw["db_path"])

        async with hr_client.HaikuRAG(**hr_client_kw) as rag:
            chunk = await rag.chunk_repository.get_by_id(chunk_id)

            if chunk:
                images = await rag.visualize_chunk(
                    chunk, refs=doc_item_refs, expand=expand
                )
                break  # first hit wins

    else:
        the_logger.error(loggers.ROOM_UNKNOWN_CHUNK_ID, chunk_id=chunk_id)
        audit.chunk_viz_failed(None, chunk_id, loggers.ROOM_UNKNOWN_CHUNK_ID)
        raise fastapi.HTTPException(
            status_code=404,
            detail=f"{loggers.ROOM_UNKNOWN_CHUNK_ID}: {chunk_id}",
        ) from None

    # Convert PIL images to base64
    base64_images = []

    if not images:
        the_logger.error(
            loggers.ROOM_CHUNK_IMAGES_NOT_AVAILALBE,
            chunk_id=chunk_id,
        )
        audit.chunk_viz_failed(
            db_path, chunk_id, loggers.ROOM_CHUNK_IMAGES_NOT_AVAILALBE
        )
        raise fastapi.HTTPException(
            status_code=404,
            detail=f"{loggers.ROOM_CHUNK_IMAGES_NOT_AVAILALBE}: {chunk_id}",
        ) from None

    for img in images:
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        base64_images.append(base64.b64encode(buffer.read()).decode("utf-8"))

    audit.chunk_viz(db_path, chunk_id, [chunk.document_uri])

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
    search_type: hr_chunk.SearchType = "hybrid",
    the_installation: installation.Installation = depend_the_installation,
    the_room_authz: authz.RoomAuthorizationPolicy = depend_the_room_authz,
    the_user_claims: authn.UserClaims = depend_the_user_claims,
    the_logger: loggers.LogWrapper = depend_the_logger,
) -> models.SearchResults:
    """Return a set of page images for a chunk, highlighting the chunk text"""
    the_logger.debug(loggers.ROOM_GET_SEARCH)

    try:
        room_config = await the_installation.get_room_config(
            room_id=room_id,
            user=the_user_claims,
            the_room_authz=the_room_authz,
            the_logger=the_logger,
        )
    except KeyError:
        # auth error logged in 'get_room_config'
        # but this could be just a missing room
        the_logger.exception(loggers.ROOM_UNKNOWN_ROOM_ID, room_id=room_id)
        raise fastapi.HTTPException(
            status_code=404,
            detail=f"{loggers.ROOM_UNKNOWN_ROOM_ID}: {room_id}",
        ) from None

    audit = loggers.RAGAccessAuditLog(claims=the_user_claims, room_id=room_id)
    aggregate_hits = []

    for hr_client_kw in room_config.list_haiku_rag_client_kw(
        include_source=True,
    ):
        source_tag = hr_client_kw.pop("source")
        source = models.RAGSource.from_source_tag(source_tag)
        db_path = str(hr_client_kw["db_path"])

        async with hr_client.HaikuRAG(**hr_client_kw) as rag:
            hits = await rag.search(
                query=query,
                search_type=search_type,
            )

        audit.search(db_path, query, [hit.chunk_id for hit in hits])

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
                    document_meta=hit.document_meta,
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
