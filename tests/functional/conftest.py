import pytest
from fastapi import testclient

from soliplex import main
from soliplex.config import routing as config_routing


@pytest.fixture(scope="module")
def minimal_app():
    config_routing.register_default_routers()
    app = main.create_app("example/minimal.yaml", no_auth_mode=True)
    config_routing.add_registered_routers(app)

    return app


@pytest.fixture(scope="module")
def no_llm_app():
    config_routing.register_default_routers()
    app = main.create_app("example/functest_no_llm.yaml", no_auth_mode=True)
    config_routing.add_registered_routers(app)

    return app


@pytest.fixture(scope="module")
def client(minimal_app):
    with testclient.TestClient(minimal_app) as client:
        yield client


@pytest.fixture(scope="module")
def client_no_llm(no_llm_app):
    with testclient.TestClient(no_llm_app) as client:
        yield client
