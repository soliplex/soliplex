import uuid
from unittest import mock

import fastapi
import pytest
from fastapi import testclient

from soliplex import authz as authz_package
from soliplex import installation
from soliplex import loggers
from soliplex import views as views_package
from soliplex.config import rooms as config_rooms
from soliplex.views import file_uploads as file_uploads_views

ROOM_ID = "test-room"
THREAD_ID = uuid.uuid4()
RUN_ID = uuid.uuid4()
FILENAME = "result.txt"
FILE_BYTES = b"hello workdir\n"


@pytest.fixture
def workdirs_path(tmp_path):
    result = tmp_path / "workdirs"
    result.mkdir()
    return result


@pytest.fixture
def the_installation(workdirs_path):
    inst = mock.create_autospec(installation.Installation)
    inst.sandbox_workdirs_path = str(workdirs_path)
    return inst


@pytest.fixture
def app(the_installation):
    app = fastapi.FastAPI()
    app.include_router(file_uploads_views.router, prefix="/api")

    async def _user_claims():
        return {
            "preferred_username": "phreddy",
            "email": "phreddy@example.com",
        }

    async def _authz():
        return mock.create_autospec(authz_package.AuthorizationPolicy)

    async def _logger():
        return mock.create_autospec(loggers.LogWrapper)

    async def _inst():
        return the_installation

    app.dependency_overrides[installation.get_the_installation] = _inst
    app.dependency_overrides[views_package.get_the_user_claims] = _user_claims
    app.dependency_overrides[authz_package.get_the_authz_policy] = _authz
    app.dependency_overrides[views_package.get_the_logger] = _logger
    return app


@pytest.fixture
def client(app):
    with testclient.TestClient(
        app, raise_server_exceptions=False
    ) as the_client:
        yield the_client


def _route_url(
    *,
    room_id=ROOM_ID,
    thread_id=THREAD_ID,
    run_id=RUN_ID,
    filename=FILENAME,
):
    return (
        f"/api/v1/workdirs/{room_id}"
        f"/thread/{thread_id}/run/{run_id}/file/{filename}"
    )


@mock.patch(
    "soliplex.views.file_uploads.soliplex_views_agui._check_user_in_room"
)
def test_get_workdir_file_returns_file_bytes(cuir, client, workdirs_path):
    cuir.return_value = mock.create_autospec(config_rooms.RoomConfig)

    target_dir = workdirs_path / ROOM_ID / str(THREAD_ID) / str(RUN_ID)
    target_dir.mkdir(parents=True)
    target_path = target_dir / FILENAME
    target_path.write_bytes(FILE_BYTES)

    response = client.get(_route_url())

    assert response.status_code == 200
    assert response.content == FILE_BYTES
    assert response.headers["content-type"].startswith("text/plain")


@mock.patch(
    "soliplex.views.file_uploads.soliplex_views_agui._check_user_in_room"
)
def test_get_workdir_file_404_when_sandbox_not_configured(
    cuir,
    client,
    the_installation,
):
    cuir.return_value = mock.create_autospec(config_rooms.RoomConfig)
    the_installation.sandbox_workdirs_path = None

    response = client.get(_route_url())

    assert response.status_code == 404
    assert response.json()["detail"] == "Sandbox workdirs not configured"


@mock.patch(
    "soliplex.views.file_uploads.soliplex_views_agui._check_user_in_room"
)
def test_get_workdir_file_404_when_file_missing(cuir, client, workdirs_path):
    cuir.return_value = mock.create_autospec(config_rooms.RoomConfig)

    response = client.get(_route_url(filename="nope.txt"))

    assert response.status_code == 404
    assert response.json()["detail"] == "No workdir file: nope.txt"
