import pytest
import tempfile
from openseamap import parse_gpx

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

    points = parse_gpx(temp_gpx_path)
    assert len(points) == 2
    assert points[0]['lat'] == 42.0
    assert points[0]['lon'] == -71.0
    assert points[0]['time'].isoformat() == '2021-01-01T12:00:00+00:00'
    assert points[1]['lat'] == 42.1
    assert points[1]['lon'] == -71.1
    assert points[1]['time'].isoformat() == '2021-01-01T12:10:00+00:00'
