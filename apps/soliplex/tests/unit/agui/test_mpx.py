import asyncio
import contextlib

import pytest

from soliplex.agui import mpx


class MPXTestError(ValueError):
    pass


async def _range_ten():
    for i in range(10):
        yield i


async def _range_ten_twenty():
    for i in range(10, 20):
        yield i


async def _range_ten_fifteen_raise():
    for i in range(10, 15):
        yield i
    raise MPXTestError("testing")


async def _raise_immediately():
    raise MPXTestError("testing")
    yield


async def _raise_after_sleep():
    await asyncio.sleep(1)
    raise MPXTestError("testing")
    yield


no_error = contextlib.nullcontext


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "w_streams, expectation",
    [
        ((), no_error([])),
        ((_range_ten,), no_error(list(range(10)))),
        (
            (
                _range_ten,
                _range_ten_twenty,
            ),
            no_error(list(range(20))),
        ),
        (
            (
                _range_ten,
                _range_ten_fifteen_raise,
            ),
            pytest.raises(MPXTestError),
        ),
        (
            (
                _raise_immediately,
                _range_ten,
            ),
            pytest.raises(MPXTestError),
        ),
        (
            (
                _range_ten,
                _raise_after_sleep,
            ),
            pytest.raises(MPXTestError),
        ),
        (
            (
                _raise_immediately,
                _raise_after_sleep,
            ),
            pytest.raises(MPXTestError),
        ),
    ],
)
async def test_multiplex_streams(w_streams, expectation):
    streams = [stream() for stream in w_streams]

    merged = mpx.multiplex_streams(*streams)

    with expectation as expected:
        found = []
        async for event in merged:
            found.append(event)
            await asyncio.sleep(0.1)

    if isinstance(expected, list):
        assert set(found) == set(expected)
