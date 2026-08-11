import contextlib
import logging
import pathlib
import tempfile
import types
from unittest import mock

import _test_features as agui_features
import pytest

from soliplex import agui
from soliplex import authz
from soliplex import loggers
from soliplex.config import agents as config_agents
from soliplex.config import agui as config_agui
from soliplex.config import authsystem as config_authsystem
from soliplex.config import routing as config_routing
from soliplex.config import secrets as config_secrets
from soliplex.config import skills as config_skills
from soliplex.config import tools as config_tools

AGUI_FEATURE_NAME = "test-agui-feature"


def _auth_systems(n_auth_systems):
    return [
        config_authsystem.OIDCAuthSystemConfig(
            id=f"auth-system-{i_auth_system}",
            title=f"Auth System #{i_auth_system}",
            token_validation_pem=f"PEM {i_auth_system:3d}",
            server_url=f"http://auth{i_auth_system:03}.example.com/",
            client_id=f"AUTH_SYSTEM_{i_auth_system:03}",
        )
        for i_auth_system in range(n_auth_systems)
    ]


@pytest.fixture(scope="module")
def anyio_backend():
    """Run anyio-marked tests on asyncio only (no trio)."""
    return "asyncio"


@pytest.fixture
def unit_of_work(the_async_session):
    """Group storage writes into one committed unit of work.

    The persistence APIs no longer commit -- the session owner does. In
    production that owner is a FastAPI dependency (or the CLI session
    context manager) that commits once per request/invocation. Tests
    mirror that boundary: statements that mutate go inside

        async with unit_of_work():
            await storage.mutate(...)

    which commits on clean exit, and any assertion that observes the
    *persisted* result (a reloaded attribute, a refreshed relationship,
    a datetime round-tripped through the DB) is made afterwards, outside
    the block, where a fresh view is guaranteed. Resolves whichever
    'the_async_session' is in scope for the requesting test.
    """

    @contextlib.asynccontextmanager
    async def _unit_of_work():
        yield the_async_session
        await the_async_session.commit()

    return _unit_of_work


@pytest.fixture
def fake_async_session():
    """Stand-in for ``sqla_asyncio.AsyncSession``.

    Production code opens a fresh per-call session with
    ``async with sqla_asyncio.AsyncSession(bind=...) as session:`` and
    sometimes a nested ``async with session.begin():``. Patch
    ``.cls`` in for ``AsyncSession`` (in whichever module opens the
    session); it records its construction call and yields ``.session``
    as the context value.

    ``session.begin()`` is a non-suppressing async context manager (its
    ``__aexit__`` returns ``False``), so code that wraps a call in a
    transaction still propagates exceptions from the body.
    """
    session = mock.MagicMock()
    session.begin.return_value.__aenter__ = mock.AsyncMock()
    session.begin.return_value.__aexit__ = mock.AsyncMock(return_value=False)

    @contextlib.asynccontextmanager
    async def _open(*_args, **_kwargs):
        yield session

    cls = mock.MagicMock(side_effect=_open)
    return types.SimpleNamespace(cls=cls, session=session)


@pytest.fixture
def mock_thread_storage():
    """Stand-in ``ThreadStorage`` for code that builds one per call.

    Patch ``agui_persistence.ThreadStorage`` (in whichever module builds
    it) with ``return_value=`` this mock, then drive/assert its methods.
    """
    return mock.create_autospec(agui.ThreadStorage)


@pytest.fixture
def temp_dir() -> pathlib.Path:
    with tempfile.TemporaryDirectory() as td:
        yield pathlib.Path(td).resolve()


@pytest.fixture
def audit_records():
    """Capture records emitted to the 'soliplex-audit' logger in a list."""
    records = []
    handler = logging.Handler()
    handler.emit = records.append
    logger = logging.getLogger(loggers.SOLIPLEX_AUDIT_LOGGER_NAME)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    try:
        yield records
    finally:
        logger.removeHandler(handler)


@pytest.fixture(params=[0, 1, 2])
def with_auth_systems(request):
    return _auth_systems(request.param)


@pytest.fixture
def the_agui_feature():
    return config_agui.AGUI_Feature(
        name=AGUI_FEATURE_NAME,
        model_klass=agui_features.EmptyFeatureModel,
        source=config_agui.AGUI_FeatureSource.CLIENT,
    )


@pytest.fixture
def patched_agui_features():
    with mock.patch.dict(config_agui.__dict__) as patched:
        registry = patched["AGUI_FEATURES_BY_NAME"] = {}

        yield registry


@pytest.fixture
def patched_app_routers():
    with mock.patch.dict(config_routing.__dict__) as patched:
        registry = patched["APP_ROUTERS_BY_GROUP_NAME"] = {}

        yield registry


@pytest.fixture
def patched_tool_registries():
    with mock.patch.dict(config_tools.__dict__) as patched:
        patched["TOOL_CONFIG_CLASSES_BY_TOOL_NAME"] = {}
        patched["MCP_TOOLSET_CONFIG_CLASSES_BY_KIND"] = {}
        patched["MCP_TOOL_CONFIG_WRAPPERS_BY_TOOL_NAME"] = {}
        yield patched


@pytest.fixture
def patched_tool_configs(patched_tool_registries):
    return patched_tool_registries["TOOL_CONFIG_CLASSES_BY_TOOL_NAME"]


@pytest.fixture
def patched_mcp_toolset_configs(patched_tool_registries):
    return patched_tool_registries["MCP_TOOLSET_CONFIG_CLASSES_BY_KIND"]


@pytest.fixture
def patched_mcp_tool_wrappers(patched_tool_registries):
    return patched_tool_registries["MCP_TOOL_CONFIG_WRAPPERS_BY_TOOL_NAME"]


@pytest.fixture
def patched_soliplex_config():
    from soliplex import config

    with mock.patch.dict(config.__dict__, patched_for_testing=True) as patched:
        yield patched


@pytest.fixture
def patched_skill_configs():
    with mock.patch.dict(config_skills.__dict__) as patched:
        result = patched["SKILL_CONFIG_CLASSES_BY_KIND"] = {}

        yield result


@pytest.fixture
def patched_agent_capabilities():
    with mock.patch.dict(config_agents.__dict__) as patched:
        registry = patched["AGENT_CAPABILITY_CLASSES_BY_NAME"] = {}

        yield registry


@pytest.fixture
def patched_agent_configs():
    with mock.patch.dict(config_agents.__dict__) as patched:
        result = patched["AGENT_CONFIG_CLASSES_BY_KIND"] = {}

        yield result


@pytest.fixture
def patched_secret_sources():
    with mock.patch.dict(config_secrets.__dict__) as patched:
        result = patched["SourceClassesByKind"] = {}

        yield result


@pytest.fixture
def patched_secret_getters():
    with mock.patch.dict(config_secrets.__dict__) as patched:
        result = patched["SECRET_GETTERS_BY_KIND"] = {}

        yield result


@pytest.fixture
def patched_jsonpath_functions():
    env = authz.the_jsonpath_environment
    with mock.patch.dict(env.function_extensions) as registry:
        yield registry
