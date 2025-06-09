from __future__ import annotations

import datetime as dt
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from . import BBox
from .source_openmeteo import OpenMeteoSource
from .cache import WindCache

app = FastAPI()

src = OpenMeteoSource()
cache = WindCache()

@app.get("/wind")
async def wind(
    time: str,
    west: float,
    south: float,
    east: float,
    north: float,
):
    """Return Leaflet-Velocity compatible wind JSON."""
    try:
        t = dt.datetime.fromisoformat(time)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid time") from exc

    bbox = BBox(west=west, south=south, east=east, north=north)
    key = f"{time}_{west}_{south}_{east}_{north}"
    cached = cache.get(key)
    if cached is not None:
        return JSONResponse(cached)

    try:
        grid = await src.grid(bbox, t, t)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Wind data not available") from exc

    result = {
        "u": grid.u,
        "v": grid.v,
        "nx": grid.nx,
        "ny": grid.ny,
        "lo1": grid.lo1,
        "la1": grid.la1,
        "dx": grid.dx,
        "dy": grid.dy,
        "times": [tm.isoformat() for tm in grid.times],
    }
    cache.set(key, result, expire=3600)
    return JSONResponse(result)


def main() -> None:
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
