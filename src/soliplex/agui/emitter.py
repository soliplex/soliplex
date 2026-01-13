"""AGUI Event Emitter for streaming state updates to clients.

This module provides a simple event emitter that can be used to stream
AG-UI events (particularly state updates) alongside the main agent stream.
"""

import asyncio
import uuid

import pydantic
from ag_ui import core as agui_core


class AGUIEmitter:
    """Emit AG-UI events to be multiplexed with the agent stream.

    The emitter is an async iterator that yields event dictionaries.
    Tools can call `update_state()` to emit STATE_SNAPSHOT events.
    """

    def __init__(
        self,
        thread_id: str,
        run_id: str,
        use_deltas: bool = True,
    ):
        self.thread_id = thread_id
        self.run_id = run_id
        self.use_deltas = use_deltas

        self._queue: asyncio.Queue = asyncio.Queue()
        self._closed = False
        self._last_state: dict = {}

    def update_state(self, state: pydantic.BaseModel | dict) -> None:
        """Emit a state snapshot event.

        Args:
            state: The new state (Pydantic model or dict)
        """
        if self._closed:
            return

        if isinstance(state, pydantic.BaseModel):
            state_dict = state.model_dump()
        else:
            state_dict = state

        event = {
            "type": agui_core.EventType.STATE_SNAPSHOT.value,
            "snapshot": state_dict,
        }

        self._last_state = state_dict
        self._queue.put_nowait(event)

    def update_activity(
        self,
        activity_type: str,
        content: dict,
        activity_id: str = None,
    ) -> None:
        """Emit an activity snapshot event.

        Args:
            activity_type: Type of activity (e.g., "thinking", "searching")
            content: Activity content dictionary
            activity_id: Optional activity ID (generated if not provided)
        """
        if self._closed:
            return

        if activity_id is None:
            activity_id = str(uuid.uuid4())

        event = {
            "type": agui_core.EventType.ACTIVITY_SNAPSHOT.value,
            "message_id": activity_id,
            "activity_type": activity_type,
            "content": content,
        }

        self._queue.put_nowait(event)

    async def close(self) -> None:
        """Signal that no more events will be emitted."""
        self._closed = True

    def __aiter__(self):
        return self

    async def __anext__(self):
        while True:
            if self._closed and self._queue.empty():
                raise StopAsyncIteration

            try:
                return await asyncio.wait_for(
                    self._queue.get(),
                    timeout=0.1,
                )
            except TimeoutError:
                if self._closed:
                    raise StopAsyncIteration from None
                continue
