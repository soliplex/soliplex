import contextlib
from unittest import mock

import _test_features as agui_features
import pytest

NoRaise = contextlib.nullcontext()


@pytest.mark.parametrize("wo_schema_desc", [False, True])
def test_aguifeature_description(the_agui_feature, wo_schema_desc):
    if wo_schema_desc:
        model_klass = mock.Mock(
            spec_set=["model_json_schema", "__name__"],
            __name__="NoDescription",
        )
        model_klass.model_json_schema.return_value = {}
        the_agui_feature.model_klass = model_klass

    found = the_agui_feature.description

    if wo_schema_desc:
        assert found == "NoDescription"
    else:
        assert found == agui_features.EmptyFeatureModel.__doc__


def test_aguifeature_as_yaml(the_agui_feature):
    found = the_agui_feature.as_yaml

    assert found == {
        "name": the_agui_feature.name,
        "description": agui_features.EmptyFeatureModel.__doc__,
        "source": "client",
    }


def test_aguifeature_json_schema(the_agui_feature):
    found = the_agui_feature.json_schema

    assert found == agui_features.EmptyFeatureModel.model_json_schema()
