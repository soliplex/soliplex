import datetime
from unittest import mock

import fastapi
import pytest
from haiku.rag.store.models import chunk as hr_chunk

from soliplex import authz as authz_package
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
DOCUMENT = mock.Mock(
    spec_set=list(DOCUMENT_KWARGS.keys()),
    **DOCUMENT_KWARGS,
)
RAG_DOCUMENT = models.RAGDocument(**DOCUMENT_KWARGS)


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
    the_authz_policy = mock.create_autospec(authz_package.AuthorizationPolicy)
    the_logger = mock.create_autospec(loggers.LogWrapper)

    found = await rooms_views.get_rooms(
        the_installation=the_installation,
        the_authz_policy=the_authz_policy,
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
        the_authz_policy=the_authz_policy,
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

    the_authz_policy = mock.create_autospec(authz_package.AuthorizationPolicy)
    the_logger = mock.create_autospec(loggers.LogWrapper)

    if ROOM_ID not in room_configs:
        with pytest.raises(fastapi.HTTPException) as exc:
            await rooms_views.get_room(
                ROOM_ID,
                the_installation=the_installation,
                the_authz_policy=the_authz_policy,
                the_user_claims=THE_USER_CLAIMS,
                the_logger=the_logger,
            )

        assert exc.value.status_code == 404
        assert exc.value.detail == loggers.ROOM_UNKNOWN_ROOM_ID % ROOM_ID
        the_logger.exception.assert_called_once_with(
            loggers.ROOM_UNKNOWN_ROOM_ID,
            ROOM_ID,
        )

    else:
        found = await rooms_views.get_room(
            ROOM_ID,
            the_installation=the_installation,
            the_authz_policy=the_authz_policy,
            the_user_claims=THE_USER_CLAIMS,
            the_logger=the_logger,
        )

        assert found is fc.return_value
        fc.assert_called_once_with(room_configs[ROOM_ID])

    the_installation.get_room_config.assert_awaited_once_with(
        room_id=ROOM_ID,
        user=THE_USER_CLAIMS,
        the_authz_policy=the_authz_policy,
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

    the_authz_policy = mock.create_autospec(authz_package.AuthorizationPolicy)
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
                the_authz_policy=the_authz_policy,
                the_user_claims=THE_USER_CLAIMS,
                the_logger=the_logger,
            )

        assert exc.value.status_code == 404
        assert exc.value.detail == loggers.ROOM_UNKNOWN_ROOM_ID % ROOM_ID
        the_logger.exception.assert_called_once_with(
            loggers.ROOM_UNKNOWN_ROOM_ID, ROOM_ID
        )
    else:
        if w_image:
            found = await rooms_views.get_room_bg_image(
                room_id=ROOM_ID,
                the_installation=the_installation,
                the_authz_policy=the_authz_policy,
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
                    the_authz_policy=the_authz_policy,
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
        the_authz_policy=the_authz_policy,
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
    the_authz_policy = mock.create_autospec(authz_package.AuthorizationPolicy)
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
                the_authz_policy=the_authz_policy,
                the_user_claims=THE_USER_CLAIMS,
                the_logger=the_logger,
            )

        assert exc.value.status_code == 404
        assert exc.value.detail == loggers.ROOM_UNKNOWN_ROOM_ID % ROOM_ID
        the_logger.exception.assert_called_once_with(
            loggers.ROOM_UNKNOWN_ROOM_ID,
            ROOM_ID,
        )

    else:
        found = await rooms_views.get_room_mcp_token(
            room_id=ROOM_ID,
            the_installation=the_installation,
            the_authz_policy=the_authz_policy,
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
        the_authz_policy=the_authz_policy,
        the_logger=the_logger,
    )
    the_logger.debug.assert_called_once_with(loggers.ROOM_GET_ROOM_MCP_TOKEN)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "w_kws, expected",
    [
        ([], None),
        ([{"foo": "bar"}], {"foo": "bar"}),
        ([{"foo": "bar"}, {"spam": "qux"}], {"foo": "bar"}),
    ],
)
async def test__get_haiku_rag_client_kw(w_kws, expected):
    room_config = mock.create_autospec(config_rooms.RoomConfig)
    room_config.list_haiku_rag_client_kw.return_value = w_kws

    found = rooms_views._get_haiku_rag_client_kw(room_config)

    assert found == expected


@pytest.mark.anyio
@pytest.mark.parametrize("w_hrck", [None, {"foo": "bar"}])
@mock.patch("soliplex.views.rooms._get_haiku_rag_client_kw")
@mock.patch("haiku.rag.client.HaikuRAG")
async def test_get_room_documents(
    hr_klass,
    ghrck,
    w_hrck,
    temp_dir,
    room_configs,
):
    ghrck.return_value = w_hrck
    ROOM_ID = "foo"

    hr_inst = hr_klass.return_value
    hr_entered = hr_inst.__aenter__.return_value

    the_installation = mock.create_autospec(installation.Installation)

    if ROOM_ID not in room_configs:
        the_installation.get_room_config.side_effect = KeyError("testing")
    else:
        the_installation.get_room_config.return_value = room_configs[ROOM_ID]

    the_authz_policy = mock.create_autospec(authz_package.AuthorizationPolicy)
    the_logger = mock.create_autospec(loggers.LogWrapper)

    if ROOM_ID in room_configs:
        if w_hrck:
            hr_entered.list_documents.return_value = [DOCUMENT]
            exp_docs = {DOCUMENT_ID: RAG_DOCUMENT}
        else:
            exp_docs = {}

    if ROOM_ID not in room_configs:
        with pytest.raises(fastapi.HTTPException) as exc:
            await rooms_views.get_room_documents(
                room_id=ROOM_ID,
                the_installation=the_installation,
                the_authz_policy=the_authz_policy,
                the_user_claims=THE_USER_CLAIMS,
                the_logger=the_logger,
            )

        assert exc.value.status_code == 404
        assert exc.value.detail == loggers.ROOM_UNKNOWN_ROOM_ID % ROOM_ID
        the_logger.exception.assert_called_once_with(
            loggers.ROOM_UNKNOWN_ROOM_ID,
            ROOM_ID,
        )
    else:
        found = await rooms_views.get_room_documents(
            room_id=ROOM_ID,
            the_installation=the_installation,
            the_authz_policy=the_authz_policy,
            the_user_claims=THE_USER_CLAIMS,
            the_logger=the_logger,
        )

        assert found == models.RoomRAGDocuments(
            room_id=ROOM_ID,
            document_set=exp_docs,
        )

        if w_hrck:
            hr_entered.list_documents.assert_called_once_with()
            hr_klass.assert_called_once_with(**w_hrck)
        else:
            hr_entered.list_documents.assert_not_called()
            hr_klass.list_documents.assert_not_called()

    the_installation.get_room_config.assert_awaited_once_with(
        room_id=ROOM_ID,
        user=THE_USER_CLAIMS,
        the_authz_policy=the_authz_policy,
        the_logger=the_logger,
    )
    the_logger.debug.assert_called_once_with(loggers.ROOM_GET_ROOM_DOCUMENTS)


@pytest.mark.anyio
@pytest.mark.parametrize("w_chunk", [False, True])
@pytest.mark.parametrize("w_hrck", [None, {"foo": "bar"}])
@mock.patch("soliplex.views.rooms._get_haiku_rag_client_kw")
@mock.patch("haiku.rag.client.HaikuRAG")
@mock.patch("base64.b64encode")
async def test_get_chunk_visualization(
    b64enc,
    hr_klass,
    ghrck,
    w_hrck,
    w_chunk,
    temp_dir,
    room_configs,
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
    ghrck.return_value = w_hrck

    hr_inst = hr_klass.return_value
    hr_entered = hr_inst.__aenter__.return_value
    chunk_repo = hr_entered.chunk_repository

    the_installation = mock.create_autospec(installation.Installation)

    if ROOM_ID not in room_configs:
        the_installation.get_room_config.side_effect = KeyError("testing")
    else:
        the_installation.get_room_config.return_value = room_configs[ROOM_ID]

    the_authz_policy = mock.create_autospec(authz_package.AuthorizationPolicy)
    the_logger = mock.create_autospec(loggers.LogWrapper)

    if ROOM_ID in room_configs:
        if w_hrck:
            if w_chunk:
                chunk = hr_chunk.Chunk(
                    chunk_id=CHUNK_ID,
                    document_uri=DOCUMENT_URI,
                    content="waaa",
                )
                chunk_repo.get_by_id.return_value = chunk

                hr_entered.visualize_chunk.return_value = PAGES_PNG
            else:
                chunk_repo.get_by_id.return_value = None

    if ROOM_ID not in room_configs:
        with pytest.raises(fastapi.HTTPException) as exc:
            await rooms_views.get_chunk_visualization(
                room_id=ROOM_ID,
                chunk_id=CHUNK_ID,
                the_installation=the_installation,
                the_authz_policy=the_authz_policy,
                the_user_claims=THE_USER_CLAIMS,
                the_logger=the_logger,
            )

        assert exc.value.status_code == 404
        assert exc.value.detail == loggers.ROOM_UNKNOWN_ROOM_ID % ROOM_ID
        the_logger.exception.assert_called_once_with(
            loggers.ROOM_UNKNOWN_ROOM_ID,
            ROOM_ID,
        )

    elif w_hrck is None:
        with pytest.raises(fastapi.HTTPException) as exc:
            await rooms_views.get_chunk_visualization(
                room_id=ROOM_ID,
                chunk_id=CHUNK_ID,
                the_installation=the_installation,
                the_authz_policy=the_authz_policy,
                the_user_claims=THE_USER_CLAIMS,
                the_logger=the_logger,
            )

        assert exc.value.status_code == 404
        assert exc.value.detail == (
            loggers.ROOM_CHUNK_IMAGES_NOT_AVAILALBE % CHUNK_ID
        )
        the_logger.error.assert_called_once_with(
            loggers.ROOM_CHUNK_IMAGES_NOT_AVAILALBE, CHUNK_ID
        )

    elif not w_chunk:
        with pytest.raises(fastapi.HTTPException) as exc:
            await rooms_views.get_chunk_visualization(
                room_id=ROOM_ID,
                chunk_id=CHUNK_ID,
                the_installation=the_installation,
                the_authz_policy=the_authz_policy,
                the_user_claims=THE_USER_CLAIMS,
                the_logger=the_logger,
            )

        assert exc.value.status_code == 404
        assert exc.value.detail == (loggers.ROOM_UNKNOWN_CHUNK_ID % CHUNK_ID)
        the_logger.error.assert_called_once_with(
            loggers.ROOM_UNKNOWN_CHUNK_ID, CHUNK_ID
        )

    else:
        found = await rooms_views.get_chunk_visualization(
            room_id=ROOM_ID,
            chunk_id=CHUNK_ID,
            the_installation=the_installation,
            the_authz_policy=the_authz_policy,
            the_user_claims=THE_USER_CLAIMS,
            the_logger=the_logger,
        )

        assert found == models.ChunkVisualization(
            chunk_id=CHUNK_ID,
            document_uri=DOCUMENT_URI,
            images_base_64=PAGES_B64,
        )

        hr_entered.visualize_chunk.assert_called_once_with(chunk)
        chunk_repo.get_by_id.assert_called_once_with(CHUNK_ID)
        hr_klass.assert_called_once_with(**w_hrck)

    the_installation.get_room_config.assert_awaited_once_with(
        room_id=ROOM_ID,
        user=THE_USER_CLAIMS,
        the_authz_policy=the_authz_policy,
        the_logger=the_logger,
    )
    the_logger.debug.assert_called_once_with(
        loggers.ROOM_GET_CHUNK_VISUALIZATION,
    )


@pytest.mark.anyio
@pytest.mark.parametrize("w_search_type", [False, True])
@pytest.mark.parametrize(
    "w_hrc_kws",
    [
        [],
        [{"source": "agent", "foo": "bar"}],
        [{"source": "skill:test", "foo": "bar"}],
        [{"source": "tool:test", "foo": "bar"}],
        [
            {"source": "skill:test", "foo": "bar"},
            {"source": "tool:test", "foo": "bar"},
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
):
    QUERY = "test query"
    SEARCH_TYPE = "hybrid"
    ROOM_ID = "foo"

    search_type_kw = {}
    if w_search_type:
        exp_search_type = search_type_kw["search_type"] = SEARCH_TYPE
    else:
        exp_search_type = "hybrid"

    w_hrc_kws = [kws.copy() for kws in w_hrc_kws]
    sources = [kws["source"] for kws in w_hrc_kws]

    search_results = [
        hr_chunk.SearchResult(
            content=f"Test content #{i_hrc_kw}",
            score=float(i_hrc_kw) / 10 + 1,
            chunk_id=f"test-chunk-{i_hrc_kw}",
            document_id=f"test-document-id-{i_hrc_kw}",
            document_uri=(
                f"https://{hrc_kw['source'].replace(':', '_')}.example.com/"
                f"documents/document-{i_hrc_kw}"
            ),
            document_title=f"Test Document #{i_hrc_kw}",
            headings=[f"test-heading-{i_hrc_kw}"],
            page_numbers=[i_hrc_kw],
            labels=[f"test-label-{i_hrc_kw}"],
        )
        for i_hrc_kw, hrc_kw in enumerate(w_hrc_kws)
    ]
    hr_insts = {hrc_kws["source"]: mock.AsyncMock() for hrc_kws in w_hrc_kws}
    hr_entereds = {
        key: value.__aenter__.return_value for key, value in hr_insts.items()
    }
    hr_klass.side_effect = hr_insts.values()

    the_installation = mock.create_autospec(installation.Installation)

    if ROOM_ID not in room_configs:
        the_installation.get_room_config.side_effect = KeyError("testing")
    else:
        the_installation.get_room_config.return_value = room_configs[ROOM_ID]

    the_authz_policy = mock.create_autospec(authz_package.AuthorizationPolicy)
    the_logger = mock.create_autospec(loggers.LogWrapper)

    if ROOM_ID not in room_configs:
        with pytest.raises(fastapi.HTTPException) as exc:
            await rooms_views.get_search(
                query=QUERY,
                room_id=ROOM_ID,
                **search_type_kw,
                the_installation=the_installation,
                the_authz_policy=the_authz_policy,
                the_user_claims=THE_USER_CLAIMS,
                the_logger=the_logger,
            )

        assert exc.value.status_code == 404
        assert exc.value.detail == loggers.ROOM_UNKNOWN_ROOM_ID % ROOM_ID
        the_logger.exception.assert_called_once_with(
            loggers.ROOM_UNKNOWN_ROOM_ID,
            ROOM_ID,
        )

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
            the_authz_policy=the_authz_policy,
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

            assert f_hit.content == exp_result.content
            assert f_hit.score == exp_result.score
            assert f_hit.chunk_id == exp_result.chunk_id
            assert f_hit.document_id == exp_result.document_id
            assert f_hit.document_uri == exp_result.document_uri
            assert f_hit.document_title == exp_result.document_title
            assert f_hit.headings == exp_result.headings
            assert f_hit.page_numbers == exp_result.page_numbers
            assert f_hit.labels == exp_result.labels

        for hr_entered in hr_entereds.values():
            hr_entered.search.assert_awaited_once_with(
                query=QUERY,
                search_type=exp_search_type,
            )
