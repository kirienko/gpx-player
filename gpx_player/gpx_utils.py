import copy
from datetime import datetime
from pathlib import Path

import gpxpy
from lxml import etree as ET


def cut_gpx_file(file_path, timestamp, cut_type):
    """
    Cut a GPX file by timestamp and write the result beside the source.

    :param file_path: Path to the original GPX file.
    :param timestamp: Timezone-aware datetime or ISO 8601 string with a timezone.
    :param cut_type: 'start' to keep timestamps at or after the cut, or 'end' to
        keep timestamps at or before it.
    :return: Path to the new GPX file. Existing output paths raise FileExistsError.

    Timestamped points must be timezone-aware. Points without timestamps are
    omitted because they cannot be ordered against the cut. Empty tracks and
    segments, along with their metadata, are preserved.
    """
    if cut_type not in ('start', 'end'):
        raise ValueError("cut_type must be 'start' or 'end'")

    if isinstance(timestamp, str):
        timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
    if not isinstance(timestamp, datetime):
        raise TypeError('timestamp must be a datetime or ISO 8601 string')
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError('timestamp must be timezone-aware')

    source_path = Path(file_path)
    with source_path.open('r', encoding='utf-8') as gpx_file:
        gpx = gpxpy.parse(gpx_file)

    new_gpx = copy.deepcopy(gpx)

    for track in new_gpx.tracks:
        for segment in track.segments:
            retained_points = []
            for point in segment.points:
                if point.time is None:
                    continue
                if point.time.tzinfo is None or point.time.utcoffset() is None:
                    raise ValueError('GPX point timestamps must be timezone-aware')
                if (
                    cut_type == 'start' and point.time >= timestamp
                    or cut_type == 'end' and point.time <= timestamp
                ):
                    retained_points.append(point)
            segment.points = retained_points

    output_suffix = source_path.suffix or '.gpx'
    output_path = source_path.with_name(f'{source_path.stem}_cut{output_suffix}')
    with output_path.open('x', encoding='utf-8') as output_file:
        output_file.write(new_gpx.to_xml())

    return str(output_path)


def _ensure_aware(ts: datetime, name: str) -> None:
    if ts.tzinfo is None:
        raise ValueError(f"trim_track: {name} must be timezone-aware")


def trim_track(track: dict, start_time: datetime, end_time: datetime) -> dict:
    """Return a new track with only points in ``[start_time, end_time]``.

    The input ``track`` is not mutated. All point fields (including any
    extension keys) and track metadata (``name``, ``description``, ...) are
    preserved. A ``ValueError`` is raised if the bounds are naive or if point
    timestamps and bounds disagree on timezone awareness.
    """
    _ensure_aware(start_time, "start_time")
    _ensure_aware(end_time, "end_time")

    filtered = []
    for p in track.get('points', []):
        t = p.get('time')
        if t is None:
            continue
        if (t.tzinfo is None) != (start_time.tzinfo is None):
            raise ValueError(
                "trim_track: point timestamps and start/end_time must both be "
                "timezone-aware or both be naive"
            )
        if start_time <= t <= end_time:
            filtered.append(dict(p))

    new_track = {k: v for k, v in track.items() if k != 'points'}
    new_track['points'] = filtered
    return new_track


def trim_tracks(tracks, start_time: datetime, end_time: datetime):
    """Apply :func:`trim_track` to each track and return a new list."""
    return [trim_track(t, start_time, end_time) for t in tracks]


def remove_extensions_tags(file_path: str, overwrite: bool = False) -> tuple[str, int]:
    """Remove all ``<extensions>...</extensions>`` blocks from a GPX file.

    Parameters
    ----------
    file_path : str
        Path to the input GPX file.

    overwrite : bool, optional
        If ``True``, the original file will be overwritten. Otherwise a new
        file with ``_noext`` appended to the name will be created. Default is
        ``False``.

    Returns
    -------
    tuple[str, int]
        A tuple containing the path to the cleaned GPX file and the number of
        ``<extensions>`` tags removed.
    """

    tree = ET.parse(file_path)
    root = tree.getroot()

    extensions = root.xpath('//*[local-name()="extensions"]')
    removed = len(extensions)
    for node in extensions:
        parent = node.getparent()
        if parent is not None:
            parent.remove(node)

    path = Path(file_path)
    if overwrite:
        new_path = path
    else:
        new_name = path.stem + "_noext.gpx"
        new_path = path.with_name(new_name)

    tree.write(str(new_path), encoding="utf-8", xml_declaration=True)
    return str(new_path), removed
