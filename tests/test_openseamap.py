import tempfile
import datetime as dt

import pytest

import gpxpy.geo

from gpx_player.openseamap import (
    parse_gpx,
    speed_to_color,
    accumulate_distances,
    calculate_average_speeds,
)

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
