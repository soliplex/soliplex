"""Routes serving a RAG document of a room: its PDF and its passage boxes"""

import asyncio
import json
import pathlib
import typing
from urllib import parse as url_parse

import fastapi
import pydantic
from docling_core.types.doc import base as docling_base
from docling_core.types.doc import document as docling_document
from fastapi import responses
from haiku.rag import client as hr_client
from haiku.rag.utils import images as hr_images

from soliplex import authn
from soliplex import authz
from soliplex import installation
from soliplex import loggers
from soliplex import models
from soliplex import util
from soliplex import views
from soliplex.views import rooms as rooms_views

router = fastapi.APIRouter(tags=["rooms"])

depend_the_installation = installation.depend_the_installation
depend_the_room_authz = views.depend_the_room_authz_policy
depend_the_user_claims = views.depend_the_user_claims
depend_the_logger = views.depend_the_logger

PDF_MAGIC = b"%PDF-"
MAX_BOXES_CHUNK_IDS = 50


async def _find_document(rag, document_id: str, database: str | None = None):
    """Return a document and the name of the database holding it

    As 'rooms.find_chunk': 'database' names the one to ask; without it the
    covered databases are asked in turn and the first holding the ID wins.
    """
    for covered in rag.source_names:
        if database is not None and covered != database:
            continue

        document = await rag.get_document_by_id(document_id, source=covered)

        if document:
            return document, covered

    return None, None


def _download_name(document) -> str:
    """Return the name to offer the document's PDF under

    The last segment of the path the document was ingested from, or its ID
    when that path names no file.
    """
    path = url_parse.unquote(url_parse.urlsplit(document.uri or "").path)
    return pathlib.PurePosixPath(path).name or f"{document.id}.pdf"


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
) -> responses.Response:
    """Return the original PDF of a document in the room's RAG database.

    The PDF is the original haiku.rag stored when it ingested the document.
    ``database`` names the haiku.rag database the document came from, as a
    citation reports it.

    Raises:

    - 'fastapi.HTTPException' (404) when the room or document is unknown,
      when no original is stored for the document (it was ingested before
      haiku.rag 0.113 and its database not rebuilt with '--originals'), or
      when the original is not a PDF.
    """
    the_logger.debug(loggers.ROOM_GET_DOCUMENT_FILE)

    room_config = await rooms_views.room_config_or_404(
        room_id, the_installation, the_room_authz, the_user_claims, the_logger
    )

    audit = loggers.RAGAccessAuditLog(claims=the_user_claims, room_id=room_id)

    for hr_client_kw in room_config.list_haiku_rag_client_kw(
        include_source=True,
    ):
        hr_client_kw.pop("source")
        db_path = hr_client_kw.pop("audit_db_path")

        async with hr_client.HaikuRAG(**hr_client_kw) as rag:
            document, covered = await _find_document(
                rag, document_id, database
            )

            if document:
                (owner,) = await rag.clients_covering([covered])
                original = await owner.document_repository.get_original(
                    document_id
                )
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

    if original is None:
        raise _unavailable(loggers.ROOM_DOCUMENT_ORIGINAL_NOT_STORED)

    if not original.startswith(PDF_MAGIC):
        raise _unavailable(loggers.ROOM_DOCUMENT_NOT_PDF)

    audit.doc_file(db_path, document_id, [document.uri])

    filename = url_parse.quote(_download_name(document), safe="")

    return responses.Response(
        original,
        media_type="application/pdf",
        headers={
            "content-disposition": f"inline; filename*=UTF-8''{filename}",
            "x-content-type-options": "nosniff",
        },
    )


def _provenances(docling_doc, refs: list[str]):
    """Yield the provenance of each item 'refs' name, in order

    Refs that resolve to no item, and items without provenance, are
    skipped, as haiku.rag's own resolver skips them.  A ref the client sent
    can be malformed ('ValidationError') or well-formed and still name no
    item: 'resolve' then raises 'IndexError' ('#/texts/99'),
    'AttributeError' ('#/bogus/0') or 'RuntimeError' ('#').
    """
    for ref in refs:
        try:
            item = docling_document.RefItem.model_validate(
                {"$ref": ref}
            ).resolve(docling_doc)
        except (
            pydantic.ValidationError,
            IndexError,
            AttributeError,
            RuntimeError,
        ):
            pass
        else:
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
    boxes = (
        _prov_box(prov, page_heights)
        for prov in _provenances(docling_doc, refs)
    )
    return [models.PassageBox(**box) for box in boxes if box is not None]


def _prov_box(prov, page_heights: dict[int, float]) -> dict | None:
    """Return the fields of a box for 'prov', bottom-left origin

    A box with a top-left origin is converted using its page's height from
    'page_heights'; None when that is unknown.
    """
    bbox = prov.bbox

    if bbox.coord_origin != docling_base.CoordOrigin.BOTTOMLEFT:
        height = page_heights.get(prov.page_no)

        if height is None:
            return None

        bbox = bbox.to_bottom_left_origin(height)

    return {
        "page": prov.page_no,
        "left": bbox.l,
        "top": bbox.t,
        "right": bbox.r,
        "bottom": bbox.b,
    }


async def _page_heights(owner, document_id: str, docling_doc, pages: set[int]):
    """Return the heights of 'pages'

    The structure sizes the pages of a document ingested since haiku.rag
    0.113; for any it does not, the stored original is measured.  Pages
    neither knows are left out.
    """
    heights = {
        page_no: docling_doc.pages[page_no].size.height
        for page_no in pages
        if page_no in docling_doc.pages
    }
    unsized = pages - heights.keys()

    if not unsized:
        return heights

    original = await owner.document_repository.get_original(document_id)

    if original is None:
        return heights

    layout = await asyncio.to_thread(hr_images.original_layout, original)

    for page_no in unsized:
        if page_no in layout.sizes:
            heights[page_no] = layout.sizes[page_no][1]

    return heights


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
    first, covered = await rooms_views.find_chunk(rag, chunk_ids[0], database)

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
    chunk_ids: typing.Annotated[list[str], fastapi.Query()],
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

    room_config = await rooms_views.room_config_or_404(
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
                anchor_refs_set = set(anchor_refs)
                context_refs_only = [
                    ref for ref in refs if ref not in anchor_refs_set
                ]

                if docling_doc is not None:
                    page_heights = await _page_heights(
                        owner,
                        document_id,
                        docling_doc,
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


def _text_parts(docling_doc):
    """Yield (provenance, label, text) for each part of the document's text

    Items come in reading order, page furniture (running headers, footers)
    included, pictures left out.  A table's text is its Markdown.

    A text item spanning pages yields a part per page, holding what its
    character span names there.  The spans index 'orig', the text as read
    off the page, not 'text', which docling may have cleaned up (joining a
    word hyphenated across lines, say), so the parts are taken from 'orig'.
    A page whose span is empty yields nothing.  An item that cannot be
    split so (a table, or a text item none of whose spans is set) yields
    its whole text once, on its first page.
    """
    layers = {
        docling_document.ContentLayer.BODY,
        docling_document.ContentLayer.FURNITURE,
    }

    for item, _ in docling_doc.iterate_items(included_content_layers=layers):
        if isinstance(item, docling_document.TextItem):
            text = item.text
        elif isinstance(item, docling_document.TableItem):
            text = item.export_to_markdown(docling_doc)
        else:
            continue

        provs = item.prov or []
        parts = []

        if len(provs) > 1 and isinstance(item, docling_document.TextItem):
            parts = [
                (prov, item.orig[start:end])
                for prov in provs
                for start, end in [prov.charspan]
                if start < end
            ]

        if not parts:
            parts = [(prov, text) for prov in provs[:1]]

        for prov, part in parts:
            if part.strip():
                yield prov, item.label.value, part


@util.logfire_span("GET /v1/rooms/{room_id}/documents/{document_id}/text")
@router.get("/v1/rooms/{room_id}/documents/{document_id}/text")
async def get_room_document_text(
    room_id: str,
    document_id: str,
    database: str | None = None,
    the_installation: installation.Installation = depend_the_installation,
    the_room_authz: authz.RoomAuthorizationPolicy = depend_the_room_authz,
    the_user_claims: authn.UserClaims = depend_the_user_claims,
    the_logger: loggers.LogWrapper = depend_the_logger,
) -> models.DocumentText:
    """Return a document's text as docling read it, block by block.

    For a scanned PDF this is the text OCR recovered at ingestion, which a
    viewer can offer where the PDF has none.  ``database`` names the
    haiku.rag database, as a citation reports it.

    Raises:

    - 'fastapi.HTTPException' (404) when the room or document is unknown,
      or the document has no docling data.
    """
    the_logger.debug(loggers.ROOM_GET_DOCUMENT_TEXT)

    room_config = await rooms_views.room_config_or_404(
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
            document, covered = await _find_document(
                rag, document_id, database
            )

            if document:
                (owner,) = await rag.clients_covering([covered])
                stored = await owner.document_repository.get_docling_data(
                    document_id
                )

                if stored is not None:
                    docling_doc = stored.get_docling_document()

                if docling_doc is not None:
                    parts = list(_text_parts(docling_doc))
                    page_heights = await _page_heights(
                        owner,
                        document_id,
                        docling_doc,
                        {
                            prov.page_no
                            for prov, _, _ in parts
                            if prov.bbox.coord_origin
                            != docling_base.CoordOrigin.BOTTOMLEFT
                        },
                    )

                break  # first hit wins

    else:
        the_logger.error(
            loggers.ROOM_UNKNOWN_DOCUMENT_ID, document_id=document_id
        )
        audit.doc_text_failed(
            None, document_id, loggers.ROOM_UNKNOWN_DOCUMENT_ID
        )
        raise fastapi.HTTPException(
            status_code=404,
            detail=f"{loggers.ROOM_UNKNOWN_DOCUMENT_ID}: {document_id}",
        )

    if docling_doc is None:
        the_logger.error(
            loggers.ROOM_DOCUMENT_TEXT_NOT_AVAILABLE, document_id=document_id
        )
        audit.doc_text_failed(
            db_path, document_id, loggers.ROOM_DOCUMENT_TEXT_NOT_AVAILABLE
        )
        raise fastapi.HTTPException(
            status_code=404,
            detail=(
                f"{loggers.ROOM_DOCUMENT_TEXT_NOT_AVAILABLE}: {document_id}"
            ),
        )

    audit.doc_text(db_path, document_id, [document.uri])

    blocks = []

    for prov, label, text in parts:
        box = _prov_box(prov, page_heights)

        if box is not None:
            blocks.append(models.TextBlock(**box, text=text, label=label))

    return models.DocumentText(
        source=source,
        database=covered,
        document_id=document_id,
        blocks=blocks,
    )
