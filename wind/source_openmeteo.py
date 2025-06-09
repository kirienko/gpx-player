from __future__ import annotations

import datetime as dt
from typing import Any

import httpx

from . import BBox, WindGrid, TiledEndpoint, WindSource


class OpenMeteoSource:
    """Fetch wind data from the Open-Meteo API."""

    FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
    ERA5_URL = "https://api.open-meteo.com/v1/era5"

    def __init__(self, fresh_threshold_h: int = 72) -> None:
        self.fresh_threshold = dt.timedelta(hours=fresh_threshold_h)

    async def grid(self, bbox: BBox, t0: dt.datetime, t1: dt.datetime, level: int = 10) -> WindGrid:
        now = dt.datetime.now(dt.timezone.utc)
        url = self.FORECAST_URL if (now - t1) < self.fresh_threshold else self.ERA5_URL

        params = {
            "latitude_min": bbox.south,
            "latitude_max": bbox.north,
            "longitude_min": bbox.west,
            "longitude_max": bbox.east,
            "hourly": "u10,v10",
            "start_date": t0.strftime("%Y-%m-%d"),
            "end_date": t1.strftime("%Y-%m-%d"),
            "timezone": "UTC",
        }

        async with httpx.AsyncClient() as client:
            resp = await client.get(url, params=params)
            if resp.status_code == 404:
                raise FileNotFoundError("Wind data not available")
            resp.raise_for_status()
            data: Any = resp.json()

        lats = data.get("latitude")
        lons = data.get("longitude")
        times = [dt.datetime.fromisoformat(t) for t in data["hourly"]["time"]]
        u = data["hourly"]["u10"]
        v = data["hourly"]["v10"]

        nx = len(lons)
        ny = len(lats)
        dx = abs(lons[1] - lons[0]) if nx > 1 else 0.0
        dy = abs(lats[1] - lats[0]) if ny > 1 else 0.0

        return WindGrid(u=u, v=v, nx=nx, ny=ny, lo1=lons[0], la1=lats[0], dx=dx, dy=dy, times=times)
