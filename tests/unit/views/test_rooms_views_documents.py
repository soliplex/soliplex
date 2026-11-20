"""Tests for the room routes serving a RAG document's PDF and passage boxes"""

import json
import os
from unittest import mock

import fastapi
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
from soliplex.views import rooms as rooms_views

ROOM_ID = "pdf_notes"
DOCUMENT_ID = "doc-1"
DATABASE = "field_notes"
THE_USER_CLAIMS = {"preferred_username": "phreddy"}
PDF_BYTES = b"%PDF-1.7\n" + b"x" * (rooms_views.PDF_CHUNKSIZE + 10)


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


async def _body(response):
    return b"".join([chunk async for chunk in response.body_iterator])


# ----------------------------------------------------------------------------
#   GET /v1/rooms/{room_id}/documents/{document_id}/file
# ----------------------------------------------------------------------------


@pytest.mark.anyio
async def test_get_room_document_file_unknown_room(hr_klass, audit_records):
    deps = _deps(w_room=False)

    with pytest.raises(fastapi.HTTPException) as exc:
        await rooms_views.get_room_document_file(
            room_id=ROOM_ID, document_id=DOCUMENT_ID, **deps
        )

    assert exc.value.status_code == 404
    assert exc.value.detail == f"{loggers.ROOM_UNKNOWN_ROOM_ID}: {ROOM_ID}"
    assert _rag_records(audit_records) == []


@pytest.mark.anyio
@pytest.mark.parametrize("w_database", [None, "other"])
async def test_get_room_document_file_unknown_document(
    hr_klass, audit_records, temp_dir, w_database
):
    pdf = temp_dir / "notes.pdf"
    pdf.write_bytes(PDF_BYTES)
    rags = [
        _rag(),
        _rag(
            names=(DATABASE,),
            documents={(DATABASE, "elsewhere"): _document(pdf.as_uri())},
        ),
    ]
    _use(hr_klass, rags)
    deps = _deps(rags=rags)

    with pytest.raises(fastapi.HTTPException) as exc:
        await rooms_views.get_room_document_file(
            room_id=ROOM_ID,
            document_id=DOCUMENT_ID,
            database=w_database,
            **deps,
        )

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
async def test_get_room_document_file(
    hr_klass, audit_records, temp_dir, w_federated
):
    pdf = temp_dir / "field notes.pdf"
    pdf.write_bytes(PDF_BYTES)
    names = ("other", DATABASE) if w_federated else (DATABASE,)
    rag = _rag(
        names=names,
        documents={(DATABASE, DOCUMENT_ID): _document(pdf.as_uri())},
    )
    _use(hr_klass, [rag])
    deps = _deps(rags=[rag])

    response = await rooms_views.get_room_document_file(
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
    assert await _body(response) == PDF_BYTES
    (record,) = _rag_records(audit_records)
    assert record.action == loggers.AUDIT_RAG_ACTION_DOC_FILE
    assert record.db_path == "/db/0"
    assert record.selector == DOCUMENT_ID
    assert record.result_refs == [pdf.as_uri()]
    deps["the_logger"].debug.assert_called_once_with(
        loggers.ROOM_GET_DOCUMENT_FILE
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "uri", ["https://example.com/notes.pdf", "relative/notes.pdf"]
)
async def test_get_room_document_file_not_local(hr_klass, audit_records, uri):
    rag = _rag(documents={(DATABASE, DOCUMENT_ID): _document(uri)})
    _use(hr_klass, [rag])

    with pytest.raises(fastapi.HTTPException) as exc:
        await rooms_views.get_room_document_file(
            room_id=ROOM_ID, document_id=DOCUMENT_ID, **_deps(rags=[rag])
        )

    assert exc.value.status_code == 404
    assert exc.value.detail == (
        f"{loggers.ROOM_DOCUMENT_NOT_LOCAL}: {DOCUMENT_ID}"
    )
    (record,) = _rag_records(audit_records)
    assert record.db_path == "/db/0"
    assert record.reason == loggers.ROOM_DOCUMENT_NOT_LOCAL


@pytest.mark.anyio
@pytest.mark.parametrize("kind", ["missing", "directory", "symlink", "text"])
async def test_get_room_document_file_unavailable(
    hr_klass, audit_records, temp_dir, kind
):
    target = temp_dir / "notes.pdf"

    if kind == "directory":
        target.mkdir()
    elif kind == "symlink":
        real = temp_dir / "real.pdf"
        real.write_bytes(PDF_BYTES)
        target.symlink_to(real)
    elif kind == "text":
        target.write_bytes(b"plain text, not a PDF")

    rag = _rag(documents={(DATABASE, DOCUMENT_ID): _document(target.as_uri())})
    _use(hr_klass, [rag])

    with (
        mock.patch("os.close", wraps=os.close) as close,
        pytest.raises(fastapi.HTTPException) as exc,
    ):
        await rooms_views.get_room_document_file(
            room_id=ROOM_ID, document_id=DOCUMENT_ID, **_deps(rags=[rag])
        )

    assert exc.value.status_code == 404
    assert exc.value.detail == (
        f"{loggers.ROOM_DOCUMENT_FILE_UNAVAILABLE}: {DOCUMENT_ID}"
    )
    # A file the route opened and refused is closed again.
    assert close.call_count == (1 if kind in ("directory", "text") else 0)
    (record,) = _rag_records(audit_records)
    assert record.reason == loggers.ROOM_DOCUMENT_FILE_UNAVAILABLE


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


def _owner(docling_doc, page_heights=None):
    owner = mock.Mock()
    stored = mock.Mock()
    stored.get_docling_document.return_value = docling_doc
    repository = owner.document_repository
    repository.get_docling_data = mock.AsyncMock(
        return_value=None if docling_doc is None else stored
    )
    pages_doc = None

    if page_heights is not None:
        pages_doc = mock.Mock()
        pages_doc.get_page_images.side_effect = lambda pages: {
            page: mock.Mock(size=mock.Mock(height=page_heights[page]))
            for page in pages
            if page in page_heights
        }

    repository.get_pages_data = mock.AsyncMock(return_value=pages_doc)
    return owner


def _boxes_rag(chunks, owner, names=(DATABASE,)):
    rag = _rag(
        names=names,
        chunks={(DATABASE, chunk.id): chunk for chunk in chunks},
    )
    rag.clients_covering.return_value = [owner]
    return rag


async def _get_boxes(rags, **kwargs):
    return await rooms_views.get_room_document_boxes(
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
        await rooms_views.get_room_document_boxes(
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
            ["#/texts/0", "#/texts/1", "#/texts/2", "#/texts/3", "#/bogus/9"]
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
    # Every box is bottom-left already: no page is loaded.
    owner.document_repository.get_pages_data.assert_not_awaited()
    (record,) = _rag_records(audit_records)
    assert record.action == loggers.AUDIT_RAG_ACTION_DOC_BOXES
    assert record.db_path == "/db/1"
    assert record.selector == ["c1", "c2"]
    assert record.result_refs == [DOCUMENT_ID]


@pytest.mark.anyio
@pytest.mark.parametrize("w_pages", [False, True])
async def test_get_room_document_boxes_top_left(hr_klass, w_pages):
    top_left = docling_base.CoordOrigin.TOPLEFT
    docling_doc = _docling(
        (1, _bbox(10, 100, 300, 150, top_left)),
        (2, _bbox(10, 100, 300, 150, top_left)),  # page 2's height is unknown
    )
    owner = _owner(docling_doc, page_heights={1: 800} if w_pages else None)
    rag = _boxes_rag([_chunk("c1", ["#/texts/0", "#/texts/1"])], owner)
    _use(hr_klass, [rag])

    result = await _get_boxes([rag], chunk_ids=["c1"])

    expected = (
        [models.PassageBox(page=1, left=10, top=700, right=300, bottom=650)]
        if w_pages
        else []
    )
    assert result.anchor == expected
    assert result.context == []
    owner.document_repository.get_pages_data.assert_awaited_once_with(
        DOCUMENT_ID
    )


# ----------------------------------------------------------------------------
#   GET /v1/rooms/{room_id}/documents/{document_id}/text
# ----------------------------------------------------------------------------


def _prov(page_no, bbox, charspan=(0, 0)):
    return docling_document.ProvenanceItem(
        page_no=page_no, bbox=bbox, charspan=charspan
    )


def _ocr_docling():
    """Return a document with one of each kind of item the route meets"""
    doc = docling_document.DoclingDocument(name="notes")
    labels = docling_labels.DocItemLabel
    doc.add_text(
        label=labels.PAGE_HEADER,
        text="Field notes",
        prov=_prov(1, _bbox(10, 790, 100, 780)),
        content_layer=docling_document.ContentLayer.FURNITURE,
    )
    doc.add_heading(text="Chunking", prov=_prov(1, _bbox(10, 760, 200, 740)))
    spanning = doc.add_text(
        label=labels.TEXT,
        text="first half second half",
        prov=_prov(1, _bbox(10, 100, 300, 50), (0, 11)),
    )
    spanning.prov.append(_prov(2, _bbox(10, 700, 300, 650), (11, 22)))
    doc.add_text(
        label=labels.TEXT,
        text="   ",  # nothing to show
        prov=_prov(2, _bbox(10, 640, 300, 600)),
    )
    doc.add_text(label=labels.TEXT, text="no prov")
    doc.add_picture(prov=_prov(2, _bbox(10, 590, 300, 400)))
    doc.add_table(
        data=docling_document.TableData(
            num_rows=1,
            num_cols=1,
            table_cells=[
                docling_document.TableCell(
                    text="cell",
                    start_row_offset_idx=0,
                    end_row_offset_idx=1,
                    start_col_offset_idx=0,
                    end_col_offset_idx=1,
                )
            ],
        ),
        prov=_prov(2, _bbox(10, 390, 300, 300)),
    )
    doc.add_text(
        label=labels.TEXT,
        text="top left",
        prov=_prov(
            3,
            _bbox(10, 100, 300, 150, docling_base.CoordOrigin.TOPLEFT),
            (0, 8),
        ),
    )
    return doc


def _text_rag(owner, names=(DATABASE,)):
    rag = _rag(
        names=names,
        documents={(DATABASE, DOCUMENT_ID): _document("file:///notes.pdf")},
    )
    rag.clients_covering.return_value = [owner]
    return rag


async def _get_text(rags, **kwargs):
    deps = _deps(rags=rags)
    result = await rooms_views.get_room_document_text(
        room_id=ROOM_ID,
        document_id=DOCUMENT_ID,
        **({"database": None} | kwargs),
        **deps,
    )
    return result, deps


@pytest.mark.anyio
async def test_get_room_document_text_unknown_room(hr_klass, audit_records):
    with pytest.raises(fastapi.HTTPException) as exc:
        await rooms_views.get_room_document_text(
            room_id=ROOM_ID, document_id=DOCUMENT_ID, **_deps(w_room=False)
        )

    assert exc.value.status_code == 404
    assert exc.value.detail == f"{loggers.ROOM_UNKNOWN_ROOM_ID}: {ROOM_ID}"
    assert _rag_records(audit_records) == []


@pytest.mark.anyio
@pytest.mark.parametrize("w_database", [None, "other"])
async def test_get_room_document_text_unknown_document(
    hr_klass, audit_records, w_database
):
    # The document is only in DATABASE: unasked when "other" is named.
    rags = [_rag(), _text_rag(_owner(None), names=("other", DATABASE))]
    if w_database is None:
        rags[1] = _rag(names=("other", DATABASE))
    _use(hr_klass, rags)

    with pytest.raises(fastapi.HTTPException) as exc:
        await _get_text(rags, database=w_database)

    assert exc.value.status_code == 404
    assert exc.value.detail == (
        f"{loggers.ROOM_UNKNOWN_DOCUMENT_ID}: {DOCUMENT_ID}"
    )
    (record,) = _rag_records(audit_records)
    assert record.action == loggers.AUDIT_RAG_ACTION_DOC_TEXT
    assert record.db_path is None
    assert record.reason == loggers.ROOM_UNKNOWN_DOCUMENT_ID


@pytest.mark.anyio
@pytest.mark.parametrize("w_stored", [False, True])
async def test_get_room_document_text_no_docling(
    hr_klass, audit_records, w_stored
):
    owner = _owner(None)

    if w_stored:
        stored = mock.Mock()
        stored.get_docling_document.return_value = None
        owner.document_repository.get_docling_data.return_value = stored

    rag = _text_rag(owner)
    _use(hr_klass, [rag])

    with pytest.raises(fastapi.HTTPException) as exc:
        await _get_text([rag])

    assert exc.value.status_code == 404
    assert exc.value.detail == (
        f"{loggers.ROOM_DOCUMENT_TEXT_NOT_AVAILABLE}: {DOCUMENT_ID}"
    )
    (record,) = _rag_records(audit_records)
    assert record.action == loggers.AUDIT_RAG_ACTION_DOC_TEXT
    assert record.db_path == "/db/0"
    assert record.reason == loggers.ROOM_DOCUMENT_TEXT_NOT_AVAILABLE


@pytest.mark.anyio
@pytest.mark.parametrize("w_pages", [False, True])
async def test_get_room_document_text(hr_klass, audit_records, w_pages):
    owner = _owner(_ocr_docling(), page_heights={3: 800} if w_pages else None)
    rag = _text_rag(owner, names=("other", DATABASE))
    _use(hr_klass, [_rag(names=()), rag])

    result, deps = await _get_text([None, rag], database=DATABASE)

    def block(page, box, text, label="text"):
        left, top, right, bottom = box
        return models.TextBlock(
            page=page,
            left=left,
            top=top,
            right=right,
            bottom=bottom,
            text=text,
            label=label,
        )

    expected = [
        block(1, (10, 790, 100, 780), "Field notes", "page_header"),
        block(1, (10, 760, 200, 740), "Chunking", "section_header"),
        block(1, (10, 100, 300, 50), "first half "),
        block(2, (10, 700, 300, 650), "second half"),
        block(2, (10, 390, 300, 300), "| cell   |\n|--------|", "table"),
    ]

    if w_pages:
        expected.append(block(3, (10, 700, 300, 650), "top left"))

    assert result == models.DocumentText(
        source=models.RAGSource(source_type="agent", name=None),
        database=DATABASE,
        document_id=DOCUMENT_ID,
        blocks=expected,
    )
    rag.clients_covering.assert_awaited_once_with([DATABASE])
    owner.document_repository.get_pages_data.assert_awaited_once_with(
        DOCUMENT_ID
    )
    (record,) = _rag_records(audit_records)
    assert record.action == loggers.AUDIT_RAG_ACTION_DOC_TEXT
    assert record.db_path == "/db/1"
    assert record.selector == DOCUMENT_ID
    assert record.result_refs == ["file:///notes.pdf"]
    deps["the_logger"].debug.assert_called_once_with(
        loggers.ROOM_GET_DOCUMENT_TEXT
    )


@pytest.mark.anyio
async def test_get_room_document_text_bottom_left_only(hr_klass):
    owner = _owner(_docling((1, _bbox(10, 700, 300, 650))))
    rag = _text_rag(owner)
    _use(hr_klass, [rag])

    result, _ = await _get_text([rag])

    assert [(b.page, b.text) for b in result.blocks] == [(1, "text")]
    owner.document_repository.get_pages_data.assert_not_awaited()
