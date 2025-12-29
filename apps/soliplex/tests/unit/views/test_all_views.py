import pytest

from soliplex import views


@pytest.mark.anyio
async def test_health_check():
    response = await views.health_check()

    assert response == "OK"
