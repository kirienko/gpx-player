import asyncio
import datetime as dt
from wind.source_openmeteo import OpenMeteoSource
from wind import BBox, WindGrid

import pytest
from unittest.mock import patch, AsyncMock


@pytest.mark.asyncio
async def test_openmeteo_grid():
    src = OpenMeteoSource()
    bbox = BBox(west=0, south=0, east=1, north=1)
    t0 = dt.datetime(2024,1,1, tzinfo=dt.timezone.utc)
    t1 = dt.datetime(2024,1,2, tzinfo=dt.timezone.utc)

    fake_json = {
        "latitude": [0, 1],
        "longitude": [0, 1],
        "hourly": {
            "time": ["2024-01-01T00:00:00Z", "2024-01-01T01:00:00Z"],
            "u10": [[0, 0],[0,0]],
            "v10": [[0, 0],[0,0]]
        }
    }

    async def fake_get(url, params=None):
        class Resp:
            status_code = 200
            def raise_for_status(self):
                pass
            def json(self):
                return fake_json
        return Resp()

    with patch('httpx.AsyncClient.get', new=AsyncMock(side_effect=fake_get)):
        grid = await src.grid(bbox, t0, t1)

    assert isinstance(grid, WindGrid)
    assert grid.nx == 2
    assert grid.ny == 2
    assert len(grid.times) == 2

