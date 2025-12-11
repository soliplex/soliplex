import pytest
from fastapi import testclient

from soliplex import main


@pytest.fixture(scope="module")
def client():
    with testclient.TestClient(
        main.create_app("example/minimal.yaml")
    ) as client:
        yield client


@pytest.fixture(scope="module")
def client_no_llm():
    with testclient.TestClient(
        main.create_app("example/functest_no_llm.yaml")
    ) as client:
        yield client
