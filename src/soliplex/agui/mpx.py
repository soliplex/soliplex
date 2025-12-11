"""Multiplex a set of AG-UI event streams"""

from __future__ import annotations

import asyncio


def multiplex_streams(*streams):
    queue = asyncio.Queue(1)
    run_count = len(streams)
    cancelling = False

    async def drain(stream):
        nonlocal run_count
        try:
            async for event in stream:
                await queue.put((False, event))
        except Exception as exc:
            if not cancelling:
                await queue.put((True, exc))
            else:  # pragma: NO COVER
                raise
        finally:
            run_count -= 1

    async def merged():
        try:
            while run_count:
                raised, event_or_exc = await queue.get()
                if raised:
                    raise event_or_exc
                yield event_or_exc

            while True:
                try:
                    raised, event_or_exc = queue.get_nowait()
                except asyncio.QueueEmpty:
                    break

                if raised:
                    raise event_or_exc

                yield event_or_exc
        finally:
            cancel_tasks()

    def cancel_tasks():
        nonlocal cancelling
        cancelling = True
        for t in tasks:
            t.cancel()

    tasks = [asyncio.create_task(drain(stream)) for stream in streams]
    return merged()
