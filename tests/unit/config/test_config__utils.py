import dataclasses
from unittest import mock

from soliplex.config import _utils as config__utils


def test__dotted_name():
    found = config__utils._dotted_name(config__utils._no_repr)

    assert found == "soliplex.config._utils._no_repr"


@mock.patch("importlib.import_module")
def test__from_dotted_name(im):
    dotted_name = "somemodule.SomeClass"

    faux_module = im.return_value = mock.Mock()

    klass = config__utils._from_dotted_name(dotted_name)

    assert klass is faux_module.SomeClass


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
