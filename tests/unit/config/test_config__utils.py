import dataclasses
from unittest import mock

import pytest

from soliplex.config import _utils as config__utils
from soliplex.config import exceptions as config_exc


def test__dotted_name():
    found = config__utils._dotted_name(config__utils._no_repr)

    assert found == "soliplex.config._utils._no_repr"


@mock.patch("importlib.import_module")
def test__from_dotted_name(im):
    dotted_name = "somemodule.SomeClass"

    faux_module = im.return_value = mock.Mock()

    klass = config__utils._from_dotted_name(dotted_name)

    assert klass is faux_module.SomeClass


@pytest.mark.parametrize(
    "path",
    ["logo.png", "./logo.png", "./sub/../logo.png"],
)
def test__local_path_w_local(temp_dir, path):
    room_dir = temp_dir / "room"
    room_dir.mkdir()

    found = config__utils._local_path(room_dir, path)

    assert found == room_dir / "logo.png"


@pytest.mark.parametrize(
    "path",
    ["../outside.png", "./../outside.png", "./sub/../../outside.png"],
)
def test__local_path_w_parent_escape(temp_dir, path):
    room_dir = temp_dir / "room"
    room_dir.mkdir()

    with pytest.raises(config_exc.PathNotLocal) as exc_info:
        config__utils._local_path(room_dir, path)

    assert exc_info.value.config_dir == room_dir
    assert exc_info.value.path == path


def test__local_path_w_absolute_outside(temp_dir):
    room_dir = temp_dir / "room"
    room_dir.mkdir()
    path = str(temp_dir / "outside.png")

    with pytest.raises(config_exc.PathNotLocal) as exc_info:
        config__utils._local_path(room_dir, path)

    assert exc_info.value.config_dir == room_dir
    assert exc_info.value.path == path


def test__local_path_w_absolute_inside(temp_dir):
    room_dir = temp_dir / "room"
    room_dir.mkdir()
    path = str(room_dir / "logo.png")

    found = config__utils._local_path(room_dir, path)

    assert found == room_dir / "logo.png"


def test__no_repr():
    found = config__utils._no_repr()

    assert found.repr is False
    assert found.compare is True
    assert found.default is dataclasses.MISSING
    assert found.default_factory is dataclasses.MISSING


def test__no_repr_w_kw():
    found = config__utils._no_repr(init=False)

    assert found.repr is False
    assert found.init is False


def test__no_repr_no_compare():
    found = config__utils._no_repr_no_compare()

    assert found.repr is False
    assert found.compare is False
    assert found.default is dataclasses.MISSING
    assert found.default_factory is dataclasses.MISSING


def test__no_repr_no_compare_none():
    found = config__utils._no_repr_no_compare_none()

    assert found.repr is False
    assert found.compare is False
    assert found.default is None


def test__no_repr_no_compare_dict():
    found = config__utils._no_repr_no_compare_dict()

    assert found.repr is False
    assert found.compare is False
    assert found.default_factory is dict


def test__default_list_field():
    found = config__utils._default_list_field()

    assert found.repr is True
    assert found.compare is True
    assert found.default_factory is list


def test__default_dict_field():
    found = config__utils._default_dict_field()

    assert found.repr is True
    assert found.compare is True
    assert found.default_factory is dict
