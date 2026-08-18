import re
from unittest import mock

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


def test_default_label_color_is_a_neutral_grey():
    # Pinned because the client offers the same value as a swatch: if
    # the two drift, the picker stops recognising an uncolored label as
    # uncolored and there is no way back to it.
    assert HEX_COLOR.match(agui_util.DEFAULT_LABEL_COLOR) is not None
    assert agui_util.DEFAULT_LABEL_COLOR == "#808080"

    red, green, blue = (
        int(agui_util.DEFAULT_LABEL_COLOR[start:start + 2], 16)
        for start in (1, 3, 5)
    )
    assert red == green == blue
