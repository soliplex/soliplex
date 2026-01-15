"""AGUI Event Emitter for streaming state updates to clients.

This module provides a simple event emitter that can be used to stream
AG-UI events (particularly state updates) alongside the main agent stream.
"""

import asyncio
import typing
import uuid

import pydantic
from ag_ui import core as agui_core

AGUI_State = dict[str, typing.Any]
AGUI_ActivityContent = dict[str, typing.Any]
AGUI_Activities = dict[str, AGUI_ActivityContent]


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

        self._queue: asyncio.Queue[dict | None] = asyncio.Queue()
        self._closed = False
        self._last_state: AGUI_State = {}
        self._last_activities: AGUI_Activities = {}

    def update_state(self, state: pydantic.BaseModel | dict) -> None:
        """Emit a state snapshot / delta event.

        Args:
            state: The new state (Pydantic model or dict)
        """
        if self._closed:
            return

        if isinstance(state, pydantic.BaseModel):
            state_dict = state.model_dump()
        else:
            state_dict = state

        if self.use_deltas:
            self._last_state |= state_dict
            event = {
                "type": agui_core.EventType.STATE_DELTA.value,
                "delta": state_dict,
            }
        else:
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

        if isinstance(content, pydantic.BaseModel):
            content_dict = content.model_dump()
        else:
            content_dict = content

        if activity_id is None:
            activity_id = str(uuid.uuid4())

        prior_content = self._last_activities.get(activity_type, {})

        if self.use_deltas:
            self._last_activities[activity_type] = prior_content | content_dict
            event = {
                "type": agui_core.EventType.ACTIVITY_DELTA.value,
                "message_id": activity_id,
                "activity_type": activity_type,
                "patch": content_dict,
            }

        else:
            self._last_activities[activity_type] = content_dict
            event = {
                "type": agui_core.EventType.ACTIVITY_SNAPSHOT.value,
                "message_id": activity_id,
                "activity_type": activity_type,
                "content": content_dict,
            }

        self._queue.put_nowait(event)

    async def close(self) -> None:
        """Signal that no more events will be emitted."""
        if self._closed:
            return
        self._closed = True
        await self._queue.put(None)

    def __aiter__(self):
        return self._iter_events()

    async def _iter_events(self):
        """Iterate over events from the queue."""
        while True:
            event = await self._queue.get()
            if event is None:
                break
            yield event
