from __future__ import annotations

from hashlib import sha1
from pathlib import Path
from typing import Any

from diskcache import Cache


class WindCache:
    def __init__(self, path: str | Path = "~/.cache/gpx-player/wind", size_limit: int = 1_000_000_000) -> None:
        self.cache = Cache(Path(path).expanduser(), size_limit=size_limit)

    def _key(self, key: str) -> str:
        return sha1(key.encode()).hexdigest()

    def get(self, key: str) -> Any:
        return self.cache.get(self._key(key))

    def set(self, key: str, value: Any, expire: int | None = None) -> None:
        self.cache.set(self._key(key), value, expire=expire)
