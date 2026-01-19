"""SSE and WebSocket streaming endpoints.

This module provides Server-Sent Events (SSE) and WebSocket endpoints
for real-time streaming communication.
"""

import asyncio

import fastapi
from fastapi import WebSocket
from fastapi.responses import StreamingResponse
from starlette.websockets import WebSocketDisconnect

from soliplex import util

router = fastapi.APIRouter()


@util.logfire_span("GET /ssetest")
@router.get("/ssetest", tags=["streaming"])
async def sse_endpoint():  # pragma: no cover
    """Server-Sent Events endpoint for real-time streaming.

    Returns a continuous stream of counter values every second.
    Useful for testing SSE connectivity and for real-time notifications.
    """

    async def event_generator():
        i = 0
        while True:
            await asyncio.sleep(1)
            yield f"data: {i}\n\n"
            i += 1

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.websocket("/wstest")
async def websocket_endpoint(ws: WebSocket):  # pragma: no cover
    """WebSocket endpoint for bidirectional real-time communication.

    Accepts a WebSocket connection and sends counter values every second.
    Useful for testing WebSocket connectivity and for interactive applications.
    """
    await ws.accept()
    i = 0
    try:
        while True:
            await asyncio.sleep(1)
            await ws.send_text(str(i))
            i += 1
    except WebSocketDisconnect:
        pass
