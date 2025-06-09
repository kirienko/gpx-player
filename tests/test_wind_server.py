import datetime as dt
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from wind.server import app, src, cache
from wind import WindGrid


@pytest.mark.asyncio
async def test_wind_endpoint():
    fake_grid = WindGrid(
        u=[[0.0]],
        v=[[0.0]],
        nx=1,
        ny=1,
        lo1=0.0,
        la1=0.0,
        dx=1.0,
        dy=1.0,
        times=[dt.datetime(2024, 1, 1, tzinfo=dt.timezone.utc)],
    )

    with patch.object(src, "grid", AsyncMock(return_value=fake_grid)):
        with patch.object(cache, "get", return_value=None), patch.object(cache, "set") as set_mock:
            params = {
                "time": "2024-01-01T00:00:00+00:00",
                "west": 0,
                "south": 0,
                "east": 1,
                "north": 1,
            }
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
                resp = await ac.get("/wind", params=params)

            assert resp.status_code == 200
            data = resp.json()
            assert data["nx"] == 1
            assert set_mock.called
