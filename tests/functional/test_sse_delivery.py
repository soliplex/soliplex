import asyncio
import contextlib
import dataclasses
import functools
import json
import pathlib
import re
import uuid

import httpx
import pytest
import sse_delivery_agent
import uvicorn
import yaml

from soliplex import main
from soliplex.config import routing as config_routing
from soliplex.views import streaming as streaming_views

GOLDEN_DIR = pathlib.Path(__file__).parent / "golden"
ROOM_ID = "scripted"
STATE = {"counter": 1}
HANG_GUARD_SECS = 30
CONTENT = "TEXT_MESSAGE_CONTENT"
BOUNDED_BY_COUNT = {
    "strategy": "bounded",
    "max_deltas": 2,
    "max_bytes": 100_000,
    "max_ms": 600_000,
}


def _write_installation(root, *, installation_block=None, room_block=None):
    room_dir = root / "rooms" / ROOM_ID
    room_dir.mkdir(parents=True)

    installation = {
        "id": "sse-delivery-functest",
        "secrets": [
            {
                "secret_name": "URL_SAFE_TOKEN_SECRET",
                "sources": [{"kind": "random_chars"}],
            },
            {
                "secret_name": "SESSION_MIDDLEWARE_TOKEN",
                "sources": [{"kind": "random_chars"}],
            },
        ],
        "environment": [{"name": "INSTALLATION_PATH", "value": "file:."}],
        "agent_configs": [],
        "thread_persistence_db": {
            "sync_dburi": f"sqlite:///{root}/threads.sqlite",
            "async_dburi": f"sqlite+aiosqlite:///{root}/threads.sqlite",
        },
        "authorization_db": {
            "sync_dburi": f"sqlite:///{root}/authz.sqlite",
            "async_dburi": f"sqlite+aiosqlite:///{root}/authz.sqlite",
        },
        "room_paths": [f"./rooms/{ROOM_ID}"],
    }
    if installation_block is not None:
        installation["agui_sse_delivery"] = installation_block

    room = {
        "id": ROOM_ID,
        "name": "Scripted",
        "description": "Scripted agent for SSE delivery tests",
        "agent": {
            "kind": "factory",
            "factory_name": "sse_delivery_agent.agent_factory",
        },
    }
    if room_block is not None:
        room["agui_sse_delivery"] = room_block

    (root / "installation.yaml").write_text(yaml.safe_dump(installation))
    (room_dir / "room_config.yaml").write_text(yaml.safe_dump(room))
    return root / "installation.yaml"


@dataclasses.dataclass
class Server:
    client: httpx.AsyncClient
    app: object

    async def background_done(self):
        tasks = set(self.app.state.agui_background_tasks)
        if tasks:
            async with asyncio.timeout(HANG_GUARD_SECS):
                await asyncio.wait(tasks)


@contextlib.asynccontextmanager
async def _serve(installation_path):
    config_routing.register_default_routers()
    app = main.create_app(installation_path, no_auth_mode=True)
    config_routing.add_registered_routers(app)

    server = uvicorn.Server(
        uvicorn.Config(
            app, host="127.0.0.1", port=0, log_level="warning", ws="none"
        ),
    )
    task = asyncio.create_task(server.serve())
    try:
        async with asyncio.timeout(HANG_GUARD_SECS):
            while not server.started:
                assert not task.done()
                await asyncio.sleep(0.01)

        (sock,) = server.servers[0].sockets
        host, port = sock.getsockname()[:2]
        async with httpx.AsyncClient(
            base_url=f"http://{host}:{port}",
            headers={"Accept-Encoding": "identity"},
            timeout=HANG_GUARD_SECS,
        ) as client:
            the_server = Server(client=client, app=app)
            yield the_server
            await the_server.background_done()
    finally:
        _release_script()
        server.should_exit = True
        done, _ = await asyncio.wait({task}, timeout=HANG_GUARD_SECS)
        if done:
            task.result()
        else:
            task.cancel()
            await asyncio.wait({task}, timeout=HANG_GUARD_SECS)
            if task.done() and not task.cancelled():
                task.exception()
            pytest.fail("uvicorn did not shut down")


def _release_script():
    script = sse_delivery_agent.SCRIPT
    script.gate.set()
    if script.hold is not None:
        script.hold.set()


async def _new_run(client):
    response = await client.post(
        f"/api/v1/rooms/{ROOM_ID}/agui",
        json={"metadata": {"name": "sse-delivery"}},
    )
    response.raise_for_status()
    body = response.json()
    (run_id,) = body["runs"]
    thread_id = body["thread_id"]
    run_input = {
        "thread_id": thread_id,
        "run_id": run_id,
        "state": STATE,
        "messages": [
            {"id": str(uuid.uuid4()), "role": "user", "content": "Hi"},
        ],
        "context": [],
        "tools": [],
        "forwarded_props": None,
    }
    url = f"/api/v1/rooms/{ROOM_ID}/agui/{thread_id}/{run_id}"
    return url, run_input


@dataclasses.dataclass
class Frame:
    id: str | None = None
    data: dict | None = None
    comment: str | None = None

    @property
    def type(self):
        return None if self.data is None else self.data["type"]

    @property
    def index(self):
        return int(self.id.rsplit(":", 1)[1])


async def _frames(response):
    """Yield each SSE frame once its terminating blank line arrives"""
    lines = []
    async for line in response.aiter_lines():
        if line:
            lines.append(line)
            continue

        frame = Frame()
        for field in lines:
            if field.startswith(":"):
                frame.comment = field
            elif field.startswith("id: "):
                frame.id = field.removeprefix("id: ")
            else:
                assert field.startswith("data: "), field
                frame.data = json.loads(field.removeprefix("data: "))
        lines = []
        yield frame

    assert lines == [], f"unterminated SSE frame: {lines}"


def _data(frames):
    return [frame for frame in frames if frame.data is not None]


def _transcript(frames):
    return "".join(f.data["delta"] for f in frames if f.type == CONTENT)


def _snake(key):
    return re.sub(r"(?<!^)(?=[A-Z])", "_", key).lower()


def _envelope(event):
    return {_snake(k): v for k, v in event.items() if v is not None}


async def _stored_events(client, url):
    response = await client.get(url)
    response.raise_for_status()
    return [_envelope(event) for event in response.json()["events"]]


def _set_script(monkeypatch, **kw):
    script = sse_delivery_agent.Script(**kw)
    monkeypatch.setattr(sse_delivery_agent, "SCRIPT", script)
    return script


_UUID = rb"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
_ID_RE = re.compile(
    rb"(?:(?<=^id: )"
    rb'|(?<="threadId":")|(?<="runId":")'
    rb'|(?<="messageId":")|(?<="toolCallId":"))' + _UUID,
    re.MULTILINE,
)
_TS_RE = re.compile(rb'(?<="timestamp":)\d+')


def _normalise(body: bytes) -> bytes:
    ids = {}

    def _sub(match):
        return ids.setdefault(match.group(0), b"<id-%d>" % len(ids))

    return _TS_RE.sub(b"0", _ID_RE.sub(_sub, body))


@pytest.mark.anyio
async def test_default_body_unchanged(tmp_path, monkeypatch):
    _set_script(monkeypatch, deltas=["Hello", ", ", "world", "!"])
    installation_path = _write_installation(tmp_path)

    async with _serve(installation_path) as server:
        url, run_input = await _new_run(server.client)
        response = await server.client.post(url, json=run_input)

    found = _normalise(response.content)
    golden = (GOLDEN_DIR / "default_body.sse").read_bytes()
    assert found == golden


@pytest.mark.anyio
@pytest.mark.parametrize(
    "installation_block, room_block",
    [
        (BOUNDED_BY_COUNT, None),
        (None, BOUNDED_BY_COUNT),
        ({"strategy": "message"}, BOUNDED_BY_COUNT),
    ],
)
async def test_bounded_delivers_while_model_paused(
    tmp_path,
    monkeypatch,
    installation_block,
    room_block,
):
    script = _set_script(
        monkeypatch,
        deltas=["a", "b", "c", "d", "e", "f"],
        gate_before=4,
    )
    installation_path = _write_installation(
        tmp_path,
        installation_block=installation_block,
        room_block=room_block,
    )
    received = []

    async with _serve(installation_path) as server:
        url, run_input = await _new_run(server.client)
        async with server.client.stream("POST", url, json=run_input) as resp:
            frames = _frames(resp)
            async with asyncio.timeout(HANG_GUARD_SECS):
                async for frame in frames:
                    received.append(frame)
                    if _transcript(received) == "abcd":
                        break

            assert not script.gate.is_set()
            assert [
                f.data["delta"] for f in received if f.type == CONTENT
            ] == [
                "ab",
                "cd",
            ]

            script.gate.set()
            received.extend([frame async for frame in frames])

        await server.background_done()
        stored = await _stored_events(server.client, url)

    data = _data(received)
    assert _transcript(data) == script.text
    assert [frame.index for frame in data] == list(range(len(data)))
    assert stored == [_envelope(frame.data) for frame in data]
    assert {"type": "STATE_SNAPSHOT", "snapshot": STATE} in stored


@pytest.mark.anyio
@pytest.mark.parametrize(
    "installation_block, room_block",
    [
        (None, None),
        (BOUNDED_BY_COUNT, {"strategy": "message"}),
    ],
)
async def test_message_holds_text_until_message_end(
    tmp_path,
    monkeypatch,
    installation_block,
    room_block,
):
    script = _set_script(
        monkeypatch,
        deltas=["a", "b", "c", "d", "e", "f"],
        gate_before=4,
    )
    installation_path = _write_installation(
        tmp_path,
        installation_block=installation_block,
        room_block=room_block,
    )
    received = []

    async def read_all(resp):
        async for frame in _frames(resp):
            received.append(frame)

    async with _serve(installation_path) as server:
        url, run_input = await _new_run(server.client)
        async with server.client.stream("POST", url, json=run_input) as resp:
            reader = asyncio.create_task(read_all(resp))
            async with asyncio.timeout(HANG_GUARD_SECS):
                while "TEXT_MESSAGE_START" not in [f.type for f in received]:
                    await asyncio.sleep(0.01)
                while len(script.produced) < 4:
                    await asyncio.sleep(0.01)

            script.gate.set()
            async with asyncio.timeout(HANG_GUARD_SECS):
                await reader

    contents = [f.data["delta"] for f in received if f.type == CONTENT]
    assert contents == ["abcdef"]


@pytest.mark.anyio
@pytest.mark.parametrize(
    "room_block",
    [
        None,
        BOUNDED_BY_COUNT | {"max_deltas": 1},
    ],
    ids=["message", "bounded"],
)
@pytest.mark.parametrize(
    "boundary",
    ["RUN_STARTED", "TEXT_MESSAGE_START", CONTENT, "TEXT_MESSAGE_END"],
)
async def test_reconnect_mid_run(tmp_path, monkeypatch, room_block, boundary):
    script = _set_script(
        monkeypatch,
        deltas=["a", "b", "c", "d"],
        hold=asyncio.Event(),
        final_deltas=["Done"],
    )
    installation_path = _write_installation(tmp_path, room_block=room_block)
    first = []

    async with _serve(installation_path) as server:
        url, run_input = await _new_run(server.client)
        async with server.client.stream("POST", url, json=run_input) as resp:
            async with asyncio.timeout(HANG_GUARD_SECS):
                async for frame in _frames(resp):
                    first.append(frame)
                    if frame.type == boundary:
                        break

        assert not script.hold.is_set()
        last_id = _data(first)[-1].id

        async def resume():
            async with server.client.stream(
                "POST",
                url,
                json=run_input,
                headers={"Last-Event-ID": last_id},
            ) as resp:
                return [frame async for frame in _frames(resp)]

        resumed = asyncio.create_task(resume())
        script.hold.set()
        async with asyncio.timeout(HANG_GUARD_SECS):
            second = await resumed

        await server.background_done()
        stored = await _stored_events(server.client, url)

    data = _data(first) + _data(second)
    assert [frame.index for frame in data] == list(range(len(data)))
    assert _transcript(data) == script.text
    assert stored == [_envelope(frame.data) for frame in data]


@pytest.mark.anyio
async def test_keepalive_while_message_is_held(tmp_path, monkeypatch):
    script = _set_script(monkeypatch, deltas=["a", "b"], gate_before=1)
    monkeypatch.setattr(
        streaming_views,
        "stream_sse_with_keepalive",
        functools.partial(
            streaming_views.stream_sse_with_keepalive,
            poll_interval_secs=0.05,
            keepalive_interval_secs=0.2,
        ),
    )
    installation_path = _write_installation(tmp_path)
    received = []

    async with _serve(installation_path) as server:
        url, run_input = await _new_run(server.client)
        async with server.client.stream("POST", url, json=run_input) as resp:
            frames = _frames(resp)
            async with asyncio.timeout(HANG_GUARD_SECS):
                async for frame in frames:
                    received.append(frame)
                    if frame.comment is not None:
                        break

            assert not script.gate.is_set()
            assert CONTENT not in [frame.type for frame in received]

            script.gate.set()
            received.extend([frame async for frame in frames])

    assert _transcript(received) == "ab"


@pytest.mark.anyio
@pytest.mark.sse_timing
async def test_bounded_loopback_timing(tmp_path, monkeypatch):
    script = _set_script(monkeypatch, deltas=["word "] * 60, interval=0.05)
    installation_path = _write_installation(
        tmp_path,
        room_block={
            "strategy": "bounded",
            "max_deltas": 8,
            "max_bytes": 256,
            "max_ms": 250,
        },
    )
    arrivals = []
    loop = asyncio.get_running_loop()

    async with _serve(installation_path) as server:
        url, run_input = await _new_run(server.client)
        async with server.client.stream("POST", url, json=run_input) as resp:
            async for frame in _frames(resp):
                if frame.type == CONTENT:
                    arrivals.append(loop.time())

    first_produced = script.produced[0][0]
    assert arrivals[0] - first_produced < 0.5
    assert 1 < len(arrivals) < len(script.deltas)
