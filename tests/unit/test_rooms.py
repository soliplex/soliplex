from unittest import mock

import fastapi
import pytest

from soliplex import config
from soliplex import installation
from soliplex import rooms

ROOM_IDS = ["foo", "bar", "baz"]


@pytest.fixture(scope="module", params=[(), ROOM_IDS])
def room_configs(request):
    return {
        room_id: mock.create_autospec(config.RoomConfig, sort_key=room_id)
        for room_id in request.param
    }


@pytest.mark.anyio
@mock.patch("soliplex.models.Room.from_config")
async def test_get_rooms(fc, room_configs):

    request = mock.create_autospec(fastapi.Request)

    the_installation = mock.create_autospec(installation.Installation)
    the_installation.get_room_configs.return_value = room_configs

    found = await rooms.get_rooms(
        request, the_installation=the_installation,
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


@pytest.mark.anyio
@mock.patch("soliplex.models.Room.from_config")
async def test_get_room(fc, room_configs):
    ROOM_ID = "foo"

    request = mock.create_autospec(fastapi.Request)

    the_installation = mock.create_autospec(installation.Installation)
    the_installation.get_room_configs.return_value = room_configs

    if ROOM_ID not in room_configs:
        with pytest.raises(fastapi.HTTPException) as exc:
            await rooms.get_room(
                request, ROOM_ID, the_installation=the_installation,
            )

        assert exc.value.status_code == 404
        assert exc.value.detail == "No such room: foo"

    else:
        found = await rooms.get_room(
            request, ROOM_ID, the_installation=the_installation,
        )

        assert found is fc.return_value
        fc.assert_called_once_with(room_configs[ROOM_ID])


@pytest.mark.anyio
@pytest.mark.parametrize("w_image", [False, True])
async def test_get_room_bg_image(temp_dir, w_image, room_configs):
    ROOM_ID = "foo"
    IMAGE_FILENAME = "logo.svg"

    image_path = temp_dir / IMAGE_FILENAME

    request = mock.create_autospec(fastapi.Request)

    the_installation = mock.create_autospec(installation.Installation)
    the_installation.get_room_configs.return_value = room_configs

    if ROOM_ID in room_configs:
        if w_image:
            room_configs[ROOM_ID].get_logo_image.return_value = image_path
        else:
            room_configs[ROOM_ID].get_logo_image.return_value = None


    if ROOM_ID not in room_configs:
        with pytest.raises(fastapi.HTTPException) as exc:
            await rooms.get_room_bg_image(
                request,
                room_id=ROOM_ID,
                the_installation=the_installation,
            )

        assert exc.value.status_code == 404
        assert exc.value.detail == "No such room: foo"
    else:
        if w_image:
            found = await rooms.get_room_bg_image(
                request,
                room_id=ROOM_ID,
                the_installation=the_installation,
            )
            # Actual image data is marshalled by fastapi framework
            assert found == str(image_path)
        else:
            with pytest.raises(fastapi.HTTPException) as exc:
                await rooms.get_room_bg_image(
                    request,
                    room_id=ROOM_ID,
                    the_installation=the_installation,
                )

            assert exc.value.status_code == 404
            assert exc.value.detail == "No image for room"
