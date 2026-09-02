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
def thread_id_run_id(client_no_llm) -> tuple[str, str]:
    response = client_no_llm.post(
        f"/api/v1/rooms/{ROOM_ID}/agui",
        json=new_thread_request,
    )
    new_thread_json = response.json()
    (run_id,) = new_thread_json["runs"]
    return new_thread_json["thread_id"], run_id


@pytest.fixture
def run_workdir(workdirs_path, thread_id_run_id):
    thread_id, run_id = thread_id_run_id
    run_dir = workdirs_path / ROOM_ID / thread_id / run_id
    run_dir.mkdir(parents=True)

    yield ROOM_ID, thread_id, run_id, run_dir

    shutil.rmtree(workdirs_path / ROOM_ID, ignore_errors=True)


def test_get_workdir_file_returns_file_bytes(client_no_llm, run_workdir):
    room_id, thread_id, run_id, run_dir = run_workdir
    filename = "result.txt"
    file_bytes = b"hello workdir\n"
    (run_dir / filename).write_bytes(file_bytes)

    response = client_no_llm.get(
        f"/api/v1/workdirs/{room_id}"
        f"/thread/{thread_id}/run/{run_id}/file/{filename}"
    )

    assert response.status_code == 200
    assert response.content == file_bytes
    assert response.headers["content-type"].startswith("text/plain")


def test_get_workdir_file_404_when_file_missing(client_no_llm, run_workdir):
    room_id, thread_id, run_id, _ = run_workdir

    response = client_no_llm.get(
        f"/api/v1/workdirs/{room_id}"
        f"/thread/{thread_id}/run/{run_id}/file/nope.txt"
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "No workdir file: nope.txt"
