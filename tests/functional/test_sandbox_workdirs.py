import pathlib
import shutil

import pytest

from soliplex.config import installation as config_installation

ROOM_ID = "chat"

new_thread_request = {"metadata": {"name": "functest"}}


@pytest.fixture(scope="module")
def workdirs_path() -> pathlib.Path:
    ic = config_installation.load_installation(
        pathlib.Path("example/functest_no_llm.yaml")
    )
    result = ic.sandbox_workdirs_path
    result.mkdir(parents=True, exist_ok=True)
    return result


@pytest.fixture
def thread_id(client_no_llm) -> str:
    response = client_no_llm.post(
        f"/api/v1/rooms/{ROOM_ID}/agui",
        json=new_thread_request,
    )
    return response.json()["thread_id"]


@pytest.fixture
def thread_workdir(workdirs_path, thread_id):
    thread_dir = workdirs_path / ROOM_ID / thread_id
    thread_dir.mkdir(parents=True)

    yield ROOM_ID, thread_id, thread_dir

    shutil.rmtree(workdirs_path / ROOM_ID, ignore_errors=True)


def test_get_workdir_file_returns_file_bytes(client_no_llm, thread_workdir):
    room_id, thread_id, thread_dir = thread_workdir
    filename = "result.txt"
    file_bytes = b"hello workdir\n"
    (thread_dir / filename).write_bytes(file_bytes)

    response = client_no_llm.get(
        f"/api/v1/workdirs/{room_id}/thread/{thread_id}/file/{filename}"
    )

    assert response.status_code == 200
    assert response.content == file_bytes
    assert response.headers["content-type"] == "application/octet-stream"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["content-disposition"] == (
        "attachment; filename*=UTF-8''result.txt"
    )


def test_get_workdir_lists_files(client_no_llm, thread_workdir):
    room_id, thread_id, thread_dir = thread_workdir
    (thread_dir / "result.txt").write_bytes(b"hello workdir\n")

    response = client_no_llm.get(
        f"/api/v1/workdirs/{room_id}/thread/{thread_id}"
    )

    assert response.status_code == 200
    listing = response.json()
    assert listing["room_id"] == room_id
    assert listing["thread_id"] == thread_id
    assert "run_id" not in listing
    (entry,) = listing["files"]
    assert entry["filename"] == "result.txt"

    download = client_no_llm.get(entry["url"])
    assert download.status_code == 200
    assert download.content == b"hello workdir\n"


def test_get_workdir_file_404_when_file_missing(client_no_llm, thread_workdir):
    room_id, thread_id, _ = thread_workdir

    response = client_no_llm.get(
        f"/api/v1/workdirs/{room_id}/thread/{thread_id}/file/nope.txt"
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "No workdir file: nope.txt"
