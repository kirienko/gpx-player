import datetime as dt
import shutil
from pathlib import Path

import pytest

from gpx_player.utils import slug, timedelta_to_hms
import gpxpy

from gpx_player.gpx_utils import (
    cut_gpx_file,
    remove_extensions_tags,
    trim_track,
    trim_tracks,
)


def _make_track(n, start, step=dt.timedelta(minutes=1), extras=None):
    points = []
    for i in range(n):
        p = {'lat': float(i), 'lon': -float(i), 'time': start + i * step}
        if extras:
            p.update(extras)
        points.append(p)
    return {'name': 'T', 'description': 'd', 'points': points}


def _write_cut_gpx(path, times=(
    '2024-06-15T14:00:00Z',
    '2024-06-15T15:00:00Z',
    '2024-06-15T16:00:00Z',
)):
    points = []
    for index, timestamp in enumerate(times):
        time_xml = f'<time>{timestamp}</time>' if timestamp else ''
        points.append(
            f'<trkpt lat="{index}" lon="-{index}"><ele>{index + 10}</ele>'
            f'{time_xml}<extensions><v:point>{index}</v:point></extensions></trkpt>'
        )
    path.write_text(
        '<?xml version="1.0"?><gpx version="1.1" creator="cut-test" '
        'xmlns="http://www.topografix.com/GPX/1/1" xmlns:v="urn:test">'
        '<metadata><name>Document name</name><desc>Document description</desc>'
        '<extensions><v:document>preserve</v:document></extensions></metadata>'
        '<trk><name>Track name</name><desc>Track description</desc><type>other</type>'
        '<extensions><v:track>preserve</v:track></extensions><trkseg>'
        '<extensions><v:segment>preserve</v:segment></extensions>'
        + ''.join(points)
        + '</trkseg></trk></gpx>',
        encoding='utf-8',
    )


def _parse_cut_gpx(path):
    with path.open(encoding='utf-8') as gpx_file:
        return gpxpy.parse(gpx_file)

def test_slug():
    # Test cases for the slug function
    test_cases = [
        ("Hello World!", "hello-world"),
        ("Python_3.9", "python_39"),
        ("   Leading and trailing spaces   ", "leading-and-trailing-spaces"),
        ("Special #$%&* characters!", "special-characters"),
        ("Multiple   Spaces", "multiple-spaces"),
        ("", ""),
    ]
    for input_str, expected_output in test_cases:
        assert slug(input_str) == expected_output

def test_timedelta_to_hms():
    # Test cases for the timedelta_to_hms function
    test_cases = [
        (dt.timedelta(hours=1, minutes=30, seconds=15), "1:30:15"),
        (dt.timedelta(minutes=45, seconds=5), "45:05"),
        (dt.timedelta(seconds=59), "00:59"),
        (dt.timedelta(hours=2), "2:00:00"),
        (dt.timedelta(hours=0, minutes=0, seconds=0), "00:00"),
        (dt.timedelta(hours=30, minutes=0, seconds=0), "30:00:00"),
        (dt.timedelta(hours=23, minutes=59, seconds=59), "23:59:59"),
    ]
    for td, expected_output in test_cases:
        assert timedelta_to_hms(td) == expected_output


def test_remove_extensions_tags(tmp_path):
    src = Path("example-data/track1.gpx")
    tmp_file = tmp_path / src.name
    shutil.copy(src, tmp_file)

    cleaned, count = remove_extensions_tags(str(tmp_file))

    assert count == 511
    with open(cleaned, "r") as f:
        content = f.read()
        assert "<extensions>" not in content


def test_remove_extensions_tags_noop(tmp_path):
    data = """<?xml version='1.1'?>\n<gpx version='1.1'><trk></trk></gpx>"""
    gpx_file = tmp_path / "sample.gpx"
    gpx_file.write_text(data)

    cleaned, count = remove_extensions_tags(str(gpx_file))

    assert count == 0
    with open(cleaned) as f:
        assert "<extensions>" not in f.read()


def test_remove_extensions_tags_preserve_namespace(tmp_path):
    src = Path("example-data/track1.gpx")
    dst = tmp_path / src.name
    shutil.copy(src, dst)

    cleaned, _ = remove_extensions_tags(str(dst))

    with open(cleaned) as f:
        f.readline()  # XML declaration
        second = f.readline()

    assert "<ns0:gpx" not in second


def test_remove_extensions_tags_overwrite(tmp_path):
    src = Path("example-data/track1.gpx")
    dst = tmp_path / src.name
    shutil.copy(src, dst)

    cleaned, removed = remove_extensions_tags(str(dst), overwrite=True)

    assert removed == 511
    assert cleaned == str(dst)
    with open(dst) as f:
        assert "<extensions>" not in f.read()


def test_trim_track_basic_window():
    t0 = dt.datetime(2024, 6, 15, 12, 0, tzinfo=dt.timezone.utc)
    track = _make_track(5, t0)
    trimmed = trim_track(track, t0 + dt.timedelta(minutes=1), t0 + dt.timedelta(minutes=3))
    assert len(trimmed['points']) == 3
    assert trimmed['points'][0]['time'] == t0 + dt.timedelta(minutes=1)
    assert trimmed['points'][-1]['time'] == t0 + dt.timedelta(minutes=3)
    assert trimmed['name'] == 'T'
    assert trimmed['description'] == 'd'


def test_trim_track_does_not_mutate_input():
    t0 = dt.datetime(2024, 6, 15, 12, 0, tzinfo=dt.timezone.utc)
    track = _make_track(4, t0)
    original_points_id = id(track['points'])
    original_first = track['points'][0]
    original_first_id = id(original_first)
    original_snapshot = dict(original_first)

    trim_track(track, t0, t0 + dt.timedelta(minutes=1))

    assert id(track['points']) == original_points_id
    assert len(track['points']) == 4
    assert id(track['points'][0]) == original_first_id
    assert track['points'][0] == original_snapshot


def test_trim_track_empty_result():
    t0 = dt.datetime(2024, 6, 15, 12, 0, tzinfo=dt.timezone.utc)
    track = _make_track(3, t0)
    trimmed = trim_track(track, t0 - dt.timedelta(hours=2), t0 - dt.timedelta(hours=1))
    assert trimmed['points'] == []
    assert trimmed['name'] == 'T'
    assert trimmed['description'] == 'd'


def test_trim_track_preserves_point_extensions():
    t0 = dt.datetime(2024, 6, 15, 12, 0, tzinfo=dt.timezone.utc)
    track = _make_track(3, t0, extras={'course': 42.0, 'hr': 120})
    trimmed = trim_track(track, t0, t0 + dt.timedelta(minutes=1))
    assert len(trimmed['points']) == 2
    for p in trimmed['points']:
        assert p['course'] == 42.0
        assert p['hr'] == 120


def test_trim_track_naive_vs_aware_raises():
    t0_naive = dt.datetime(2024, 6, 15, 12, 0)
    track = {'name': 'n', 'points': [{'lat': 0.0, 'lon': 0.0, 'time': t0_naive}]}
    aware_start = dt.datetime(2024, 6, 15, 11, 0, tzinfo=dt.timezone.utc)
    aware_end = dt.datetime(2024, 6, 15, 13, 0, tzinfo=dt.timezone.utc)
    with pytest.raises(ValueError):
        trim_track(track, aware_start, aware_end)


def test_trim_tracks_wrapper():
    t0 = dt.datetime(2024, 6, 15, 12, 0, tzinfo=dt.timezone.utc)
    tracks = [_make_track(5, t0), _make_track(5, t0 + dt.timedelta(hours=1))]
    trimmed = trim_tracks(tracks, t0, t0 + dt.timedelta(minutes=2))
    assert len(trimmed) == 2
    assert len(trimmed[0]['points']) == 3
    assert trimmed[1]['points'] == []


@pytest.mark.parametrize(
    ('relative_source', 'relative_output'),
    [
        ('track.gpx', 'track_cut.gpx'),
        ('track.GPX', 'track_cut.GPX'),
        ('track.GpX', 'track_cut.GpX'),
        ('track', 'track_cut.gpx'),
        ('folder.gpx/track.gpx', 'folder.gpx/track_cut.gpx'),
    ],
)
def test_cut_gpx_file_writes_a_sibling_without_changing_the_source(
    tmp_path, relative_source, relative_output
):
    source = tmp_path / relative_source
    source.parent.mkdir(parents=True, exist_ok=True)
    _write_cut_gpx(source)
    original = source.read_bytes()

    output = cut_gpx_file(
        source,
        dt.datetime(2024, 6, 15, 15, tzinfo=dt.timezone.utc),
        'start',
    )

    expected_output = tmp_path / relative_output
    assert Path(output) == expected_output
    assert expected_output.exists()
    assert source.read_bytes() == original


@pytest.mark.parametrize(
    ('cut_type', 'expected_times'),
    [
        ('start', ['2024-06-15T15:00:00+00:00', '2024-06-15T16:00:00+00:00']),
        ('end', ['2024-06-15T14:00:00+00:00', '2024-06-15T15:00:00+00:00']),
    ],
)
def test_cut_gpx_file_uses_inclusive_instants_and_preserves_metadata(
    tmp_path, cut_type, expected_times
):
    source = tmp_path / 'track.gpx'
    _write_cut_gpx(source)
    output = cut_gpx_file(source, '2024-06-15T17:00:00+02:00', cut_type)

    result = _parse_cut_gpx(Path(output))
    segment = result.tracks[0].segments[0]
    assert [point.time.isoformat() for point in segment.points] == expected_times
    assert result.creator == 'cut-test'
    assert result.name == 'Document name'
    assert result.description == 'Document description'
    assert result.tracks[0].name == 'Track name'
    assert result.tracks[0].description == 'Track description'
    assert result.tracks[0].type == 'other'
    assert result.tracks[0].extensions
    assert segment.extensions
    assert [point.elevation for point in segment.points] == [
        11.0 if cut_type == 'start' else 10.0,
        12.0 if cut_type == 'start' else 11.0,
    ]
    assert segment.points[-1].extensions
    output_xml = Path(output).read_text(encoding='utf-8')
    assert '<v:document>preserve</v:document>' in output_xml


def test_cut_gpx_file_with_empty_selection_preserves_empty_structure_and_metadata(tmp_path):
    source = tmp_path / 'track.gpx'
    _write_cut_gpx(source)

    output = cut_gpx_file(
        source,
        dt.datetime(2024, 6, 15, 13, tzinfo=dt.timezone.utc),
        'end',
    )

    result = _parse_cut_gpx(Path(output))
    assert result.name == 'Document name'
    assert result.description == 'Document description'
    assert len(result.tracks) == 1
    assert len(result.tracks[0].segments) == 1
    assert result.tracks[0].segments[0].points == []
    assert result.tracks[0].segments[0].extensions


def test_cut_gpx_file_rejects_invalid_cut_type_before_creating_output(tmp_path):
    source = tmp_path / 'track.gpx'
    _write_cut_gpx(source)
    original = source.read_bytes()

    with pytest.raises(ValueError, match='cut_type'):
        cut_gpx_file(source, '2024-06-15T15:00:00+00:00', 'middle')

    assert source.read_bytes() == original
    assert not (tmp_path / 'track_cut.gpx').exists()


def test_cut_gpx_file_does_not_overwrite_an_existing_destination(tmp_path):
    source = tmp_path / 'track.gpx'
    destination = tmp_path / 'track_cut.gpx'
    _write_cut_gpx(source)
    destination.write_text('keep this file', encoding='utf-8')

    with pytest.raises(FileExistsError):
        cut_gpx_file(source, '2024-06-15T15:00:00+00:00', 'start')

    assert destination.read_text(encoding='utf-8') == 'keep this file'


def test_cut_gpx_file_rejects_naive_timestamps_before_creating_output(tmp_path):
    source = tmp_path / 'track.gpx'
    _write_cut_gpx(source)

    with pytest.raises(ValueError, match='timezone-aware'):
        cut_gpx_file(source, dt.datetime(2024, 6, 15, 15), 'start')

    assert not (tmp_path / 'track_cut.gpx').exists()


def test_cut_gpx_file_rejects_naive_point_timestamps_before_creating_output(tmp_path):
    source = tmp_path / 'track.gpx'
    _write_cut_gpx(source, times=('2024-06-15T14:00:00',))

    with pytest.raises(ValueError, match='point timestamps must be timezone-aware'):
        cut_gpx_file(source, '2024-06-15T15:00:00+00:00', 'start')

    assert not (tmp_path / 'track_cut.gpx').exists()


def test_cut_gpx_file_ignores_points_without_timestamps(tmp_path):
    source = tmp_path / 'track.gpx'
    _write_cut_gpx(source, times=(None, '2024-06-15T15:00:00Z'))

    output = cut_gpx_file(source, '2024-06-15T15:00:00+00:00', 'start')

    result = _parse_cut_gpx(Path(output))
    points = result.tracks[0].segments[0].points
    assert len(points) == 1
    assert points[0].time.isoformat() == '2024-06-15T15:00:00+00:00'
