import copy
from unittest import mock

import _test_middleware
import pytest
import yaml

from soliplex.config import middleware as config_middleware

BOGUS_MWCONFIG_YAML = """\
nonesuch: foo
"""

BARE_MIDDLEWARE_NAME = "bare"
BARE_MWCONFIG_KW = {
    "name": BARE_MIDDLEWARE_NAME,
    "app_factory": _test_middleware.null_app_factory,
}
BARE_MWCONFIG_YAML = f"""\
name: "{BARE_MIDDLEWARE_NAME}"
app_factory: "_test_middleware.null_app_factory"
"""

W_NEEDS_ICONFIG_MIDDLEWARE_NAME = "w_needs_iconfig"
W_NEEDS_ICONFIG_MWCONFIG_KW = {
    "name": W_NEEDS_ICONFIG_MIDDLEWARE_NAME,
    "app_factory": _test_middleware.w_iconfig_app_factory,
}
W_NEEDS_ICONFIG_MWCONFIG_YAML = f"""\
name: "{W_NEEDS_ICONFIG_MIDDLEWARE_NAME}"
app_factory: "_test_middleware.w_iconfig_app_factory"
"""

W_EXTRA_PARAMS_MIDDLEWARE_NAME = "w_extra_params"
W_EXTRA_PARAMS_MWCONFIG_KW = {
    "name": W_EXTRA_PARAMS_MIDDLEWARE_NAME,
    "app_factory": _test_middleware.w_extra_params_app_factory,
}
W_EXTRA_PARAMS_MWCONFIG_YAML = f"""\
name: "{W_EXTRA_PARAMS_MIDDLEWARE_NAME}"
app_factory: "_test_middleware.w_extra_params_app_factory"
"""


@pytest.mark.parametrize(
    "config_yaml, expected_kw",
    [
        (BOGUS_MWCONFIG_YAML, None),
        (BARE_MWCONFIG_YAML, BARE_MWCONFIG_KW),
        (W_NEEDS_ICONFIG_MWCONFIG_YAML, W_NEEDS_ICONFIG_MWCONFIG_KW),
        (W_EXTRA_PARAMS_MWCONFIG_YAML, W_EXTRA_PARAMS_MWCONFIG_KW),
    ],
)
def test_middlewareconfig_from_yaml(
    temp_dir,
    config_yaml,
    expected_kw,
):
    expected_kw = copy.deepcopy(expected_kw)

    yaml_file = temp_dir / "config.yaml"
    yaml_file.write_text(config_yaml)

    with yaml_file.open() as fp:
        config_dict = yaml.safe_load(fp)

    config_dict = copy.deepcopy(config_dict)

    if expected_kw is None:
        with pytest.raises(KeyError):
            config_middleware.MiddlewareConfig.from_yaml(config_dict)

    else:
        expected = config_middleware.MiddlewareConfig(**expected_kw)
        found = config_middleware.MiddlewareConfig.from_yaml(
            config_dict.copy(),
        )
        assert found == expected


@pytest.mark.parametrize(
    "config_kw, expected",
    [
        (BARE_MWCONFIG_KW, False),
        (W_NEEDS_ICONFIG_MWCONFIG_KW, True),
        (W_EXTRA_PARAMS_MWCONFIG_KW, False),
    ],
)
def test_middlewareconfig_needs_iconfig(
    config_kw,
    expected,
):
    mw_config = config_middleware.MiddlewareConfig(**config_kw)

    found = mw_config.needs_iconfig

    assert found == expected


APP = mock.Mock(spec_set=())
I_CONFIG = mock.Mock(spec_set=())


@pytest.mark.parametrize(
    "to_compose_kwargs",
    [
        [],
        [
            {
                "name": "null",
                "app_factory": _test_middleware.null_app_factory,
            },
        ],
        [
            {
                "name": "w_iconfg",
                "app_factory": _test_middleware.w_iconfig_app_factory,
            },
        ],
        [
            {
                "name": "w_extra",
                "app_factory": _test_middleware.w_extra_params_app_factory,
                "extra_params": {"foo": "bar"},
            },
        ],
        [
            {
                "name": "null",
                "app_factory": _test_middleware.null_app_factory,
            },
            {
                "name": "w_iconfg",
                "app_factory": _test_middleware.w_iconfig_app_factory,
            },
            {
                "name": "w_extra",
                "app_factory": _test_middleware.w_extra_params_app_factory,
                "extra_params": {"foo": "bar"},
            },
        ],
    ],
)
def test_compose_middlware_stack(to_compose_kwargs):
    to_compose = [
        config_middleware.MiddlewareConfig(**kw) for kw in to_compose_kwargs
    ]

    found = config_middleware.compose_middleware_stack(
        APP,
        I_CONFIG,
        to_compose,
    )

    wrappers = []
    current = found

    while current is not APP:
        wrappers.append(current)
        current = current.app

    assert current is APP

    for composed, wrapper in zip(to_compose, wrappers, strict=True):
        if composed.needs_iconfig:
            assert wrapper.i_config is I_CONFIG
        else:
            assert wrapper.i_config is None

        assert wrapper.kwargs == composed.extra_params
