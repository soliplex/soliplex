import datetime
import pathlib
from unittest import mock

import fastapi
import pytest
from haiku.rag.store.models import chunk as hr_chunk

from soliplex import config
from soliplex import installation
from soliplex import models
from soliplex.views import rooms as rooms_views

NOW = datetime.datetime.now(datetime.UTC)

ROOM_IDS = ["foo", "bar", "baz"]

USER_NAME = "phreddy"
GIVEN_NAME = "Phred"
FAMILY_NAME = "Phlyntstone"
EMAIL = "phreddy@example.com"

AUTH_USER = {
    "preferred_username": USER_NAME,
    "given_name": GIVEN_NAME,
    "family_name": FAMILY_NAME,
    "email": EMAIL,
}

UNKNOWN_USER = {
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
        room_id: mock.create_autospec(config.RoomConfig, sort_key=room_id)
        for room_id in request.param
    }


@pytest.mark.anyio
@mock.patch("soliplex.authn.authenticate")
@mock.patch("soliplex.models.Room.from_config")
async def test_get_rooms(fc, auth_fn, room_configs):
    request = mock.create_autospec(fastapi.Request)

    the_installation = mock.create_autospec(installation.Installation)
    the_installation.get_room_configs.return_value = room_configs
    token = object()

    found = await rooms_views.get_rooms(
        request,
        the_installation=the_installation,
        token=token,
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

    the_installation.get_room_configs.assert_called_once_with(
        auth_fn.return_value,
    )
    auth_fn.assert_called_once_with(the_installation, token)


@pytest.mark.anyio
@mock.patch("soliplex.authn.authenticate")
@mock.patch("soliplex.models.Room.from_config")
async def test_get_room(fc, auth_fn, room_configs):
    ROOM_ID = "foo"

    request = mock.create_autospec(fastapi.Request)

    the_installation = mock.create_autospec(installation.Installation)

    if ROOM_ID not in room_configs:
        the_installation.get_room_config.side_effect = KeyError("testing")
    else:
        the_installation.get_room_config.return_value = room_configs[ROOM_ID]

    token = object()

    if ROOM_ID not in room_configs:
        with pytest.raises(fastapi.HTTPException) as exc:
            await rooms_views.get_room(
                request,
                ROOM_ID,
                the_installation=the_installation,
                token=token,
            )

        assert exc.value.status_code == 404
        assert exc.value.detail == "No such room: foo"

    else:
        found = await rooms_views.get_room(
            request,
            ROOM_ID,
            the_installation=the_installation,
            token=token,
        )

        assert found is fc.return_value
        fc.assert_called_once_with(room_configs[ROOM_ID])

    the_installation.get_room_config.assert_called_once_with(
        ROOM_ID,
        auth_fn.return_value,
    )
    auth_fn.assert_called_once_with(the_installation, token)


@pytest.mark.anyio
@pytest.mark.parametrize("w_image", [False, True])
@mock.patch("soliplex.authn.authenticate")
async def test_get_room_bg_image(auth_fn, temp_dir, w_image, room_configs):
    ROOM_ID = "foo"
    IMAGE_FILENAME = "logo.svg"

    image_path = temp_dir / IMAGE_FILENAME

    request = mock.create_autospec(fastapi.Request)

    the_installation = mock.create_autospec(installation.Installation)

    if ROOM_ID not in room_configs:
        the_installation.get_room_config.side_effect = KeyError("testing")
    else:
        the_installation.get_room_config.return_value = room_configs[ROOM_ID]

    token = object()

    if ROOM_ID in room_configs:
        if w_image:
            room_configs[ROOM_ID].get_logo_image.return_value = image_path
        else:
            room_configs[ROOM_ID].get_logo_image.return_value = None

    if ROOM_ID not in room_configs:
        with pytest.raises(fastapi.HTTPException) as exc:
            await rooms_views.get_room_bg_image(
                request,
                room_id=ROOM_ID,
                the_installation=the_installation,
                token=token,
            )

        assert exc.value.status_code == 404
        assert exc.value.detail == "No such room: foo"
    else:
        if w_image:
            found = await rooms_views.get_room_bg_image(
                request,
                room_id=ROOM_ID,
                the_installation=the_installation,
                token=token,
            )
            # Actual image data is marshalled by fastapi framework
            assert found == str(image_path)
        else:
            with pytest.raises(fastapi.HTTPException) as exc:
                await rooms_views.get_room_bg_image(
                    request,
                    room_id=ROOM_ID,
                    the_installation=the_installation,
                    token=token,
                )

            assert exc.value.status_code == 404
            assert exc.value.detail == "No image for room"

    the_installation.get_room_config.assert_called_once_with(
        ROOM_ID,
        auth_fn.return_value,
    )
    auth_fn.assert_called_once_with(the_installation, token)


@pytest.mark.anyio
@pytest.mark.parametrize("w_error", [False, True])
@mock.patch("soliplex.mcp_auth.generate_url_safe_token")
@mock.patch("soliplex.authn.authenticate")
async def test_get_room_mcp_token(auth_fn, gust, w_error):
    ROOM_ID = "test-room"
    ROOM_CONFIG = object()
    MCP_TOKEN = gust.return_value = "DEADBEEF"

    request = fastapi.Request(scope={"type": "http"})

    the_installation = mock.create_autospec(installation.Installation)

    token = object()
    wylma = auth_fn.return_value = {
        "full_name": "Wylma Phlyntstone",
        "email": "wylma@exmple.com",
    }

    if w_error:
        the_installation.get_room_config.side_effect = ValueError("testing")
    else:
        the_installation.get_room_config.return_value = ROOM_CONFIG

    if w_error:
        with pytest.raises(fastapi.HTTPException) as exc:
            await rooms_views.get_room_mcp_token(
                request,
                room_id=ROOM_ID,
                the_installation=the_installation,
                token=token,
            )

        assert exc.value.status_code == 404

    else:
        found = await rooms_views.get_room_mcp_token(
            request,
            room_id=ROOM_ID,
            the_installation=the_installation,
            token=token,
        )

        expected = {
            "room_id": ROOM_ID,
            "mcp_token": MCP_TOKEN,
        }
        assert found.model_dump() == expected

        gust.assert_called_once_with(
            the_installation.get_secret.return_value,
            ROOM_ID,
            **wylma,
        )
        the_installation.get_secret.assert_called_once_with(
            "URL_SAFE_TOKEN_SECRET"
        )

    the_installation.get_room_config.assert_called_once_with(
        ROOM_ID,
        user=auth_fn.return_value,
    )
    auth_fn.assert_called_once_with(the_installation, token)


@pytest.mark.anyio
@pytest.mark.parametrize("w_hr_tool", [False, True])
@mock.patch("haiku.rag.client.HaikuRAG")
@mock.patch("soliplex.authn.authenticate")
async def test_get_room_documents(
    auth_fn,
    hr_klass,
    temp_dir,
    w_hr_tool,
    room_configs,
):
    ROOM_ID = "foo"

    hr_inst = hr_klass.return_value
    hr_entered = hr_inst.__aenter__.return_value

    request = mock.create_autospec(fastapi.Request)

    the_installation = mock.create_autospec(installation.Installation)

    if ROOM_ID not in room_configs:
        the_installation.get_room_config.side_effect = KeyError("testing")
    else:
        the_installation.get_room_config.return_value = room_configs[ROOM_ID]

    token = object()

    hr_config = object()
    db_path = pathlib.Path("/tmp/rag.db")

    if ROOM_ID in room_configs:
        non_hr_tool_config = mock.create_autospec(config.ToolConfig)
        tool_configs = room_configs[ROOM_ID].tool_configs = {
            "non_hr": non_hr_tool_config,
        }

        if w_hr_tool:
            tool_config = mock.create_autospec(
                config.ToolConfig,
                haiku_rag_config=hr_config,
                rag_lancedb_path=db_path,
            )
            tool_configs["testing"] = tool_config

            hr_entered.list_documents.return_value = [DOCUMENT]
            exp_docs = {DOCUMENT_ID: RAG_DOCUMENT}
        else:
            exp_docs = {}

    if ROOM_ID not in room_configs:
        with pytest.raises(fastapi.HTTPException) as exc:
            await rooms_views.get_room_documents(
                request,
                room_id=ROOM_ID,
                the_installation=the_installation,
                token=token,
            )

        assert exc.value.status_code == 404
        assert exc.value.detail == "No such room: foo"
    else:
        found = await rooms_views.get_room_documents(
            request,
            room_id=ROOM_ID,
            the_installation=the_installation,
            token=token,
        )

        assert found == models.RoomDocuments(
            room_id=ROOM_ID,
            document_set=exp_docs,
        )

        if w_hr_tool:
            hr_entered.list_documents.assert_called_once_with()

            hr_klass.assert_called_once_with(
                db_path=db_path,
                config=hr_config,
            )
        else:
            hr_entered.list_documents.assert_not_called()
            hr_klass.list_documents.assert_not_called()

    the_installation.get_room_config.assert_called_once_with(
        ROOM_ID,
        auth_fn.return_value,
    )
    auth_fn.assert_called_once_with(the_installation, token)


@pytest.mark.anyio
@pytest.mark.parametrize("w_chunk", [False, True])
@pytest.mark.parametrize("w_hr_tool", [False, True])
@mock.patch("haiku.rag.client.HaikuRAG")
@mock.patch("base64.b64encode")
@mock.patch("soliplex.authn.authenticate")
async def test_get_chunk_visualization(
    auth_fn,
    b64enc,
    hr_klass,
    temp_dir,
    w_hr_tool,
    w_chunk,
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

    hr_inst = hr_klass.return_value
    hr_entered = hr_inst.__aenter__.return_value
    chunk_repo = hr_entered.chunk_repository

    request = mock.create_autospec(fastapi.Request)

    the_installation = mock.create_autospec(installation.Installation)

    if ROOM_ID not in room_configs:
        the_installation.get_room_config.side_effect = KeyError("testing")
    else:
        the_installation.get_room_config.return_value = room_configs[ROOM_ID]

    token = object()

    hr_config = object()
    db_path = pathlib.Path("/tmp/rag.db")

    if ROOM_ID in room_configs:
        non_hr_tool_config = mock.create_autospec(config.ToolConfig)
        tool_configs = room_configs[ROOM_ID].tool_configs = {
            "non_hr": non_hr_tool_config,
        }

        if w_hr_tool:
            tool_config = mock.create_autospec(
                config.ToolConfig,
                haiku_rag_config=hr_config,
                rag_lancedb_path=db_path,
            )
            tool_configs["testing"] = tool_config

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
                request,
                room_id=ROOM_ID,
                chunk_id=CHUNK_ID,
                the_installation=the_installation,
                token=token,
            )

        assert exc.value.status_code == 404
        assert exc.value.detail == "No such room: foo"

    elif not w_hr_tool:
        with pytest.raises(fastapi.HTTPException) as exc:
            await rooms_views.get_chunk_visualization(
                request,
                room_id=ROOM_ID,
                chunk_id=CHUNK_ID,
                the_installation=the_installation,
                token=token,
            )

        assert exc.value.status_code == 404
        assert exc.value.detail == f"Chunk images not available: {CHUNK_ID}"

    elif not w_chunk:
        with pytest.raises(fastapi.HTTPException) as exc:
            await rooms_views.get_chunk_visualization(
                request,
                room_id=ROOM_ID,
                chunk_id=CHUNK_ID,
                the_installation=the_installation,
                token=token,
            )

        assert exc.value.status_code == 404
        assert exc.value.detail == f"Chunk not found: {CHUNK_ID}"

    else:
        found = await rooms_views.get_chunk_visualization(
            request,
            room_id=ROOM_ID,
            chunk_id=CHUNK_ID,
            the_installation=the_installation,
            token=token,
        )

        assert found == models.ChunkVisualization(
            chunk_id=CHUNK_ID,
            document_uri=DOCUMENT_URI,
            images_base_64=PAGES_B64,
        )

        hr_entered.visualize_chunk.assert_called_once_with(chunk)
        chunk_repo.get_by_id.assert_called_once_with(CHUNK_ID)
        hr_klass.assert_called_once_with(
            db_path=db_path,
            config=hr_config,
        )

    the_installation.get_room_config.assert_called_once_with(
        ROOM_ID,
        auth_fn.return_value,
    )
    auth_fn.assert_called_once_with(the_installation, token)
