from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, List

@dataclass
class BBox:
    west: float
    south: float
    east: float
    north: float

@dataclass
class WindGrid:
    u: List[List[float]]
    v: List[List[float]]
    nx: int
    ny: int
    lo1: float
    la1: float
    dx: float
    dy: float
    times: List[datetime]

@dataclass
class TiledEndpoint:
    url: str

class WindSource(Protocol):
    async def grid(self, bbox: BBox, t0: datetime, t1: datetime, level: int = 10) -> WindGrid | TiledEndpoint:
        ...
