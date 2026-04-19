import tempfile
import datetime as dt

import pytest

import gpxpy.geo

from gpx_player.openseamap import (
    parse_gpx,
    speed_to_color,
    accumulate_distances,
    calculate_average_speeds,
    create_map,
)


def _write_sample_gpx(n_points=6, step_seconds=60, start="2024-06-15T12:00:00Z"):
    """Write a GPX file with ``n_points`` evenly spaced points; return its path."""
    t0 = dt.datetime.strptime(start, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
    pts_xml = []
    for i in range(n_points):
        t = (t0 + dt.timedelta(seconds=i * step_seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")
        pts_xml.append(
            f'            <trkpt lat="{42.0 + i * 0.001}" lon="{-71.0 - i * 0.001}">\n'
            f'                <time>{t}</time>\n'
            f'            </trkpt>'
        )
    gpx = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<gpx version="1.1" creator="pytest">\n'
        '    <trk>\n'
        '        <name>Test Track</name>\n'
        '        <trkseg>\n'
        + "\n".join(pts_xml) + "\n"
        '        </trkseg>\n'
        '    </trk>\n'
        '</gpx>'
    )
    tmp = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".gpx")
    tmp.write(gpx)
    tmp.close()
    return tmp.name, t0

def test_parse_gpx():
    sample_gpx = '''<?xml version="1.0" encoding="UTF-8"?>
    <gpx version="1.1" creator="pytest">
        <trk>
            <name>Test Track</name>
            <trkseg>
                <trkpt lat="42.0" lon="-71.0">
                    <time>2021-01-01T12:00:00Z</time>
                </trkpt>
                <trkpt lat="42.1" lon="-71.1">
                    <time>2021-01-01T12:10:00Z</time>
                </trkpt>
            </trkseg>
        </trk>
    </gpx>'''

    with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_gpx:
        temp_gpx.write(sample_gpx)
        temp_gpx_path = temp_gpx.name

    tracks = parse_gpx(temp_gpx_path)
    points = tracks[0]['points']
    name = tracks[0]['name']

    assert len(points) == 2
    assert points[0]['lat'] == 42.0
    assert points[0]['lon'] == -71.0
    assert points[0]['time'].isoformat() == '2021-01-01T12:00:00+00:00'
    assert points[1]['lat'] == 42.1
    assert points[1]['lon'] == -71.1
    assert points[1]['time'].isoformat() == '2021-01-01T12:10:00+00:00'
    assert name == 'Test Track'

def test_speed_to_color():
    # Test cases for speed_to_color function
    max_speed = 12.0
    speeds = [0, 3, 6, 9, 12]  # Speeds within max_speed

    for speed in speeds:
        color = speed_to_color(speed, max_speed)
        assert isinstance(color, str)
        assert color.startswith("#")
        assert len(color) == 7

    # Test speed exceeding max_speed
    color = speed_to_color(15, max_speed)
    assert isinstance(color, str)
    assert color.startswith("#")
    assert len(color) == 7


def test_accumulate_distances_and_avg_speed():
    points = [
        {
            'lat': 0.0,
            'lon': 0.0,
            'time': dt.datetime(2020, 1, 1, 0, 0, 0, tzinfo=dt.timezone.utc),
        },
        {
            'lat': 0.0,
            'lon': 1.0,
            'time': dt.datetime(2020, 1, 1, 1, 0, 0, tzinfo=dt.timezone.utc),
        },
        {
            'lat': 0.0,
            'lon': 2.0,
            'time': dt.datetime(2020, 1, 1, 2, 0, 0, tzinfo=dt.timezone.utc),
        },
    ]

    dists = accumulate_distances(points)

    expected_first = 0.0
    one_deg_nm = gpxpy.geo.haversine_distance(0, 0, 0, 1) / 1852.0
    expected_second = one_deg_nm
    expected_third = 2 * one_deg_nm

    assert len(dists) == 3
    assert dists[0] == pytest.approx(expected_first)
    assert dists[1] == pytest.approx(expected_second)
    assert dists[2] == pytest.approx(expected_third)

    avgs = calculate_average_speeds(points, dists)

    assert len(avgs) == 3
    assert avgs[0] == 0.0
    assert avgs[1] == pytest.approx(expected_second / 1.0)
    assert avgs[2] == pytest.approx(expected_third / 2.0)


def test_create_map_default_unchanged():
    path, _t0 = _write_sample_gpx(n_points=6)
    _map, all_tracks, _max_speed, _map_id = create_map([path], names=None, max_speed=12.0)

    assert len(all_tracks) == 1
    assert len(all_tracks[0]['points']) == 6


def test_create_map_with_time_window():
    path, t0 = _write_sample_gpx(n_points=6, step_seconds=60)
    # Window is [t0+60s, t0+240s] → keeps points at 60s, 120s, 180s, 240s (4 points)
    start = t0 + dt.timedelta(seconds=60)
    end = t0 + dt.timedelta(seconds=240)

    _map, all_tracks, _max_speed, _map_id = create_map(
        [path], names=None, max_speed=12.0, start_time=start, end_time=end,
    )

    assert len(all_tracks) == 1
    points = all_tracks[0]['points']
    assert len(points) == 4
    assert points[0]['time'] == start
    assert points[-1]['time'] == end
    # Parallel arrays must line up with the filtered points.
    assert len(all_tracks[0]['seg_speeds']) == 3
    assert len(all_tracks[0]['distances']) == 4
    assert len(all_tracks[0]['avg_speeds']) == 4
    assert len(all_tracks[0]['point_speeds']) == 4


def test_create_map_skips_empty_track(capsys):
    path, t0 = _write_sample_gpx(n_points=4)
    # Window entirely before the track's time range.
    start = t0 - dt.timedelta(hours=2)
    end = t0 - dt.timedelta(hours=1)

    _map, all_tracks, _max_speed, _map_id = create_map(
        [path], names=None, max_speed=12.0, start_time=start, end_time=end,
    )

    assert all_tracks == []
    captured = capsys.readouterr()
    assert "no points" in captured.out
    assert "skipping" in captured.out
