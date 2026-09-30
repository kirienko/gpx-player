import datetime as dt
import re
from typing import Iterable, List, Optional, Union


UTC = dt.timezone.utc
_COMPACT_TZ_RE = re.compile(r"([+-]\d{2})(\d{2})$")
TimestampValue = Union[str, dt.datetime, None]


class GPXTimestampError(ValueError):
    """Raised when a GPX timestamp cannot be used on a UTC timeline."""


class GPXRenderReadinessError(GPXTimestampError):
    """Raised when a valid GPX file is not ready for time-based rendering."""


def normalize_datetime(value: dt.datetime) -> dt.datetime:
    if not isinstance(value, dt.datetime):
        raise GPXTimestampError(
            f"expected a datetime value, got {type(value).__name__}"
        )
    try:
        offset = value.utcoffset()
    except (OverflowError, ValueError) as exc:
        raise GPXTimestampError(f"invalid timezone information: {exc}") from exc
    if value.tzinfo is None or offset is None:
        raise GPXTimestampError("timestamp must be timezone-aware")
    return value.astimezone(UTC)


def parse_iso_datetime(value: str) -> dt.datetime:
    if not isinstance(value, str):
        raise GPXTimestampError(
            f"timestamp must be a string, got {type(value).__name__}"
        )
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    normalized = _COMPACT_TZ_RE.sub(r"\1:\2", normalized)
    try:
        parsed = dt.datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise GPXTimestampError(f"invalid ISO 8601 timestamp {value!r}: {exc}") from exc
    return normalize_datetime(parsed)


def normalize_timestamp_sequence(
    values: Iterable[TimestampValue],
    *,
    context: str,
    require_all: bool,
) -> List[Optional[dt.datetime]]:
    normalized = []
    seen = set()
    previous = None

    for point_index, value in enumerate(values, start=1):
        point_context = f"{context}, point {point_index}"
        if value is None or (isinstance(value, str) and not value.strip()):
            if require_all:
                raise GPXRenderReadinessError(
                    f"{point_context} is missing a timestamp required for time-based processing"
                )
            normalized.append(None)
            continue

        try:
            timestamp = (
                parse_iso_datetime(value)
                if isinstance(value, str)
                else normalize_datetime(value)
            )
        except GPXTimestampError as exc:
            raise GPXTimestampError(
                f"Invalid timestamp at {point_context}: {exc}"
            ) from exc

        if timestamp in seen:
            raise GPXTimestampError(
                f"Duplicate timestamp found at {point_context}: {timestamp.isoformat()}"
            )
        if previous is not None and timestamp < previous:
            raise GPXTimestampError(
                f"Timestamps not strictly increasing: at {point_context}, "
                f"{timestamp.isoformat()} does not come after {previous.isoformat()}"
            )
        normalized.append(timestamp)
        seen.add(timestamp)
        previous = timestamp

    return normalized
