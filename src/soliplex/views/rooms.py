import base64
import io
import json
import os
import pathlib
import stat
from urllib import parse as url_parse

import fastapi
from docling_core.types.doc import base as docling_base
from docling_core.types.doc import document as docling_document
from fastapi import responses
from haiku.rag import client as hr_client
from haiku.rag import uri as hr_uri
from haiku.rag.store.models import chunk as hr_chunk

from soliplex import authn
from soliplex import authz
from soliplex import installation
from soliplex import loggers
from soliplex import models
from soliplex import token_mint
from soliplex import util
from soliplex import views
from soliplex.config import exceptions as config_exc

router = fastapi.APIRouter(tags=["rooms"])

depend_the_admin_users = views.depend_the_admin_user_policy
depend_the_installation = installation.depend_the_installation
depend_the_room_authz = views.depend_the_room_authz_policy
depend_the_user_claims = views.depend_the_user_claims
depend_the_logger = views.depend_the_logger


@util.logfire_span("GET /v1/rooms")
@router.get("/v1/rooms", summary="Get available rooms")
async def get_rooms(
    the_installation: installation.Installation = depend_the_installation,
    the_admin_users: authz.AdminUserPolicy = depend_the_admin_users,
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

    is_admin = await the_admin_users.is_admin(the_user_claims)

    async def _user_has_write(room_id, room):
        return is_admin or await the_room_authz.has_room_permission(
            room_id=room_id,
            user_token=the_user_claims,
            permission=authz.Permission.WRITE,
        )

    return {
        room_id: models.Room.from_config(room).model_copy(
            update={"user_has_write": await _user_has_write(room_id, room)}
        )
        for room_id, room in rc_items
    }


@util.logfire_span("GET /v1/rooms/{room_id}")
@router.get("/v1/rooms/{room_id}")
async def get_room(
    room_id: str,
    the_installation: installation.Installation = depend_the_installation,
    the_admin_users: authz.AdminUserPolicy = depend_the_admin_users,
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

    user_has_write = await the_admin_users.is_admin(
        the_user_claims
    ) or await the_room_authz.has_room_permission(
        room_id=room_id,
        user_token=the_user_claims,
        permission=authz.Permission.WRITE,
    )

    return models.Room.from_config(room_config).model_copy(
        update={"user_has_write": user_has_write},
    )


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

    try:
        logo_image = room_config.get_logo_image()
    except config_exc.PathNotLocal:
        the_logger.exception(loggers.ROOM_BG_IMAGE_NOT_LOCAL, room_id=room_id)
        logo_image = None

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
    mcp_token = token_mint.generate_url_safe_token(
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
        db_path = hr_client_kw.pop("audit_db_path")

        async with hr_client.HaikuRAG(**hr_client_kw) as rag:
            results = await rag.list_documents()

        audit.doc_list(db_path, [document.id for document in results])

        for document in results:
            document_set[document.id] = models.RAGDocument(
                source=source,
                database=document.source,
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


async def _find_chunk(rag, chunk_id: str, database: str | None = None):
    """Return a chunk and the name of the database holding it

    Chunk IDs repeat between copies of a database, so 'database' names the
    one to ask; without it the covered databases are asked in turn and the
    first holding the ID wins.
    """
    for covered in rag.source_names:
        if database is not None and covered != database:
            continue

        chunk = await rag.get_chunk_by_id(chunk_id, source=covered)

        if chunk:
            return chunk, covered

    return None, None


@util.logfire_span("GET /v1/rooms/{room_id}/chunk/{chunk_id}")
@router.get("/v1/rooms/{room_id}/chunk/{chunk_id}")
async def get_chunk_visualization(
    room_id: str,
    chunk_id: str,
    refs: str | None = None,
    expand: bool = False,
    database: str | None = None,
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
    ``expand=false`` highlights only the chunk itself. ``database`` names the
    haiku.rag database the chunk came from, as a citation reports it.
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
        db_path = hr_client_kw.pop("audit_db_path")

        async with hr_client.HaikuRAG(**hr_client_kw) as rag:
            chunk, chunk_database = await _find_chunk(rag, chunk_id, database)

            if chunk:
                images = await rag.visualize_chunk(
                    chunk,
                    refs=doc_item_refs,
                    expand=expand,
                    source=chunk_database,
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
        database=chunk_database,
        chunk_id=chunk_id,
        document_uri=chunk.document_uri,
        images_base_64=base64_images,
    )


PDF_MAGIC = b"%PDF-"
PDF_CHUNKSIZE = 64 * 1024
MAX_BOXES_CHUNK_IDS = 50


async def _room_config_or_404(
    room_id: str, the_installation, the_room_authz, the_user_claims, the_logger
):
    try:
        return await the_installation.get_room_config(
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


async def _find_document(rag, document_id: str, database: str | None = None):
    """Return a document and the name of the database holding it

    As '_find_chunk': 'database' names the one to ask; without it the
    covered databases are asked in turn and the first holding the ID wins.
    """
    for covered in rag.source_names:
        if database is not None and covered != database:
            continue

        document = await rag.get_document_by_id(document_id, source=covered)

        if document:
            return document, covered

    return None, None


class _UnservablePDF(Exception):
    """The document's file is not a regular file holding a PDF"""

    def __init__(self):
        super().__init__("Not a regular file holding a PDF")


def _original_pdf_path(document) -> pathlib.Path | None:
    """Return where the document's original PDF is on this server's disk

    haiku.rag keeps page images but not the original file, so this is the
    path the document was ingested from; None when it was not ingested
    from a local file.
    """
    try:
        path = hr_uri.uri_to_path(document.uri)
    except ValueError:
        return None

    return path if path.is_absolute() else None


def _check_pdf(fd: int) -> os.stat_result:
    """Return the stat of 'fd', a regular file starting with the PDF header"""
    st = os.fstat(fd)

    if not stat.S_ISREG(st.st_mode):
        raise _UnservablePDF

    if os.pread(fd, len(PDF_MAGIC), 0) != PDF_MAGIC:
        raise _UnservablePDF

    return st


def _open_pdf(path: pathlib.Path) -> tuple[int, int]:
    """Open 'path' and return its fd and size

    The path is the one the document was ingested from, recorded by
    whoever built the database, so it is not confined to a root; but it
    must name a regular file, not through a final symlink, starting with
    the PDF header.
    """
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)

    try:
        st = _check_pdf(fd)
    except BaseException:
        os.close(fd)
        raise

    return fd, st.st_size


def _stream_fd(fd: int):
    """Return a generator streaming 'fd', which it then owns"""

    def _stream():
        with os.fdopen(fd, "rb") as fh:
            while chunk := fh.read(PDF_CHUNKSIZE):
                yield chunk

    return _stream()


@util.logfire_span("GET /v1/rooms/{room_id}/documents/{document_id}/file")
@router.get("/v1/rooms/{room_id}/documents/{document_id}/file")
async def get_room_document_file(
    room_id: str,
    document_id: str,
    database: str | None = None,
    the_installation: installation.Installation = depend_the_installation,
    the_room_authz: authz.RoomAuthorizationPolicy = depend_the_room_authz,
    the_user_claims: authn.UserClaims = depend_the_user_claims,
    the_logger: loggers.LogWrapper = depend_the_logger,
) -> responses.StreamingResponse:
    """Return the original PDF of a document in the room's RAG database.

    ``database`` names the haiku.rag database the document came from, as a
    citation reports it.

    Raises:

    - 'fastapi.HTTPException' (404) when the room or document is unknown,
      when the document was not ingested from a file on this server, or
      when that file is gone, is not a regular file, or is not a PDF.
    """
    the_logger.debug(loggers.ROOM_GET_DOCUMENT_FILE)

    room_config = await _room_config_or_404(
        room_id, the_installation, the_room_authz, the_user_claims, the_logger
    )

    audit = loggers.RAGAccessAuditLog(claims=the_user_claims, room_id=room_id)

    for hr_client_kw in room_config.list_haiku_rag_client_kw(
        include_source=True,
    ):
        hr_client_kw.pop("source")
        db_path = hr_client_kw.pop("audit_db_path")

        async with hr_client.HaikuRAG(**hr_client_kw) as rag:
            document, _ = await _find_document(rag, document_id, database)

        if document:
            break  # first hit wins

    else:
        the_logger.error(
            loggers.ROOM_UNKNOWN_DOCUMENT_ID, document_id=document_id
        )
        audit.doc_file_failed(
            None, document_id, loggers.ROOM_UNKNOWN_DOCUMENT_ID
        )
        raise fastapi.HTTPException(
            status_code=404,
            detail=f"{loggers.ROOM_UNKNOWN_DOCUMENT_ID}: {document_id}",
        )

    def _unavailable(reason: str):
        the_logger.error(reason, document_id=document_id)
        audit.doc_file_failed(db_path, document_id, reason)
        return fastapi.HTTPException(
            status_code=404,
            detail=f"{reason}: {document_id}",
        )

    path = _original_pdf_path(document)

    if path is None:
        raise _unavailable(loggers.ROOM_DOCUMENT_NOT_LOCAL)

    try:
        fd, size = _open_pdf(path)
    except (OSError, _UnservablePDF):
        raise _unavailable(loggers.ROOM_DOCUMENT_FILE_UNAVAILABLE) from None

    audit.doc_file(db_path, document_id, [document.uri])

    filename = url_parse.quote(path.name, safe="")

    return responses.StreamingResponse(
        _stream_fd(fd),
        media_type="application/pdf",
        headers={
            "content-length": str(size),
            "content-disposition": f"inline; filename*=UTF-8''{filename}",
            "x-content-type-options": "nosniff",
        },
    )


def _provenances(docling_doc, refs: list[str]):
    """Yield the provenance of each item 'refs' name, in order

    Refs that resolve to no item, and items without provenance, are
    skipped, as haiku.rag's own resolver skips them.
    """
    for ref in refs:
        try:
            item = docling_document.RefItem.model_validate(
                {"$ref": ref}
            ).resolve(docling_doc)
        except Exception:  # noqa: BLE001, S112 - as haiku.rag's resolver
            continue

        yield from getattr(item, "prov", None) or []


def _top_left_pages(docling_doc, refs: list[str]) -> set[int]:
    """Return the pages on which a box of 'refs' has a top-left origin"""
    return {
        prov.page_no
        for prov in _provenances(docling_doc, refs)
        if prov.bbox.coord_origin != docling_base.CoordOrigin.BOTTOMLEFT
    }


def _item_boxes(
    docling_doc, refs: list[str], page_heights: dict[int, float]
) -> list[models.PassageBox]:
    """Return the boxes of the items 'refs' name, bottom-left origin

    A box with a top-left origin is converted using its page's height from
    'page_heights', and skipped when that is unknown.
    """
    boxes = []

    for prov in _provenances(docling_doc, refs):
        bbox = prov.bbox

        if bbox.coord_origin != docling_base.CoordOrigin.BOTTOMLEFT:
            height = page_heights.get(prov.page_no)

            if height is None:
                continue

            bbox = bbox.to_bottom_left_origin(height)

        boxes.append(
            models.PassageBox(
                page=prov.page_no,
                left=bbox.l,
                top=bbox.t,
                right=bbox.r,
                bottom=bbox.b,
            )
        )

    return boxes


async def _page_heights(owner, document_id: str, pages: set[int]):
    """Return the heights of 'pages', loading them only when there are any"""
    if not pages:
        return {}

    pages_doc = await owner.document_repository.get_pages_data(document_id)

    if pages_doc is None:
        return {}

    return {
        page_no: page.size.height
        for page_no, page in pages_doc.get_page_images(sorted(pages)).items()
    }


def _parse_context_refs(context_refs: str | None) -> list[str]:
    if not context_refs:
        return []

    try:
        parsed = json.loads(context_refs)
    except ValueError:
        parsed = None

    if not isinstance(parsed, list) or not all(
        isinstance(ref, str) for ref in parsed
    ):
        raise fastapi.HTTPException(
            status_code=422,
            detail=loggers.ROOM_INVALID_CONTEXT_REFS,
        )

    return parsed


async def _cited_chunks(rag, document_id, chunk_ids, database):
    """Return the chunks named, and the database holding them all

    The first covered database holding the first chunk is the one asked
    for the rest; each must be there and belong to 'document_id'.
    """
    first, covered = await _find_chunk(rag, chunk_ids[0], database)

    if first is None:
        return None, None

    chunks = [first]

    for chunk_id in chunk_ids[1:]:
        chunks.append(await rag.get_chunk_by_id(chunk_id, source=covered))

    if any(
        chunk is None or chunk.document_id != document_id for chunk in chunks
    ):
        return None, None

    return chunks, covered


@util.logfire_span("GET /v1/rooms/{room_id}/documents/{document_id}/boxes")
@router.get("/v1/rooms/{room_id}/documents/{document_id}/boxes")
async def get_room_document_boxes(
    room_id: str,
    document_id: str,
    chunk_ids: list[str] = fastapi.Query(),  # noqa: B008 - FastAPI idiom
    context_refs: str | None = None,
    database: str | None = None,
    the_installation: installation.Installation = depend_the_installation,
    the_room_authz: authz.RoomAuthorizationPolicy = depend_the_room_authz,
    the_user_claims: authn.UserClaims = depend_the_user_claims,
    the_logger: loggers.LogWrapper = depend_the_logger,
) -> models.DocumentBoxes:
    """Return the boxes of a citation's passage in its document's pages.

    ``chunk_ids`` (repeated) are the citation's chunks: every one in a
    citation that merged several hits.  Their own items are the 'anchor'.
    ``context_refs`` is an optional JSON-encoded list of the citation's
    ``doc_item_refs`` (the expanded context the model read); those not in
    the anchor are the 'context'.  ``database`` names the haiku.rag
    database, as a citation reports it.
    """
    the_logger.debug(loggers.ROOM_GET_DOCUMENT_BOXES)

    chunk_ids = list(dict.fromkeys(chunk_ids))

    if not 0 < len(chunk_ids) <= MAX_BOXES_CHUNK_IDS:
        raise fastapi.HTTPException(
            status_code=422,
            detail=loggers.ROOM_INVALID_CHUNK_IDS,
        )

    refs = _parse_context_refs(context_refs)

    room_config = await _room_config_or_404(
        room_id, the_installation, the_room_authz, the_user_claims, the_logger
    )

    audit = loggers.RAGAccessAuditLog(claims=the_user_claims, room_id=room_id)
    docling_doc = None

    for hr_client_kw in room_config.list_haiku_rag_client_kw(
        include_source=True,
    ):
        source_tag = hr_client_kw.pop("source")
        source = models.RAGSource.from_source_tag(source_tag)
        db_path = hr_client_kw.pop("audit_db_path")

        async with hr_client.HaikuRAG(**hr_client_kw) as rag:
            chunks, chunks_database = await _cited_chunks(
                rag, document_id, chunk_ids, database
            )

            if chunks:
                (owner,) = await rag.clients_covering([chunks_database])
                repository = owner.document_repository
                stored = await repository.get_docling_data(document_id)

                if stored is not None:
                    docling_doc = stored.get_docling_document()

                anchor_refs = list(
                    dict.fromkeys(
                        ref
                        for chunk in chunks
                        for ref in chunk.get_chunk_metadata().doc_item_refs
                    )
                )
                context_refs_only = [
                    ref for ref in refs if ref not in set(anchor_refs)
                ]

                if docling_doc is not None:
                    page_heights = await _page_heights(
                        owner,
                        document_id,
                        _top_left_pages(
                            docling_doc, anchor_refs + context_refs_only
                        ),
                    )

                break  # first hit wins

    else:
        the_logger.error(loggers.ROOM_UNKNOWN_CHUNK_ID, chunk_ids=chunk_ids)
        audit.doc_boxes_failed(None, chunk_ids, loggers.ROOM_UNKNOWN_CHUNK_ID)
        raise fastapi.HTTPException(
            status_code=404,
            detail=f"{loggers.ROOM_UNKNOWN_CHUNK_ID}: {', '.join(chunk_ids)}",
        )

    if docling_doc is None:
        the_logger.error(
            loggers.ROOM_DOCUMENT_BOXES_NOT_AVAILABLE, document_id=document_id
        )
        audit.doc_boxes_failed(
            db_path, chunk_ids, loggers.ROOM_DOCUMENT_BOXES_NOT_AVAILABLE
        )
        raise fastapi.HTTPException(
            status_code=404,
            detail=(
                f"{loggers.ROOM_DOCUMENT_BOXES_NOT_AVAILABLE}: {document_id}"
            ),
        )

    audit.doc_boxes(db_path, chunk_ids, [document_id])

    return models.DocumentBoxes(
        source=source,
        database=chunks_database,
        document_id=document_id,
        anchor=_item_boxes(docling_doc, anchor_refs, page_heights),
        context=_item_boxes(docling_doc, context_refs_only, page_heights),
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
        db_path = hr_client_kw.pop("audit_db_path")

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
                    database=hit.source,
                    content=hit.content,
                    score=hit.score,
                    chunk_id=hit.chunk_id,
                    document_id=hit.document_id,
                    document_uri=hit.document_uri,
                    document_title=hit.document_title,
                    document_meta=hit.document_meta,
                    # A chunk with no heading metadata has no headings.
                    headings=hit.headings or [],
                    page_numbers=hit.page_numbers,
                    labels=hit.labels,
                )
            )

    return models.SearchResults(
        query=query,
        search_type=search_type,
        hits=aggregate_hits,
    )
