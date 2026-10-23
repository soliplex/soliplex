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


def test_thinking_feature_is_registered_and_client_owned():
    """The one feature a client writes rather than reads.

    Every other registration is 'server': the server accumulates the
    state and the client carries it back untouched.  This one travels
    the other way, and 'source' is what says so.
    """
    from soliplex.config import agui as config_agui

    feature = config_agui.AGUI_FEATURES_BY_NAME[
        config_agui.THINKING_FEATURE_NAME
    ]

    assert feature.source is config_agui.AGUI_FeatureSource.CLIENT
    assert feature.model_klass is config_agui.ThinkingState


def test_thinking_feature_publishes_its_levels():
    """A client reads the vocabulary rather than restating it.

    'soliplex-cli agui-feature-schemas' publishes this, so a client
    generates its own type from it instead of hand-copying a list that
    can drift.
    """
    from soliplex.config import agents as config_agents
    from soliplex.config import agui as config_agui

    schema = config_agui.AGUI_FEATURES_BY_NAME[
        config_agui.THINKING_FEATURE_NAME
    ].json_schema

    published = schema["$defs"]["ThinkingLevelName"]["enum"]

    assert tuple(published) == tuple(config_agents.THINKING_LEVELS)


def test_thinking_state_defaults_to_asking_for_nothing():
    """Every registered model class must build with no arguments.

    A new thread's state is synthesized that way, and the value it
    lands on is what a client that never sets a level sends forever.
    """
    from soliplex.config import agui as config_agui

    assert config_agui.ThinkingState().level is None
