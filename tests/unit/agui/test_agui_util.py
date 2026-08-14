import re
from unittest import mock

import pytest

from soliplex.agui import util as agui_util

HEX_COLOR = re.compile(r"^#[0-9A-F]{6}$")


@mock.patch("uuid.uuid4")
def test__make_uuid_str(u4):
    expected_uuid = u4.return_value = object()

    found = agui_util._make_uuid_str()

    assert found == str(expected_uuid)

    u4.assert_called_once_with()


@mock.patch("datetime.timezone")
@mock.patch("datetime.datetime")
def test__timestamp(dt, tz):
    found = agui_util._timestamp()

    assert found is dt.now.return_value

    dt.now.assert_called_once_with(tz.utc)


@pytest.mark.parametrize("index", [0, 1, 7, 42, 1000])
def test_hue_rotated_hex_renders_a_hex_color(index):
    found = agui_util.hue_rotated_hex(index)

    assert HEX_COLOR.match(found) is not None


def test_hue_rotated_hex_is_deterministic():
    # A label keeps its color across restarts because the color is a
    # function of the label's ID and nothing else.
    assert agui_util.hue_rotated_hex(13) == agui_util.hue_rotated_hex(13)


def test_hue_rotated_hex_separates_consecutive_ids():
    # The point of the golden angle: labels created back to back must
    # not come out as neighbouring shades.
    colors = [agui_util.hue_rotated_hex(index) for index in range(1, 13)]

    assert len(set(colors)) == len(colors)


def test_hue_rotated_hex_is_pinned():
    # Pinned so the palette cannot drift silently: existing labels carry
    # their color in the database, but any label created after a change
    # to the constants would no longer match its neighbours.
    assert agui_util.hue_rotated_hex(1) == "#42D76D"
    assert agui_util.hue_rotated_hex(2) == "#9942D7"
