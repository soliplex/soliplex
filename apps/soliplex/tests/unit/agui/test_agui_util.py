from unittest import mock

from soliplex.agui import util as agui_util


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
