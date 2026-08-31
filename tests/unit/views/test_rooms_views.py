import datetime
from unittest import mock

import fastapi
import pytest
from haiku.rag.store.models import chunk as hr_chunk

from soliplex import authz
from soliplex import installation
from soliplex import loggers
from soliplex import models
from soliplex.config import rooms as config_rooms
from soliplex.views import rooms as rooms_views

NOW = datetime.datetime.now(datetime.UTC)

ROOM_IDS = ["foo", "bar", "baz"]

USER_NAME = "phreddy"
GIVEN_NAME = "Phred"
FAMILY_NAME = "Phlyntstone"
EMAIL = "phreddy@example.com"

THE_USER_CLAIMS = {
    "preferred_username": USER_NAME,
    "given_name": GIVEN_NAME,
    "family_name": FAMILY_NAME,
    "email": EMAIL,
}

UNKNOWN_USER_CLAIMS = {
    "preferred_username": "<unknown>",
    "given_name": "<unknown>",
    "family_name": "<unknown>",
    "email": "<unknown>",
}

DOCUMENT_ID = "test-doc-id"
DOCUMENT_URI = f"https://example.com/documents/{DOCUMENT_ID}.txt"
DOCUMENT_TITLE = "Test Document"
DOCUMENT_METADATA = {"testing": "Test"}
DOCUMENT_CREATED_AT = NOW
DOCUMENT_UPDATED_AT = NOW

DOCUMENT_KWARGS = {
    "id": DOCUMENT_ID,
    "uri": DOCUMENT_URI,
    "title": DOCUMENT_TITLE,
    "metadata": DOCUMENT_METADATA,
    "created_at": DOCUMENT_CREATED_AT,
    "updated_at": DOCUMENT_UPDATED_AT,
}


@pytest.fixture(scope="module", params=[(), ROOM_IDS])
def room_configs(request):
    return {
        room_id: mock.create_autospec(
            config_rooms.RoomConfig,
            sort_key=room_id,
        )
        for room_id in request.param
    }


@pytest.mark.anyio
@mock.patch("soliplex.models.Room.from_config")
async def test_get_rooms(fc, room_configs):
    the_installation = mock.create_autospec(installation.Installation)
    the_installation.get_room_configs.return_value = room_configs
    the_room_authz = mock.create_autospec(authz.RoomAuthorizationPolicy)
    the_logger = mock.create_autospec(loggers.LogWrapper)

    found = await rooms_views.get_rooms(
        the_installation=the_installation,
        the_room_authz=the_room_authz,
        the_user_claims=THE_USER_CLAIMS,
        the_logger=the_logger,
    )

    for (found_key, found_room), room_id, fc_call in zip(
        found.items(),  # should already be sorted
        sorted(room_configs),
        fc.call_args_list,
        strict=True,
    ):
        assert found_key == room_id
        assert found_room is fc.return_value
        assert fc_call == mock.call(room_configs[room_id])

    the_installation.get_room_configs.assert_awaited_once_with(
        user=THE_USER_CLAIMS,
        the_room_authz=the_room_authz,
        the_logger=the_logger,
    )
    the_logger.debug.assert_called_once_with(loggers.ROOM_GET_ROOMS)


@pytest.mark.anyio
@mock.patch("soliplex.models.Room.from_config")
async def test_get_room(fc, room_configs):
    ROOM_ID = "foo"

    the_installation = mock.create_autospec(installation.Installation)

    if ROOM_ID not in room_configs:
        the_installation.get_room_config.side_effect = KeyError("testing")
    else:
        the_installation.get_room_config.return_value = room_configs[ROOM_ID]

    the_room_authz = mock.create_autospec(authz.RoomAuthorizationPolicy)
    the_logger = mock.create_autospec(loggers.LogWrapper)

    if ROOM_ID not in room_configs:
        with pytest.raises(fastapi.HTTPException) as exc:
            await rooms_views.get_room(
                ROOM_ID,
                the_installation=the_installation,
                the_room_authz=the_room_authz,
                the_user_claims=THE_USER_CLAIMS,
                the_logger=the_logger,
            )

        assert exc.value.status_code == 404
        assert exc.value.detail == (
            f"{loggers.ROOM_UNKNOWN_ROOM_ID}: {ROOM_ID}"
        )
        the_logger.exception.assert_called_once_with(
            loggers.ROOM_UNKNOWN_ROOM_ID,
            room_id=ROOM_ID,
        )

    else:
        found = await rooms_views.get_room(
            ROOM_ID,
            the_installation=the_installation,
            the_room_authz=the_room_authz,
            the_user_claims=THE_USER_CLAIMS,
            the_logger=the_logger,
        )

        assert found is fc.return_value
        fc.assert_called_once_with(room_configs[ROOM_ID])

    the_installation.get_room_config.assert_awaited_once_with(
        room_id=ROOM_ID,
        user=THE_USER_CLAIMS,
        the_room_authz=the_room_authz,
        the_logger=the_logger,
    )
    the_logger.debug.assert_called_once_with(loggers.ROOM_GET_ROOM)


@pytest.mark.anyio
@pytest.mark.parametrize("w_image", [False, True])
async def test_get_room_bg_image(temp_dir, w_image, room_configs):
    ROOM_ID = "foo"
    IMAGE_FILENAME = "logo.svg"

    image_path = temp_dir / IMAGE_FILENAME

    the_installation = mock.create_autospec(installation.Installation)

    if ROOM_ID not in room_configs:
        the_installation.get_room_config.side_effect = KeyError("testing")
    else:
        the_installation.get_room_config.return_value = room_configs[ROOM_ID]

    the_room_authz = mock.create_autospec(authz.RoomAuthorizationPolicy)
    the_logger = mock.create_autospec(loggers.LogWrapper)

    if ROOM_ID in room_configs:
        if w_image:
            room_configs[ROOM_ID].get_logo_image.return_value = image_path
        else:
            room_configs[ROOM_ID].get_logo_image.return_value = None

    if ROOM_ID not in room_configs:
        with pytest.raises(fastapi.HTTPException) as exc:
            await rooms_views.get_room_bg_image(
                room_id=ROOM_ID,
                the_installation=the_installation,
                the_room_authz=the_room_authz,
                the_user_claims=THE_USER_CLAIMS,
                the_logger=the_logger,
            )

        assert exc.value.status_code == 404
        assert exc.value.detail == (
            f"{loggers.ROOM_UNKNOWN_ROOM_ID}: {ROOM_ID}"
        )
        the_logger.exception.assert_called_once_with(
            loggers.ROOM_UNKNOWN_ROOM_ID,
            room_id=ROOM_ID,
        )
    else:
        if w_image:
            found = await rooms_views.get_room_bg_image(
                room_id=ROOM_ID,
                the_installation=the_installation,
                the_room_authz=the_room_authz,
                the_user_claims=THE_USER_CLAIMS,
                the_logger=the_logger,
            )
            # Actual image data is marshalled by fastapi framework
            assert found == str(image_path)
        else:
            with pytest.raises(fastapi.HTTPException) as exc:
                await rooms_views.get_room_bg_image(
                    room_id=ROOM_ID,
                    the_installation=the_installation,
                    the_room_authz=the_room_authz,
                    the_user_claims=THE_USER_CLAIMS,
                    the_logger=the_logger,
                )

            assert exc.value.status_code == 404
            assert exc.value.detail == "No image for room"
            # Note that we do *not* log this as an exception:  it
            # is an expected condition for rooms without an image
            # configured.

    the_installation.get_room_config.assert_awaited_once_with(
        room_id=ROOM_ID,
        user=THE_USER_CLAIMS,
        the_room_authz=the_room_authz,
        the_logger=the_logger,
    )
    the_logger.debug.assert_called_once_with(loggers.ROOM_GET_ROOM_BG_IMAGE)


@pytest.mark.anyio
@pytest.mark.parametrize("w_error", [False, True])
@mock.patch("soliplex.mcp_auth.generate_url_safe_token")
async def test_get_room_mcp_token(gust, w_error):
    ROOM_ID = "test-room"
    ROOM_CONFIG = object()
    MCP_TOKEN = gust.return_value = "DEADBEEF"

    the_installation = mock.create_autospec(installation.Installation)
    the_room_authz = mock.create_autospec(authz.RoomAuthorizationPolicy)
    the_logger = mock.create_autospec(loggers.LogWrapper)

    if w_error:
        the_installation.get_room_config.side_effect = KeyError("testing")
    else:
        the_installation.get_room_config.return_value = ROOM_CONFIG

    if w_error:
        with pytest.raises(fastapi.HTTPException) as exc:
            await rooms_views.get_room_mcp_token(
                room_id=ROOM_ID,
                the_installation=the_installation,
                the_room_authz=the_room_authz,
                the_user_claims=THE_USER_CLAIMS,
                the_logger=the_logger,
            )

        assert exc.value.status_code == 404
        assert exc.value.detail == (
            f"{loggers.ROOM_UNKNOWN_ROOM_ID}: {ROOM_ID}"
        )
        the_logger.exception.assert_called_once_with(
            loggers.ROOM_UNKNOWN_ROOM_ID,
            room_id=ROOM_ID,
        )

    else:
        found = await rooms_views.get_room_mcp_token(
            room_id=ROOM_ID,
            the_installation=the_installation,
            the_room_authz=the_room_authz,
            the_user_claims=THE_USER_CLAIMS,
            the_logger=the_logger,
        )

        expected = {
            "room_id": ROOM_ID,
            "mcp_token": MCP_TOKEN,
        }
        assert found.model_dump() == expected

        gust.assert_called_once_with(
            the_installation.get_secret.return_value,
            ROOM_ID,
            **THE_USER_CLAIMS,
        )
        the_installation.get_secret.assert_called_once_with(
            "URL_SAFE_TOKEN_SECRET"
        )

    the_installation.get_room_config.assert_awaited_once_with(
        room_id=ROOM_ID,
        user=THE_USER_CLAIMS,
        the_room_authz=the_room_authz,
        the_logger=the_logger,
    )
    the_logger.debug.assert_called_once_with(loggers.ROOM_GET_ROOM_MCP_TOKEN)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "w_hrc_kws",
    [
        [],
        [{"source": "agent", "db_path": "/db/agent", "foo": "bar"}],
        [{"source": "skill:test", "db_path": "/db/skill", "foo": "bar"}],
        [{"source": "tool:test", "db_path": "/db/tool", "foo": "bar"}],
        [
            {"source": "skill:test", "db_path": "/db/skill", "foo": "bar"},
            {"source": "tool:test", "db_path": "/db/tool", "foo": "bar"},
        ],
    ],
)
@mock.patch("haiku.rag.client.HaikuRAG")
async def test_get_room_documents(
    hr_klass,
    w_hrc_kws,
    temp_dir,
    room_configs,
    audit_records,
):
    ROOM_ID = "foo"

    w_hrc_kws = [
        kws | {"audit_db_path": str(kws["db_path"])} for kws in w_hrc_kws
    ]
    sources = [kws["source"] for kws in w_hrc_kws]
    hr_insts = {source: mock.AsyncMock() for source in sources}
    hr_entereds = {
        key: value.__aenter__.return_value for key, value in hr_insts.items()
    }
    hr_klass.side_effect = hr_insts.values()

    rag_sources = {}

    for source in sources:
        if source == "agent":
            source_type = "agent"
            name = None
        else:
            source_type, name = source.split(":")

        rag_sources[source] = models.RAGSource(
            source_type=source_type,
            name=name,
        )

    document_infos = {
        source: {
            "id": f"test-doc-id-{source}",
            "uri": DOCUMENT_URI,
            "title": DOCUMENT_TITLE,
            "metadata": DOCUMENT_METADATA,
            "created_at": DOCUMENT_CREATED_AT,
            "updated_at": DOCUMENT_UPDATED_AT,
        }
        for source in sources
    }
    doc_fields = [
        "id",
        "uri",
        "title",
        "metadata",
        "created_at",
        "updated_at",
        "source",  # the haiku.rag database name
    ]
    documents = {
        source: mock.Mock(
            spec_set=doc_fields,
            source=f"db-{source}",
            **document_infos[source],
        )
        for source in sources
    }

    the_installation = mock.create_autospec(installation.Installation)

    if ROOM_ID not in room_configs:
        the_installation.get_room_config.side_effect = KeyError("testing")
    else:
        the_installation.get_room_config.return_value = room_configs[ROOM_ID]

    the_room_authz = mock.create_autospec(authz.RoomAuthorizationPolicy)
    the_logger = mock.create_autospec(loggers.LogWrapper)

    if ROOM_ID not in room_configs:
        with pytest.raises(fastapi.HTTPException) as exc:
            await rooms_views.get_room_documents(
                room_id=ROOM_ID,
                the_installation=the_installation,
                the_room_authz=the_room_authz,
                the_user_claims=THE_USER_CLAIMS,
                the_logger=the_logger,
            )

        assert exc.value.status_code == 404
        assert exc.value.detail == (
            f"{loggers.ROOM_UNKNOWN_ROOM_ID}: {ROOM_ID}"
        )
        the_logger.exception.assert_called_once_with(
            loggers.ROOM_UNKNOWN_ROOM_ID,
            room_id=ROOM_ID,
        )
        assert audit_records == []
    else:
        room_config = room_configs[ROOM_ID]
        room_config.list_haiku_rag_client_kw.return_value = w_hrc_kws

        for source in sources:
            hr_entered = hr_entereds[source]
            hr_entered.list_documents.return_value = [documents[source]]

        exp_rag_docs = {
            document_info["id"]: models.RAGDocument(
                source=rag_sources[source],
                database=f"db-{source}",
                **document_info,
            )
            for source, document_info in document_infos.items()
        }

        found = await rooms_views.get_room_documents(
            room_id=ROOM_ID,
            the_installation=the_installation,
            the_room_authz=the_room_authz,
            the_user_claims=THE_USER_CLAIMS,
            the_logger=the_logger,
        )

        assert found == models.RoomRAGDocuments(
            room_id=ROOM_ID,
            document_set=exp_rag_docs,
        )

        if w_hrc_kws:
            for kw in w_hrc_kws:
                assert mock.call(**kw) in hr_klass.call_args_list

            for hr_entered in hr_entereds.values():
                hr_entered.list_documents.assert_awaited_once_with()
        else:
            hr_klass.assert_not_called()

        rag_records = [
            record
            for record in audit_records
            if record.__dict__.get(loggers.SOLIPLEX_AUDIT_LOGGER_SCOPE_EXTRA)
            == loggers.AuditLogScopes.RAG_ACCESS
        ]
        assert len(rag_records) == len(sources)
        for record, kws, source in zip(
            rag_records, w_hrc_kws, sources, strict=True
        ):
            assert record.action == loggers.AUDIT_RAG_ACTION_DOC_LIST
            assert record.outcome == loggers.AUDIT_OUTCOME_SUCCESS
            assert record.room_id == ROOM_ID
            assert record.db_path == kws["db_path"]
            assert record.result_refs == [documents[source].id]

    the_installation.get_room_config.assert_awaited_once_with(
        room_id=ROOM_ID,
        user=THE_USER_CLAIMS,
        the_room_authz=the_room_authz,
        the_logger=the_logger,
    )
    the_logger.debug.assert_called_once_with(loggers.ROOM_GET_ROOM_DOCUMENTS)


def _sole_rag_record(audit_records):
    """Return the single rag-access audit record, asserting there is one."""
    rag_records = [
        record
        for record in audit_records
        if record.__dict__.get(loggers.SOLIPLEX_AUDIT_LOGGER_SCOPE_EXTRA)
        == loggers.AuditLogScopes.RAG_ACCESS
    ]
    assert len(rag_records) == 1
    return rag_records[0]


@pytest.mark.anyio
@pytest.mark.parametrize("w_image", [False, True])
@pytest.mark.parametrize("w_chunk_index", [None, 0, -1])
@pytest.mark.parametrize(
    "w_hrc_kws",
    [
        [],
        [{"source": "agent", "db_path": "/db/agent", "foo": "bar"}],
        [{"source": "skill:test", "db_path": "/db/skill", "foo": "bar"}],
        [{"source": "tool:test", "db_path": "/db/tool", "foo": "bar"}],
        [
            {"source": "skill:test", "db_path": "/db/skill", "foo": "bar"},
            {"source": "tool:test", "db_path": "/db/tool", "foo": "bar"},
        ],
    ],
)
@mock.patch("haiku.rag.client.HaikuRAG")
@mock.patch("base64.b64encode")
async def test_get_chunk_visualization(
    b64enc,
    hr_klass,
    w_hrc_kws,
    w_chunk_index,
    w_image,
    temp_dir,
    room_configs,
    audit_records,
):
    ROOM_ID = "foo"
    CHUNK_ID = "test-chunk-123"
    DOCUMENT_URI = f"https://example.com/chunks/{CHUNK_ID}"
    PAGES_PNG = [
        mock.Mock(spec_set=["blob", "save"], blob="facedace8765"),
        mock.Mock(spec_set=["blob", "save"], blob="deadbeef3456"),
    ]
    PAGES_B64 = [
        "facedace8765",
        "deadbeef3456",
    ]
    b64enc.return_value.decode.side_effect = PAGES_B64

    w_hrc_kws = [
        kws | {"audit_db_path": str(kws["db_path"])} for kws in w_hrc_kws
    ]
    sources = [kws["source"] for kws in w_hrc_kws]
    hr_insts = {source: mock.AsyncMock() for source in sources}
    hr_entereds = {
        key: value.__aenter__.return_value for key, value in hr_insts.items()
    }
    rags = list(hr_entereds.values())
    hr_klass.side_effect = hr_insts.values()

    rag_sources = {}

    for source in sources:
        if source == "agent":
            source_type = "agent"
            name = None
        else:
            source_type, name = source.split(":")

        rag_sources[source] = models.RAGSource(
            source_type=source_type,
            name=name,
        )

    the_installation = mock.create_autospec(installation.Installation)

    if ROOM_ID not in room_configs:
        the_installation.get_room_config.side_effect = KeyError("testing")
    else:
        the_installation.get_room_config.return_value = room_configs[ROOM_ID]

    the_room_authz = mock.create_autospec(authz.RoomAuthorizationPolicy)
    the_logger = mock.create_autospec(loggers.LogWrapper)

    if ROOM_ID in room_configs:
        if w_hrc_kws:
            for rag in rags:
                rag.covers_multiple = False
                rag.source = None  # an unnamed single database
                rag.reader_for.return_value = rag
                rag.get_chunk_by_id.return_value = None
                rag.visualize_chunk.return_value = None

            if w_chunk_index is not None:
                chunk = hr_chunk.Chunk(
                    chunk_id=CHUNK_ID,
                    document_uri=DOCUMENT_URI,
                    content="waaa",
                )
                rag_w_chunk = rags[w_chunk_index]
                rag_w_chunk.get_chunk_by_id.return_value = chunk

                if w_image:
                    rag_w_chunk.visualize_chunk.return_value = PAGES_PNG

    if ROOM_ID not in room_configs:
        with pytest.raises(fastapi.HTTPException) as exc:
            await rooms_views.get_chunk_visualization(
                room_id=ROOM_ID,
                chunk_id=CHUNK_ID,
                the_installation=the_installation,
                the_room_authz=the_room_authz,
                the_user_claims=THE_USER_CLAIMS,
                the_logger=the_logger,
            )

        assert exc.value.status_code == 404
        assert exc.value.detail == (
            f"{loggers.ROOM_UNKNOWN_ROOM_ID}: {ROOM_ID}"
        )
        the_logger.exception.assert_called_once_with(
            loggers.ROOM_UNKNOWN_ROOM_ID,
            room_id=ROOM_ID,
        )
        assert audit_records == []

    else:
        room_config = room_configs[ROOM_ID]
        room_config.list_haiku_rag_client_kw = mock.Mock(
            spec_set=(),
            return_value=w_hrc_kws,
        )

        if not w_hrc_kws:  # no rag sources
            with pytest.raises(fastapi.HTTPException) as exc:
                await rooms_views.get_chunk_visualization(
                    room_id=ROOM_ID,
                    chunk_id=CHUNK_ID,
                    the_installation=the_installation,
                    the_room_authz=the_room_authz,
                    the_user_claims=THE_USER_CLAIMS,
                    the_logger=the_logger,
                )

            assert exc.value.status_code == 404
            assert exc.value.detail == (
                f"{loggers.ROOM_UNKNOWN_CHUNK_ID}: {CHUNK_ID}"
            )
            the_logger.error.assert_called_once_with(
                loggers.ROOM_UNKNOWN_CHUNK_ID, chunk_id=CHUNK_ID
            )

            record = _sole_rag_record(audit_records)
            assert record.action == loggers.AUDIT_RAG_ACTION_CHUNK_VIZ
            assert record.outcome == loggers.AUDIT_OUTCOME_ERROR
            assert record.room_id == ROOM_ID
            assert record.db_path is None
            assert record.selector == CHUNK_ID
            assert record.reason == loggers.ROOM_UNKNOWN_CHUNK_ID

        elif w_chunk_index is None:
            with pytest.raises(fastapi.HTTPException) as exc:
                await rooms_views.get_chunk_visualization(
                    room_id=ROOM_ID,
                    chunk_id=CHUNK_ID,
                    the_installation=the_installation,
                    the_room_authz=the_room_authz,
                    the_user_claims=THE_USER_CLAIMS,
                    the_logger=the_logger,
                )

            assert exc.value.status_code == 404
            assert exc.value.detail == (
                f"{loggers.ROOM_UNKNOWN_CHUNK_ID}: {CHUNK_ID}"
            )
            the_logger.error.assert_called_once_with(
                loggers.ROOM_UNKNOWN_CHUNK_ID, chunk_id=CHUNK_ID
            )

            record = _sole_rag_record(audit_records)
            assert record.action == loggers.AUDIT_RAG_ACTION_CHUNK_VIZ
            assert record.outcome == loggers.AUDIT_OUTCOME_ERROR
            assert record.room_id == ROOM_ID
            assert record.db_path is None
            assert record.selector == CHUNK_ID
            assert record.reason == loggers.ROOM_UNKNOWN_CHUNK_ID

        elif not w_image:
            with pytest.raises(fastapi.HTTPException) as exc:
                await rooms_views.get_chunk_visualization(
                    room_id=ROOM_ID,
                    chunk_id=CHUNK_ID,
                    the_installation=the_installation,
                    the_room_authz=the_room_authz,
                    the_user_claims=THE_USER_CLAIMS,
                    the_logger=the_logger,
                )

            assert exc.value.status_code == 404
            assert exc.value.detail == (
                f"{loggers.ROOM_CHUNK_IMAGES_NOT_AVAILALBE}: {CHUNK_ID}"
            )
            the_logger.error.assert_called_once_with(
                loggers.ROOM_CHUNK_IMAGES_NOT_AVAILALBE, chunk_id=CHUNK_ID
            )

            record = _sole_rag_record(audit_records)
            assert record.action == loggers.AUDIT_RAG_ACTION_CHUNK_VIZ
            assert record.outcome == loggers.AUDIT_OUTCOME_ERROR
            assert record.room_id == ROOM_ID
            assert record.db_path == w_hrc_kws[w_chunk_index]["db_path"]
            assert record.selector == CHUNK_ID
            assert record.reason == loggers.ROOM_CHUNK_IMAGES_NOT_AVAILALBE

        else:
            found = await rooms_views.get_chunk_visualization(
                room_id=ROOM_ID,
                chunk_id=CHUNK_ID,
                the_installation=the_installation,
                the_room_authz=the_room_authz,
                the_user_claims=THE_USER_CLAIMS,
                the_logger=the_logger,
            )

            chunk_source = sources[w_chunk_index]
            assert found == models.ChunkVisualization(
                source=rag_sources[chunk_source],
                chunk_id=CHUNK_ID,
                document_uri=DOCUMENT_URI,
                images_base_64=PAGES_B64,
            )

            record = _sole_rag_record(audit_records)
            assert record.action == loggers.AUDIT_RAG_ACTION_CHUNK_VIZ
            assert record.outcome == loggers.AUDIT_OUTCOME_SUCCESS
            assert record.room_id == ROOM_ID
            assert record.db_path == w_hrc_kws[w_chunk_index]["db_path"]
            assert record.selector == CHUNK_ID
            assert record.result_refs == [DOCUMENT_URI]

            rag_w_chunk.visualize_chunk.assert_called_once_with(
                chunk,
                refs=None,
                expand=False,
            )
            for rag in rags:
                if rag is not rag_w_chunk:
                    rag.visualize_chunk.assert_not_called()

        room_config.list_haiku_rag_client_kw.assert_called_once_with(
            include_source=True,
        )

    the_installation.get_room_config.assert_awaited_once_with(
        room_id=ROOM_ID,
        user=THE_USER_CLAIMS,
        the_room_authz=the_room_authz,
        the_logger=the_logger,
    )
    the_logger.debug.assert_called_once_with(
        loggers.ROOM_GET_CHUNK_VISUALIZATION,
    )


@pytest.mark.anyio
@pytest.mark.parametrize("expand", [True, False])
@pytest.mark.parametrize(
    "refs_arg,expected_refs",
    [
        ('["#/texts/0", "#/texts/1"]', ["#/texts/0", "#/texts/1"]),
        ("not valid json", None),
        ('{"not": "a list"}', None),
        (None, None),
    ],
)
@mock.patch("haiku.rag.client.HaikuRAG")
@mock.patch("base64.b64encode")
async def test_get_chunk_visualization_refs_and_expand(
    b64enc,
    hr_klass,
    refs_arg,
    expected_refs,
    expand,
    audit_records,
):
    """refs (JSON list) and expand reach visualize_chunk."""
    ROOM_ID = "foo"
    CHUNK_ID = "test-chunk-123"
    DOCUMENT_URI = f"https://example.com/chunks/{CHUNK_ID}"
    PAGES_PNG = [mock.Mock(spec_set=["blob", "save"], blob="facedace8765")]
    b64enc.return_value.decode.return_value = "facedace8765"

    hr_insts = {"agent": mock.AsyncMock()}
    rag = hr_insts["agent"].__aenter__.return_value
    hr_klass.side_effect = hr_insts.values()

    chunk = hr_chunk.Chunk(
        chunk_id=CHUNK_ID,
        document_uri=DOCUMENT_URI,
        content="waaa",
    )
    rag.covers_multiple = False
    rag.source = None  # an unnamed single database
    rag.reader_for.return_value = rag
    rag.get_chunk_by_id.return_value = chunk
    rag.visualize_chunk.return_value = PAGES_PNG

    room_config = mock.create_autospec(config_rooms.RoomConfig)
    room_config.list_haiku_rag_client_kw = mock.Mock(
        spec_set=(),
        return_value=[
            {
                "source": "agent",
                "db_path": "/db/agent",
                "audit_db_path": "/db/agent",
            },
        ],
    )
    the_installation = mock.create_autospec(installation.Installation)
    the_installation.get_room_config.return_value = room_config
    the_room_authz = mock.create_autospec(authz.RoomAuthorizationPolicy)
    the_logger = mock.create_autospec(loggers.LogWrapper)

    found = await rooms_views.get_chunk_visualization(
        room_id=ROOM_ID,
        chunk_id=CHUNK_ID,
        refs=refs_arg,
        expand=expand,
        the_installation=the_installation,
        the_room_authz=the_room_authz,
        the_user_claims=THE_USER_CLAIMS,
        the_logger=the_logger,
    )

    assert found.chunk_id == CHUNK_ID
    assert found.database is None
    rag.visualize_chunk.assert_awaited_once_with(
        chunk,
        refs=expected_refs,
        expand=expand,
    )


def _federated_room_config(covered_names, chunks_by_name):
    """A room whose sole RAG config covers several named databases"""
    rag = mock.AsyncMock()
    rag.covers_multiple = True
    rag.source_names = covered_names
    rag.get_chunk_by_id.side_effect = lambda chunk_id, source=None: (
        chunks_by_name.get(source)
    )

    room_config = mock.create_autospec(config_rooms.RoomConfig)
    room_config.list_haiku_rag_client_kw = mock.Mock(
        spec_set=(),
        return_value=[
            {
                "source": "skill:rag",
                "db_path": None,
                "audit_db_path": "papers=/db/papers, wiki=/db/wiki",
            },
        ],
    )
    return rag, room_config


@pytest.mark.anyio
@mock.patch("haiku.rag.client.HaikuRAG")
@mock.patch("base64.b64encode")
async def test_get_chunk_visualization_federated(
    b64enc,
    hr_klass,
    audit_records,
):
    """The database holding the chunk owns the visualization"""
    ROOM_ID = "foo"
    CHUNK_ID = "test-chunk-123"
    DOCUMENT_URI = f"https://example.com/chunks/{CHUNK_ID}"
    PAGES_PNG = [mock.Mock(spec_set=["blob", "save"], blob="facedace8765")]
    b64enc.return_value.decode.return_value = "facedace8765"

    chunk = hr_chunk.Chunk(
        chunk_id=CHUNK_ID,
        document_uri=DOCUMENT_URI,
        content="waaa",
    )
    rag, room_config = _federated_room_config(
        ("papers", "wiki"),
        {"wiki": chunk},
    )
    owner = mock.AsyncMock()
    owner.visualize_chunk.return_value = PAGES_PNG
    rag.reader_for.return_value = owner

    hr_inst = mock.AsyncMock()
    hr_inst.__aenter__.return_value = rag
    hr_klass.side_effect = [hr_inst]

    the_installation = mock.create_autospec(installation.Installation)
    the_installation.get_room_config.return_value = room_config
    the_room_authz = mock.create_autospec(authz.RoomAuthorizationPolicy)
    the_logger = mock.create_autospec(loggers.LogWrapper)

    found = await rooms_views.get_chunk_visualization(
        room_id=ROOM_ID,
        chunk_id=CHUNK_ID,
        the_installation=the_installation,
        the_room_authz=the_room_authz,
        the_user_claims=THE_USER_CLAIMS,
        the_logger=the_logger,
    )

    assert found.chunk_id == CHUNK_ID
    assert found.database == "wiki"
    assert found.document_uri == DOCUMENT_URI

    # Asked the databases in turn, stopping at the one holding the chunk.
    assert rag.get_chunk_by_id.await_args_list == [
        mock.call(CHUNK_ID, source="papers"),
        mock.call(CHUNK_ID, source="wiki"),
    ]
    rag.reader_for.assert_awaited_once_with("wiki")
    owner.visualize_chunk.assert_awaited_once_with(
        chunk,
        refs=None,
        expand=False,
    )
    rag.visualize_chunk.assert_not_called()

    record = _sole_rag_record(audit_records)
    assert record.db_path == "papers=/db/papers, wiki=/db/wiki"


@pytest.mark.anyio
@mock.patch("haiku.rag.client.HaikuRAG")
@mock.patch("base64.b64encode")
async def test_get_chunk_visualization_one_named_database(
    b64enc,
    hr_klass,
    audit_records,
):
    """One named database reports its name, as search and documents do"""
    ROOM_ID = "foo"
    CHUNK_ID = "test-chunk-123"
    DOCUMENT_URI = f"https://example.com/chunks/{CHUNK_ID}"
    PAGES_PNG = [mock.Mock(spec_set=["blob", "save"], blob="facedace8765")]
    b64enc.return_value.decode.return_value = "facedace8765"

    chunk = hr_chunk.Chunk(
        chunk_id=CHUNK_ID,
        document_uri=DOCUMENT_URI,
        content="waaa",
    )
    # A one-entry 'rag_databases' opens as a single-database client that
    # keeps the configured name.
    rag = mock.AsyncMock()
    rag.covers_multiple = False
    rag.source = "papers"
    rag.reader_for.return_value = rag
    rag.get_chunk_by_id.return_value = chunk
    rag.visualize_chunk.return_value = PAGES_PNG

    room_config = mock.create_autospec(config_rooms.RoomConfig)
    room_config.list_haiku_rag_client_kw = mock.Mock(
        spec_set=(),
        return_value=[
            {
                "source": "skill:rag",
                "db_path": None,
                "audit_db_path": "papers=/db/papers",
            },
        ],
    )

    hr_inst = mock.AsyncMock()
    hr_inst.__aenter__.return_value = rag
    hr_klass.side_effect = [hr_inst]

    the_installation = mock.create_autospec(installation.Installation)
    the_installation.get_room_config.return_value = room_config
    the_room_authz = mock.create_autospec(authz.RoomAuthorizationPolicy)
    the_logger = mock.create_autospec(loggers.LogWrapper)

    found = await rooms_views.get_chunk_visualization(
        room_id=ROOM_ID,
        chunk_id=CHUNK_ID,
        the_installation=the_installation,
        the_room_authz=the_room_authz,
        the_user_claims=THE_USER_CLAIMS,
        the_logger=the_logger,
    )

    assert found.database == "papers"
    rag.get_chunk_by_id.assert_awaited_once_with(CHUNK_ID)
    rag.reader_for.assert_awaited_once_with("papers")


@pytest.mark.anyio
@mock.patch("haiku.rag.client.HaikuRAG")
async def test_get_chunk_visualization_federated_wo_chunk(
    hr_klass,
    audit_records,
):
    """A chunk in none of the covered databases is a 404"""
    ROOM_ID = "foo"
    CHUNK_ID = "test-chunk-123"

    rag, room_config = _federated_room_config(("papers", "wiki"), {})

    hr_inst = mock.AsyncMock()
    hr_inst.__aenter__.return_value = rag
    hr_klass.side_effect = [hr_inst]

    the_installation = mock.create_autospec(installation.Installation)
    the_installation.get_room_config.return_value = room_config
    the_room_authz = mock.create_autospec(authz.RoomAuthorizationPolicy)
    the_logger = mock.create_autospec(loggers.LogWrapper)

    with pytest.raises(fastapi.HTTPException) as exc:
        await rooms_views.get_chunk_visualization(
            room_id=ROOM_ID,
            chunk_id=CHUNK_ID,
            the_installation=the_installation,
            the_room_authz=the_room_authz,
            the_user_claims=THE_USER_CLAIMS,
            the_logger=the_logger,
        )

    assert exc.value.status_code == 404
    assert exc.value.detail == f"{loggers.ROOM_UNKNOWN_CHUNK_ID}: {CHUNK_ID}"
    rag.reader_for.assert_not_called()

    record = _sole_rag_record(audit_records)
    assert record.outcome == loggers.AUDIT_OUTCOME_ERROR
    assert record.db_path is None
    assert record.reason == loggers.ROOM_UNKNOWN_CHUNK_ID


@pytest.mark.anyio
@mock.patch("haiku.rag.client.HaikuRAG")
async def test_get_search_wo_title_uri_or_headings(hr_klass, audit_records):
    """A document with no title, URI or headings is a hit like any other"""
    ROOM_ID = "foo"
    QUERY = "waaa"

    hit = hr_chunk.SearchResult(
        content="Test content",
        score=1.0,
        chunk_id="test-chunk",
        document_id="test-document",
        document_uri=None,
        document_title=None,
        headings=None,
    )

    rag = mock.AsyncMock()
    rag.search.return_value = [hit]
    hr_inst = mock.AsyncMock()
    hr_inst.__aenter__.return_value = rag
    hr_klass.side_effect = [hr_inst]

    room_config = mock.create_autospec(config_rooms.RoomConfig)
    room_config.list_haiku_rag_client_kw = mock.Mock(
        spec_set=(),
        return_value=[
            {
                "source": "skill:rag",
                "db_path": "/db/rag",
                "audit_db_path": "/db/rag",
            },
        ],
    )
    the_installation = mock.create_autospec(installation.Installation)
    the_installation.get_room_config.return_value = room_config
    the_room_authz = mock.create_autospec(authz.RoomAuthorizationPolicy)
    the_logger = mock.create_autospec(loggers.LogWrapper)

    found = await rooms_views.get_search(
        query=QUERY,
        room_id=ROOM_ID,
        the_installation=the_installation,
        the_room_authz=the_room_authz,
        the_user_claims=THE_USER_CLAIMS,
        the_logger=the_logger,
    )

    (f_hit,) = found.hits
    assert f_hit.document_title is None
    assert f_hit.document_uri is None
    assert f_hit.headings == []


@pytest.mark.anyio
@pytest.mark.parametrize("w_search_type", [False, True])
@pytest.mark.parametrize(
    "w_hrc_kws",
    [
        [],
        [{"source": "agent", "db_path": "/db/agent", "foo": "bar"}],
        [{"source": "skill:test", "db_path": "/db/skill", "foo": "bar"}],
        [{"source": "tool:test", "db_path": "/db/tool", "foo": "bar"}],
        [
            {"source": "skill:test", "db_path": "/db/skill", "foo": "bar"},
            {"source": "tool:test", "db_path": "/db/tool", "foo": "bar"},
        ],
    ],
)
@mock.patch("haiku.rag.client.HaikuRAG")
async def test_get_search(
    hr_klass,
    w_hrc_kws,
    w_search_type,
    temp_dir,
    room_configs,
    audit_records,
):
    QUERY = "test query"
    SEARCH_TYPE = "hybrid"
    ROOM_ID = "foo"

    search_type_kw = {}
    if w_search_type:
        exp_search_type = search_type_kw["search_type"] = SEARCH_TYPE
    else:
        exp_search_type = "hybrid"

    w_hrc_kws = [
        kws | {"audit_db_path": str(kws["db_path"])} for kws in w_hrc_kws
    ]
    sources = [kws["source"] for kws in w_hrc_kws]
    hr_insts = {source: mock.AsyncMock() for source in sources}
    hr_entereds = {
        key: value.__aenter__.return_value for key, value in hr_insts.items()
    }
    hr_klass.side_effect = hr_insts.values()

    search_results = [
        hr_chunk.SearchResult(
            content=f"Test content #{i_source}",
            score=float(i_source) / 10 + 1,
            chunk_id=f"test-chunk-{i_source}",
            document_id=f"test-document-id-{i_source}",
            document_uri=(
                f"https://{source.replace(':', '_')}.example.com/"
                f"documents/document-{i_source}"
            ),
            document_title=f"Test Document #{i_source}",
            document_meta={"foo": "bar"},
            page_numbers=[100 - i_source],
            headings=[f"Test Heading #{i_source}"],
            labels=[f"test-label-{i_source}"],
            image_data={f"img-{i_source:03}": "abcdef0123456789"},
            source=f"db-{i_source}",
        )
        for i_source, source in enumerate(sources)
    ]

    the_installation = mock.create_autospec(installation.Installation)

    if ROOM_ID not in room_configs:
        the_installation.get_room_config.side_effect = KeyError("testing")
    else:
        the_installation.get_room_config.return_value = room_configs[ROOM_ID]

    the_room_authz = mock.create_autospec(authz.RoomAuthorizationPolicy)
    the_logger = mock.create_autospec(loggers.LogWrapper)

    if ROOM_ID not in room_configs:
        with pytest.raises(fastapi.HTTPException) as exc:
            await rooms_views.get_search(
                query=QUERY,
                room_id=ROOM_ID,
                **search_type_kw,
                the_installation=the_installation,
                the_room_authz=the_room_authz,
                the_user_claims=THE_USER_CLAIMS,
                the_logger=the_logger,
            )

        assert exc.value.status_code == 404
        assert exc.value.detail == (
            f"{loggers.ROOM_UNKNOWN_ROOM_ID}: {ROOM_ID}"
        )
        the_logger.exception.assert_called_once_with(
            loggers.ROOM_UNKNOWN_ROOM_ID,
            room_id=ROOM_ID,
        )
        assert audit_records == []

    else:
        room_config = room_configs[ROOM_ID]
        room_config.list_haiku_rag_client_kw.return_value = w_hrc_kws

        for hr_entered, search_result in zip(
            hr_entereds.values(),
            search_results,
            strict=True,
        ):
            hr_entered.search.return_value = [search_result]

        found = await rooms_views.get_search(
            query=QUERY,
            search_type=SEARCH_TYPE,
            room_id=ROOM_ID,
            the_installation=the_installation,
            the_room_authz=the_room_authz,
            the_user_claims=THE_USER_CLAIMS,
            the_logger=the_logger,
        )

        assert found.query == QUERY
        assert found.search_type == SEARCH_TYPE

        for f_hit, source, exp_result in zip(
            found.hits,
            sources,
            search_results,
            strict=True,
        ):
            if source == "agent":
                assert f_hit.source.source_type == "agent"
                assert f_hit.source.name is None
            else:
                source_type, name = source.split(":")
                assert f_hit.source.source_type == source_type
                assert f_hit.source.name == name

            assert f_hit.database == exp_result.source
            assert f_hit.content == exp_result.content
            assert f_hit.score == exp_result.score
            assert f_hit.chunk_id == exp_result.chunk_id
            assert f_hit.document_id == exp_result.document_id
            assert f_hit.document_uri == exp_result.document_uri
            assert f_hit.document_title == exp_result.document_title
            assert f_hit.document_meta == exp_result.document_meta
            assert f_hit.headings == exp_result.headings
            assert f_hit.page_numbers == exp_result.page_numbers
            assert f_hit.labels == exp_result.labels

        for hr_entered in hr_entereds.values():
            hr_entered.search.assert_awaited_once_with(
                query=QUERY,
                search_type=exp_search_type,
            )

        rag_records = [
            record
            for record in audit_records
            if record.__dict__.get(loggers.SOLIPLEX_AUDIT_LOGGER_SCOPE_EXTRA)
            == loggers.AuditLogScopes.RAG_ACCESS
        ]
        assert len(rag_records) == len(sources)
        for record, kws, exp_result in zip(
            rag_records, w_hrc_kws, search_results, strict=True
        ):
            assert record.action == loggers.AUDIT_RAG_ACTION_SEARCH
            assert record.outcome == loggers.AUDIT_OUTCOME_SUCCESS
            assert record.room_id == ROOM_ID
            assert record.db_path == kws["db_path"]
            assert record.selector == QUERY
            assert record.result_refs == [exp_result.chunk_id]
