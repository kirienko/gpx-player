import gpxpy
import gpxpy.gpx
from datetime import datetime
from lxml import etree as ET
from pathlib import Path

def cut_gpx_file(file_path, timestamp, cut_type):
    """
    Cuts a GPX file at the point closest to the given timestamp.

    :param file_path: Path to the original GPX file.
    :param timestamp: Timestamp as a datetime instance or string in the format 'YYYY-MM-DDTHH:MM:SS%z'.
    :param cut_type: 'start' to keep everything after the timestamp, 'end' to keep everything before.
    :return: Path to the new GPX file.
    """
    if isinstance(timestamp, str):
        timestamp = datetime.strptime(timestamp, '%Y-%m-%dT%H:%M:%S%z')

    with open(file_path, 'r') as gpx_file:
        gpx = gpxpy.parse(gpx_file)

    new_gpx = gpxpy.gpx.GPX()

    for track in gpx.tracks:
        new_track = gpxpy.gpx.GPXTrack()
        new_gpx.tracks.append(new_track)

        for segment in track.segments:
            new_segment = gpxpy.gpx.GPXTrackSegment()
            new_track.segments.append(new_segment)

            for point in segment.points:
                if (cut_type == 'start' and point.time >= timestamp) or (cut_type == 'end' and point.time <= timestamp):
                    new_segment.points.append(point)

    new_file_path = file_path.replace('.gpx', '_cut.gpx')
    with open(new_file_path, 'w') as f:
        f.write(new_gpx.to_xml())

    return new_file_path


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
