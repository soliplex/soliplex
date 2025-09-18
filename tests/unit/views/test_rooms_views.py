from unittest import mock

import fastapi
import pytest

from soliplex import config
from soliplex import installation
from soliplex.views import rooms as rooms_views

ROOM_IDS = ["foo", "bar", "baz"]


@pytest.fixture(scope="module", params=[(), ROOM_IDS])
def room_configs(request):
    return {
        room_id: mock.create_autospec(config.RoomConfig, sort_key=room_id)
        for room_id in request.param
    }


@pytest.mark.anyio
@mock.patch("soliplex.auth.authenticate")
@mock.patch("soliplex.models.Room.from_config")
async def test_get_rooms(fc, auth_fn, room_configs):

    request = mock.create_autospec(fastapi.Request)

    the_installation = mock.create_autospec(installation.Installation)
    the_installation.get_room_configs.return_value = room_configs
    token = object()

    found = await rooms_views.get_rooms(
        request, the_installation=the_installation, token=token,
    )

    for (found_key, found_room), room_id, fc_call in zip(
        found.items(),   # should already be sorted
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
@mock.patch("soliplex.auth.authenticate")
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
        ROOM_ID, auth_fn.return_value,
    )
    auth_fn.assert_called_once_with(the_installation, token)


@pytest.mark.anyio
@pytest.mark.parametrize("w_image", [False, True])
@mock.patch("soliplex.auth.authenticate")
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
        ROOM_ID, auth_fn.return_value,
    )
    auth_fn.assert_called_once_with(the_installation, token)


@pytest.mark.anyio
@pytest.mark.parametrize("w_error", [False, True])
@mock.patch("soliplex.mcp_auth.generate_url_safe_token")
@mock.patch("soliplex.auth.authenticate")
async def test_get_room_mcp_token(
    auth_fn, gust, w_error
):
    ROOM_ID = "test-room"
    ROOM_CONFIG = object()
    MCP_TOKEN = gust.return_value = "DEADBEEF"

    request = fastapi.Request(scope={"type": "http"})

    the_installation = mock.create_autospec(installation.Installation)

    token = object()
    wylma = auth_fn.return_value = {
        "full_name": "Wylma Phlyntstone", "email": "wylma@exmple.com",
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

        gust.assert_called_once_with(ROOM_ID, **wylma)

    the_installation.get_room_config.assert_called_once_with(
        ROOM_ID, user=auth_fn.return_value,
    )
    auth_fn.assert_called_once_with(the_installation, token)
