"""Tests for the routes serving a RAG document of a room"""

import io
import json
from unittest import mock

import fastapi
import pypdfium2
import pytest
from docling_core.types.doc import base as docling_base
from docling_core.types.doc import document as docling_document
from docling_core.types.doc import labels as docling_labels
from haiku.rag.store.models import chunk as hr_chunk
from haiku.rag.store.models import document as hr_document

from soliplex import authz
from soliplex import installation
from soliplex import loggers
from soliplex import models
from soliplex.config import rooms as config_rooms
from soliplex.views import room_documents as room_documents_views

ROOM_ID = "pdf_notes"
DOCUMENT_ID = "doc-1"
DATABASE = "field_notes"
THE_USER_CLAIMS = {"preferred_username": "phreddy"}
PDF_BYTES = b"%PDF-1.7\n" + b"x" * 100
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"x" * 100


def _rag_records(audit_records):
    return [
        record
        for record in audit_records
        if record.__dict__.get(loggers.SOLIPLEX_AUDIT_LOGGER_SCOPE_EXTRA)
        == loggers.AuditLogScopes.RAG_ACCESS
    ]


def _deps(*, w_room=True, rags=()):
    """Return the view's dependencies, over 'rags' as its databases' clients"""
    the_installation = mock.create_autospec(installation.Installation)
    room_config = mock.create_autospec(config_rooms.RoomConfig)
    room_config.list_haiku_rag_client_kw.side_effect = lambda **_: [
        {"source": "agent", "audit_db_path": f"/db/{index}", "config": None}
        for index in range(len(rags))
    ]

    if w_room:
        the_installation.get_room_config.return_value = room_config
    else:
        the_installation.get_room_config.side_effect = KeyError("testing")

    return {
        "the_installation": the_installation,
        "the_room_authz": mock.create_autospec(authz.RoomAuthorizationPolicy),
        "the_user_claims": THE_USER_CLAIMS,
        "the_logger": mock.create_autospec(loggers.LogWrapper),
    }


def _rag(*, names=(DATABASE,), documents=None, chunks=None):
    rag = mock.AsyncMock()
    rag.source_names = names
    documents = documents or {}
    chunks = chunks or {}
    rag.get_document_by_id.side_effect = lambda doc_id, source: documents.get(
        (source, doc_id)
    )
    rag.get_chunk_by_id.side_effect = lambda chunk_id, source: chunks.get(
        (source, chunk_id)
    )
    return rag


@pytest.fixture
def hr_klass():
    with mock.patch("haiku.rag.client.HaikuRAG") as klass:
        yield klass


def _use(hr_klass, rags):
    instances = [mock.AsyncMock() for _ in rags]

    for instance, rag in zip(instances, rags, strict=True):
        instance.__aenter__.return_value = rag

    hr_klass.side_effect = instances


def _document(uri):
    return hr_document.Document(id=DOCUMENT_ID, content="", uri=uri)


def _file_rag(original, *, names=(DATABASE,), uri="file:///docs/notes.pdf"):
    """Return a client holding the document, its original 'original'"""
    rag = _rag(
        names=names,
        documents={(DATABASE, DOCUMENT_ID): _document(uri)},
    )
    owner = mock.Mock()
    owner.document_repository.get_original = mock.AsyncMock(
        return_value=original
    )
    rag.clients_covering.return_value = [owner]
    return rag, owner


async def _get_file(rags, **kwargs):
    return await room_documents_views.get_room_document_file(
        room_id=ROOM_ID,
        document_id=DOCUMENT_ID,
        **({"database": None} | kwargs),
        **_deps(rags=rags),
    )


# ----------------------------------------------------------------------------
#   GET /v1/rooms/{room_id}/documents/{document_id}/file
# ----------------------------------------------------------------------------


@pytest.mark.anyio
async def test_get_room_document_file_unknown_room(hr_klass, audit_records):
    deps = _deps(w_room=False)

    with pytest.raises(fastapi.HTTPException) as exc:
        await room_documents_views.get_room_document_file(
            room_id=ROOM_ID, document_id=DOCUMENT_ID, **deps
        )

    assert exc.value.status_code == 404
    assert exc.value.detail == f"{loggers.ROOM_UNKNOWN_ROOM_ID}: {ROOM_ID}"
    assert _rag_records(audit_records) == []


@pytest.mark.anyio
@pytest.mark.parametrize("w_database", [None, "other"])
async def test_get_room_document_file_unknown_document(
    hr_klass, audit_records, w_database
):
    rags = [
        _rag(),
        _rag(
            names=(DATABASE,),
            documents={
                (DATABASE, "elsewhere"): _document("file:///notes.pdf")
            },
        ),
    ]
    _use(hr_klass, rags)

    with pytest.raises(fastapi.HTTPException) as exc:
        await _get_file(rags, database=w_database)

    assert exc.value.status_code == 404
    assert exc.value.detail == (
        f"{loggers.ROOM_UNKNOWN_DOCUMENT_ID}: {DOCUMENT_ID}"
    )
    (record,) = _rag_records(audit_records)
    assert record.action == loggers.AUDIT_RAG_ACTION_DOC_FILE
    assert record.db_path is None
    assert record.reason == loggers.ROOM_UNKNOWN_DOCUMENT_ID


@pytest.mark.anyio
@pytest.mark.parametrize("w_federated", [False, True])
async def test_get_room_document_file(hr_klass, audit_records, w_federated):
    names = ("other", DATABASE) if w_federated else (DATABASE,)
    uri = "file:///docs/field%20notes.pdf"
    rag, owner = _file_rag(PDF_BYTES, names=names, uri=uri)
    _use(hr_klass, [rag])
    deps = _deps(rags=[rag])

    response = await room_documents_views.get_room_document_file(
        room_id=ROOM_ID,
        document_id=DOCUMENT_ID,
        database=DATABASE,
        **deps,
    )

    assert response.media_type == "application/pdf"
    assert response.headers["content-length"] == str(len(PDF_BYTES))
    assert response.headers["content-disposition"] == (
        "inline; filename*=UTF-8''field%20notes.pdf"
    )
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.body == PDF_BYTES
    rag.clients_covering.assert_awaited_once_with([DATABASE])
    owner.document_repository.get_original.assert_awaited_once_with(
        DOCUMENT_ID
    )
    (record,) = _rag_records(audit_records)
    assert record.action == loggers.AUDIT_RAG_ACTION_DOC_FILE
    assert record.db_path == "/db/0"
    assert record.selector == DOCUMENT_ID
    assert record.result_refs == [uri]
    deps["the_logger"].debug.assert_called_once_with(
        loggers.ROOM_GET_DOCUMENT_FILE
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "uri, expected",
    [
        ("https://example.com/reports/q3%20notes.pdf?v=2", "q3%20notes.pdf"),
        ("s3://bucket/scans/notes.pdf", "notes.pdf"),
        ("https://example.com/", f"{DOCUMENT_ID}.pdf"),
        ("", f"{DOCUMENT_ID}.pdf"),
    ],
)
async def test_get_room_document_file_download_name(hr_klass, uri, expected):
    rag, _ = _file_rag(PDF_BYTES, uri=uri)
    _use(hr_klass, [rag])

    response = await _get_file([rag])

    assert response.headers["content-disposition"] == (
        f"inline; filename*=UTF-8''{expected}"
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "original, reason",
    [
        (None, loggers.ROOM_DOCUMENT_ORIGINAL_NOT_STORED),
        (PNG_BYTES, loggers.ROOM_DOCUMENT_NOT_PDF),
    ],
)
async def test_get_room_document_file_unavailable(
    hr_klass, audit_records, original, reason
):
    rag, _ = _file_rag(original)
    _use(hr_klass, [rag])

    with pytest.raises(fastapi.HTTPException) as exc:
        await _get_file([rag])

    assert exc.value.status_code == 404
    assert exc.value.detail == f"{reason}: {DOCUMENT_ID}"
    (record,) = _rag_records(audit_records)
    assert record.db_path == "/db/0"
    assert record.reason == reason


# ----------------------------------------------------------------------------
#   GET /v1/rooms/{room_id}/documents/{document_id}/boxes
# ----------------------------------------------------------------------------


def _bbox(
    left, top, right, bottom, origin=docling_base.CoordOrigin.BOTTOMLEFT
):
    return docling_base.BoundingBox(
        l=left, t=top, r=right, b=bottom, coord_origin=origin
    )


def _docling(*items):
    """Return a document of one text item per (page, bbox) in 'items'"""
    doc = docling_document.DoclingDocument(name="notes")

    for page_no, bbox in items:
        doc.add_text(
            label=docling_labels.DocItemLabel.TEXT,
            text="text",
            prov=docling_document.ProvenanceItem(
                page_no=page_no, bbox=bbox, charspan=(0, 4)
            ),
        )

    doc.add_text(label=docling_labels.DocItemLabel.TEXT, text="no prov")
    return doc


def _chunk(chunk_id, refs, document_id=DOCUMENT_ID):
    return hr_chunk.Chunk(
        id=chunk_id,
        document_id=document_id,
        content="text",
        metadata={"doc_item_refs": refs},
    )


def _owner(docling_doc, original=None):
    owner = mock.Mock()
    stored = mock.Mock()
    stored.get_docling_document.return_value = docling_doc
    repository = owner.document_repository
    repository.get_docling_data = mock.AsyncMock(
        return_value=None if docling_doc is None else stored
    )
    repository.get_original = mock.AsyncMock(return_value=original)
    return owner


def _pdf(*heights):
    """Return a PDF of one 600 pt wide page per height in 'heights'"""
    pdf = pypdfium2.PdfDocument.new()

    for height in heights:
        pdf.new_page(600, height)

    out = io.BytesIO()
    pdf.save(out)
    pdf.close()
    return out.getvalue()


def _size_pages(docling_doc, heights):
    """Size 'docling_doc's pages, as haiku.rag 0.113 keeps them"""
    for page_no, height in heights.items():
        docling_doc.add_page(
            page_no=page_no,
            size=docling_document.Size(width=600, height=height),
        )


TOP_LEFT_BOXES = {
    "structure": [
        models.PassageBox(page=1, left=10, top=700, right=300, bottom=650),
        models.PassageBox(page=2, left=10, top=500, right=300, bottom=450),
    ],
    # The original has one page: page 2's height is unknown.
    "original": [
        models.PassageBox(page=1, left=10, top=700, right=300, bottom=650),
    ],
    "none": [],
}


def _top_left_owner(docling_doc, sizes_from):
    """Return an owner whose pages are sized as 'sizes_from' says

    'structure' sizes both pages in the docling structure; 'original' leaves
    the structure unsized, as a migrated one is, and stores a one-page PDF
    800 pt high; 'none' has neither.
    """
    if sizes_from == "structure":
        _size_pages(docling_doc, {1: 800, 2: 600})

    original = _pdf(800) if sizes_from == "original" else None
    return _owner(docling_doc, original=original)


def _assert_original_loaded(owner, sizes_from):
    get_original = owner.document_repository.get_original

    if sizes_from == "structure":
        get_original.assert_not_awaited()
    else:
        get_original.assert_awaited_once_with(DOCUMENT_ID)


def _boxes_rag(chunks, owner, names=(DATABASE,)):
    rag = _rag(
        names=names,
        chunks={(DATABASE, chunk.id): chunk for chunk in chunks},
    )
    rag.clients_covering.return_value = [owner]
    return rag


async def _get_boxes(rags, **kwargs):
    return await room_documents_views.get_room_document_boxes(
        room_id=ROOM_ID,
        document_id=DOCUMENT_ID,
        **({"context_refs": None, "database": None} | kwargs),
        **_deps(rags=rags),
    )


@pytest.mark.anyio
@pytest.mark.parametrize("chunk_ids", [[], [f"c{i}" for i in range(51)]])
async def test_get_room_document_boxes_bad_chunk_ids(hr_klass, chunk_ids):
    with pytest.raises(fastapi.HTTPException) as exc:
        await _get_boxes([], chunk_ids=chunk_ids)

    assert exc.value.status_code == 422
    assert exc.value.detail == loggers.ROOM_INVALID_CHUNK_IDS


@pytest.mark.anyio
@pytest.mark.parametrize("context_refs", ["not json", '{"a": 1}', "[1]"])
async def test_get_room_document_boxes_bad_context_refs(
    hr_klass, context_refs
):
    with pytest.raises(fastapi.HTTPException) as exc:
        await _get_boxes([], chunk_ids=["c1"], context_refs=context_refs)

    assert exc.value.status_code == 422
    assert exc.value.detail == loggers.ROOM_INVALID_CONTEXT_REFS


@pytest.mark.anyio
async def test_get_room_document_boxes_unknown_room(hr_klass):
    deps = _deps(w_room=False)

    with pytest.raises(fastapi.HTTPException) as exc:
        await room_documents_views.get_room_document_boxes(
            room_id=ROOM_ID,
            document_id=DOCUMENT_ID,
            chunk_ids=["c1"],
            context_refs=None,
            database=None,
            **deps,
        )

    assert exc.value.status_code == 404


@pytest.mark.anyio
@pytest.mark.parametrize(
    "chunks",
    [
        [],  # the first chunk is unknown
        [_chunk("c1", [])],  # the second is unknown
        [_chunk("c1", []), _chunk("c2", [], document_id="doc-2")],
    ],
)
async def test_get_room_document_boxes_unknown_chunks(
    hr_klass, audit_records, chunks
):
    rag = _boxes_rag(chunks, _owner(None))
    _use(hr_klass, [rag])

    with pytest.raises(fastapi.HTTPException) as exc:
        await _get_boxes([rag], chunk_ids=["c1", "c2"])

    assert exc.value.status_code == 404
    assert exc.value.detail == f"{loggers.ROOM_UNKNOWN_CHUNK_ID}: c1, c2"
    (record,) = _rag_records(audit_records)
    assert record.action == loggers.AUDIT_RAG_ACTION_DOC_BOXES
    assert record.reason == loggers.ROOM_UNKNOWN_CHUNK_ID


@pytest.mark.anyio
@pytest.mark.parametrize("w_stored", [False, True])
async def test_get_room_document_boxes_no_docling(
    hr_klass, audit_records, w_stored
):
    owner = _owner(None)

    if w_stored:
        stored = mock.Mock()
        stored.get_docling_document.return_value = None
        owner.document_repository.get_docling_data.return_value = stored

    rag = _boxes_rag([_chunk("c1", ["#/texts/0"])], owner)
    _use(hr_klass, [rag])

    with pytest.raises(fastapi.HTTPException) as exc:
        await _get_boxes([rag], chunk_ids=["c1"])

    assert exc.value.status_code == 404
    assert exc.value.detail == (
        f"{loggers.ROOM_DOCUMENT_BOXES_NOT_AVAILABLE}: {DOCUMENT_ID}"
    )
    (record,) = _rag_records(audit_records)
    assert record.db_path == "/db/0"


@pytest.mark.anyio
async def test_get_room_document_boxes(hr_klass, audit_records):
    docling_doc = _docling(
        (1, _bbox(10, 700, 300, 650)),  # texts/0: chunk c1
        (1, _bbox(10, 640, 300, 600)),  # texts/1: chunk c2 (merged hit)
        (2, _bbox(20, 500, 200, 450)),  # texts/2: context only
    )
    owner = _owner(docling_doc)
    chunks = [_chunk("c1", ["#/texts/0"]), _chunk("c2", ["#/texts/1"])]
    rag = _boxes_rag(chunks, owner, names=("other", DATABASE))
    _use(hr_klass, [_rag(names=()), rag])

    result = await _get_boxes(
        [None, rag],
        chunk_ids=["c1", "c2", "c1"],
        context_refs=json.dumps(
            [
                "#/texts/0",
                "#/texts/1",
                "#/texts/2",
                "#/texts/3",
                "#/bogus/9",
                "#/texts/99",
                "#",
                "not-a-ref",
            ]
        ),
        database=DATABASE,
    )

    assert result == models.DocumentBoxes(
        source=models.RAGSource(source_type="agent", name=None),
        database=DATABASE,
        document_id=DOCUMENT_ID,
        anchor=[
            models.PassageBox(page=1, left=10, top=700, right=300, bottom=650),
            models.PassageBox(page=1, left=10, top=640, right=300, bottom=600),
        ],
        context=[
            models.PassageBox(page=2, left=20, top=500, right=200, bottom=450),
        ],
    )
    rag.clients_covering.assert_awaited_once_with([DATABASE])
    # Every box is bottom-left already: no original is loaded.
    owner.document_repository.get_original.assert_not_awaited()
    (record,) = _rag_records(audit_records)
    assert record.action == loggers.AUDIT_RAG_ACTION_DOC_BOXES
    assert record.db_path == "/db/1"
    assert record.selector == ["c1", "c2"]
    assert record.result_refs == [DOCUMENT_ID]


@pytest.mark.anyio
@pytest.mark.parametrize("sizes_from", ["structure", "original", "none"])
async def test_get_room_document_boxes_top_left(hr_klass, sizes_from):
    top_left = docling_base.CoordOrigin.TOPLEFT
    docling_doc = _docling(
        (1, _bbox(10, 100, 300, 150, top_left)),
        (2, _bbox(10, 100, 300, 150, top_left)),
    )
    owner = _top_left_owner(docling_doc, sizes_from)
    rag = _boxes_rag([_chunk("c1", ["#/texts/0", "#/texts/1"])], owner)
    _use(hr_klass, [rag])

    result = await _get_boxes([rag], chunk_ids=["c1"])

    assert result.anchor == TOP_LEFT_BOXES[sizes_from]
    assert result.context == []
    _assert_original_loaded(owner, sizes_from)
