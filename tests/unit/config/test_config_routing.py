import contextlib
from unittest import mock

import fastapi
import pytest

from soliplex.config import exceptions as config_exc
from soliplex.config import routing as config_routing

PREFIX = "/prefix"
TAG_ONE = "tag-one"
TAG_TWO = "tag-tow"
TAGS = [TAG_ONE, TAG_TWO]
DEP_ONE = "my.package.dependency_one"
DEP_TWO = "my.package.dependency_two"
DEPENDENCIES = [DEP_ONE, DEP_TWO]
DEFAULT_RESPONSE_CLASS = "my.package.default_response_class"
DEPRECATED = True
DEFAULT_KW = {"prefix": "/api"}
GROUP_NAME = "test-group"
ROUTER_NAME = "soliplex.test_router"

ALREADY_GROUP = pytest.raises(config_routing.AppRoutingGroupAlreadyExists)
UNKNOWN_GROUP = pytest.raises(config_routing.UnknownAppRoutingGroup)


@pytest.mark.parametrize(
    "ctor_kw, expected",
    [
        ({}, DEFAULT_KW),
        ({"prefix": None}, {}),
        ({"prefix": PREFIX}, {"prefix": PREFIX}),
        ({"tags": TAGS}, {"tags": TAGS} | DEFAULT_KW),
        (
            {"dependencies": DEPENDENCIES},
            {"dependencies": DEPENDENCIES} | DEFAULT_KW,
        ),
        (
            {"default_response_class": DEFAULT_RESPONSE_CLASS},
            {"default_response_class": DEFAULT_RESPONSE_CLASS} | DEFAULT_KW,
        ),
        ({"deprecated": DEPRECATED}, {"deprecated": DEPRECATED} | DEFAULT_KW),
    ],
)
def test_apirouterkwargs_router_kwargs(ctor_kw, expected):
    arkw = config_routing.APIRouterKwargs(**ctor_kw)

    found = arkw.router_kwargs

    assert found == expected


@pytest.fixture
def soliplex_test_router():
    the_test_router = mock.Mock(spec_set=())
    with mock.patch.dict("soliplex.__dict__", test_router=the_test_router):
        yield the_test_router


@pytest.mark.parametrize(
    "router_kw, exp_router_kw",
    [
        ({}, DEFAULT_KW),
        ({"prefix": None}, {}),
        ({"prefix": PREFIX}, {"prefix": PREFIX}),
        ({"tags": TAGS}, {"tags": TAGS} | DEFAULT_KW),
        (
            {"dependencies": DEPENDENCIES},
            {"dependencies": DEPENDENCIES} | DEFAULT_KW,
        ),
        (
            {"default_response_class": DEFAULT_RESPONSE_CLASS},
            {"default_response_class": DEFAULT_RESPONSE_CLASS} | DEFAULT_KW,
        ),
        ({"deprecated": DEPRECATED}, {"deprecated": DEPRECATED} | DEFAULT_KW),
    ],
)
@pytest.mark.parametrize(
    "replace_kw, exp_replace",
    [
        ({}, {"replace_existing": False}),
        ({"replace_existing": False}, {"replace_existing": False}),
        ({"replace_existing": True}, {"replace_existing": True}),
    ],
)
def test_addapprouter_as_yaml(
    replace_kw,
    exp_replace,
    router_kw,
    exp_router_kw,
):
    add_op = config_routing.AddAppRouter(
        group_name=GROUP_NAME,
        router_name=ROUTER_NAME,
        **replace_kw,
        **router_kw,
    )

    expected = (
        {
            "kind": "add",
            "group_name": GROUP_NAME,
            "router_name": ROUTER_NAME,
        }
        | exp_replace
        | exp_router_kw
    )

    found = add_op.as_yaml

    assert found == expected


@pytest.mark.parametrize(
    "w_existing, w_replace, expectation",
    [
        (False, None, contextlib.nullcontext()),
        (True, None, ALREADY_GROUP),
        (True, False, ALREADY_GROUP),
        (True, True, contextlib.nullcontext()),
    ],
)
def test_addapprouter_apply(
    patched_app_routers,
    soliplex_test_router,
    w_existing,
    w_replace,
    expectation,
):
    if w_existing:
        already = patched_app_routers[GROUP_NAME] = object()

    ctor_kwargs = {}

    if w_replace is not None:
        ctor_kwargs["replace_existing"] = w_replace

    operation = config_routing.AddAppRouter(
        group_name=GROUP_NAME,
        router_name=ROUTER_NAME,
        **ctor_kwargs,
    )

    with expectation as expected:
        operation.apply()

    def assert_applied():
        (router, router_name, router_kw) = patched_app_routers[GROUP_NAME]
        assert router is soliplex_test_router
        assert router_name == ROUTER_NAME
        assert router_kw == DEFAULT_KW

    if expected is not None:
        assert patched_app_routers[GROUP_NAME] is already
    else:
        assert_applied()


@pytest.mark.parametrize(
    "require_kw, exp_require",
    [
        ({}, {"require_existing": True}),
        ({"require_existing": False}, {"require_existing": False}),
        ({"require_existing": True}, {"require_existing": True}),
    ],
)
def test_deleteapprouter_as_yaml(
    require_kw,
    exp_require,
):
    delete_op = config_routing.DeleteAppRouter(
        group_name=GROUP_NAME,
        **require_kw,
    )

    expected = {
        "kind": "delete",
        "group_name": GROUP_NAME,
    } | exp_require

    found = delete_op.as_yaml

    assert found == expected


@pytest.mark.parametrize(
    "w_existing, w_require, expectation",
    [
        (True, None, contextlib.nullcontext()),
        (False, None, UNKNOWN_GROUP),
        (False, True, UNKNOWN_GROUP),
        (False, False, contextlib.nullcontext()),
    ],
)
def test_deleteapprouter_apply(
    patched_app_routers,
    w_existing,
    w_require,
    expectation,
):
    if w_existing:
        patched_app_routers[GROUP_NAME] = object()

    ctor_kwargs = {}

    if w_require is not None:
        ctor_kwargs["require_existing"] = w_require

    operation = config_routing.DeleteAppRouter(
        group_name=GROUP_NAME,
        **ctor_kwargs,
    )

    with expectation as expected:
        operation.apply()

    if expected is not None:
        assert GROUP_NAME not in patched_app_routers


def test_clearapprouteras_yaml():
    clear_op = config_routing.ClearAppRouters()

    found = clear_op.as_yaml

    assert found == {"kind": "clear"}


@pytest.mark.parametrize("w_existing", [False, True])
def test_clearapprouters_apply(patched_app_routers, w_existing):
    if w_existing:
        patched_app_routers[GROUP_NAME] = object()

    operation = config_routing.ClearAppRouters()

    operation.apply()

    assert len(patched_app_routers) == 0


@pytest.mark.parametrize(
    "w_kind, expectation",
    [
        ("add", contextlib.nullcontext()),
        ("delete", contextlib.nullcontext()),
        ("clear", contextlib.nullcontext()),
        ("bogus", pytest.raises(config_exc.FromYamlException)),
    ],
)
def test__validate_app_router_operation_kind(temp_dir, w_kind, expectation):
    config_dict = {"kind": w_kind}
    with expectation as expected:
        found = config_routing._validate_app_router_operation_kind(
            config_path=temp_dir,
            config_dict=config_dict,
        )

    if expected is None:
        assert found == w_kind


@pytest.mark.parametrize(
    "config_dict, expectation",
    [
        (
            {
                "kind": "add",
                "group_name": GROUP_NAME,
                "router_name": ROUTER_NAME,
            },
            contextlib.nullcontext(config_routing.AddAppRouter),
        ),
        (
            {"kind": "delete", "group_name": GROUP_NAME},
            contextlib.nullcontext(config_routing.DeleteAppRouter),
        ),
        (
            {"kind": "clear"},
            contextlib.nullcontext(config_routing.ClearAppRouters),
        ),
        ({}, pytest.raises(config_exc.FromYamlException)),
        ({"kind": "bogus"}, pytest.raises(config_exc.FromYamlException)),
        ({"kind": "add"}, pytest.raises(config_exc.FromYamlException)),
        ({"kind": "delete"}, pytest.raises(config_exc.FromYamlException)),
    ],
)
def test_app_router_operation_from_yaml(temp_dir, config_dict, expectation):
    with expectation as expected:
        found = config_routing.app_router_operation_from_yaml(
            config_path=temp_dir,
            config_dict=config_dict,
        )

    if isinstance(expected, type):
        assert isinstance(found, expected)


@mock.patch("soliplex.config._utils._from_dotted_name")
def test_register_default_routers(fdn, patched_app_routers):
    config_routing.register_default_routers()

    assert len(patched_app_routers) == len(
        config_routing._DEFAULT_ROUTER_NAMES
    )

    for (g_name, r_name), fdn_call in zip(
        config_routing._DEFAULT_ROUTER_NAMES.items(),
        fdn.call_args_list,
        strict=True,
    ):
        assert fdn_call == mock.call(r_name)
        router, name, kwargs = patched_app_routers[g_name]
        assert router is fdn.return_value
        assert name == r_name
        assert kwargs is config_routing._DEFAULT_KWARGS


@pytest.mark.parametrize("w_aro", [False, True])
def test_add_registered_routers(patched_app_routers, w_aro):
    app = mock.create_autospec(fastapi.FastAPI)

    if w_aro:
        router = mock.Mock(spec_set=())
        patched_app_routers[GROUP_NAME] = (
            router,
            ROUTER_NAME,
            {"prefix": PREFIX},
        )

    config_routing.add_registered_routers(app)

    if w_aro:
        app.include_router.assert_called_once_with(router, prefix=PREFIX)
    else:
        app.include_router.assert_not_called()
