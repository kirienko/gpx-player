"""Exercise video CLI entry points with real, tiny renders."""

import datetime as dt
import importlib
import os
from pathlib import Path
import subprocess
import sys

import gpxpy
from PIL import Image
import pytest


ROOT = Path(__file__).resolve().parents[1]
CONSOLE = [
    sys.executable, '-c',
    'from gpx_player.main import main; import sys; sys.exit(main())',
]
MODULE = [sys.executable, '-m', 'gpx_player.main']


def run_cli(tmp_path, command, *args):
    env = dict(os.environ, MPLBACKEND='Agg',
               MPLCONFIGDIR=os.environ.get('MPLCONFIGDIR', str(tmp_path.parent / 'mpl')),
               PYTHONPATH=str(ROOT))
    return subprocess.run(command + list(args), cwd=tmp_path, env=env,
                          capture_output=True, text=True, timeout=45)


@pytest.fixture
def track(tmp_path):
    path = tmp_path / 'track.gpx'
    path.write_text('''<gpx version="1.1" creator="tests"
        xmlns="http://www.topografix.com/GPX/1/1"><trk><trkseg>
        <trkpt lat="53.5" lon="9.8"><time>2023-07-01T11:00:00Z</time></trkpt>
        <trkpt lat="53.5001" lon="9.8001"><time>2023-07-01T11:00:01Z</time></trkpt>
        </trkseg></trk></gpx>''', encoding='utf-8')
    return str(path)


def write_track(path, points):
    track_points = ''.join(
        f'<trkpt lat="{lat}" lon="{lon}"><time>{timestamp}</time></trkpt>'
        for lat, lon, timestamp in points
    )
    path.write_text(
        '<gpx version="1.1" creator="tests" xmlns="http://www.topografix.com/GPX/1/1">'
        f'<trk><trkseg>{track_points}</trkseg></trk></gpx>',
        encoding='utf-8',
    )
    return str(path)


@pytest.fixture
def staggered_tracks(tmp_path):
    start = dt.datetime.fromisoformat('2023-07-01T11:00:00+00:00')

    def point(minutes, lat, lon):
        time = start + dt.timedelta(minutes=minutes)
        return lat, lon, time.isoformat().replace('+00:00', 'Z')

    early = write_track(tmp_path / 'early.gpx', [
        point(0, 53.5, 9.8),
        point(1, 53.5, 9.801),
        point(2, 53.5, 9.802),
    ])
    late = write_track(tmp_path / 'late.gpx', [
        point(1.5, 54.0, 10.0),
        point(2.5, 54.0, 10.001),
    ])
    return start.astimezone(dt.timezone(dt.timedelta(hours=2))), early, late


def run_frame_callbacks(monkeypatch, tmp_path, tracks, callback_times, *options):
    monkeypatch.setenv('MPLCONFIGDIR', str(tmp_path / 'mpl'))
    video_main = importlib.import_module('gpx_player.main')
    snapshots = []

    class RecordingAnimation:
        def __init__(self, figure, func, frames, fargs, **kwargs):
            self.func = func
            self.fargs = fargs

        def save(self, output, **kwargs):
            for current_time in callback_times:
                artists = self.func(current_time, *self.fargs)
                track_count = len(self.fargs[0])
                lines = artists[:track_count]
                heads = artists[track_count:track_count * 2]
                time_text = artists[track_count * 2]
                distances = artists[track_count * 2 + 1:track_count * 3 + 1]
                speeds = artists[track_count * 3 + 1:track_count * 4 + 1]
                snapshots.append({
                    'line_x': tuple(tuple(line.get_xdata()) for line in lines),
                    'line_y': tuple(tuple(line.get_ydata()) for line in lines),
                    'heads': tuple(
                        (head.get_visible(), tuple(head.get_xdata()), tuple(head.get_ydata()))
                        for head in heads
                    ),
                    'distances': tuple(text.get_text() for text in distances),
                    'speeds': tuple(text.get_text() for text in speeds),
                    'time': time_text.get_text(),
                })

    monkeypatch.setattr(video_main.animation, 'FuncAnimation', RecordingAnimation)
    monkeypatch.setattr(video_main.plt, 'show', lambda: None)
    assert video_main.main([
        *tracks, '--gif', '--output', str(tmp_path / 'frames.gif'), *options,
    ]) == 0
    return snapshots


def test_import_does_not_parse_arguments_or_create_figures(tmp_path):
    result = run_cli(tmp_path, [sys.executable, '-c', '''
import sys
from unittest.mock import patch
import matplotlib.pyplot as plt
sys.argv = ['host-program', '--unrelated-option']
with patch('argparse.ArgumentParser.parse_args', side_effect=AssertionError('parsed argv')):
    with patch.object(plt, 'subplots', side_effect=AssertionError('created figure')):
        from gpx_player.main import main
assert callable(main)
'''])
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize('command', [CONSOLE, MODULE], ids=['console', 'module'])
@pytest.mark.parametrize('options,filename', [
    (['--title', 'Exit Test'], 'exit-test.gif'),
    ([], 'untitled.gif'),
    (['--title', 'Ignored', '-o', 'custom name.gif'], 'custom name.gif'),
    (['--output', 'explicit.gif'], 'explicit.gif'),
])
def test_successful_render_exits_zero(tmp_path, track, command, options, filename):
    result = run_cli(tmp_path, command, track, '-g', *options)
    assert result.returncode == 0, result.stderr
    with Image.open(tmp_path / filename) as rendered:
        assert rendered.format == 'GIF'
        assert rendered.n_frames == 2
    assert sorted(p.name for p in tmp_path.glob('*.gif')) == [filename]


def test_video_metrics_and_track_artists_follow_each_frame(monkeypatch, tmp_path, staggered_tracks):
    start, early, late = staggered_tracks
    first_minute = start + dt.timedelta(minutes=1)
    second_minute = start + dt.timedelta(minutes=2)
    late_finish = start + dt.timedelta(minutes=2, seconds=30)
    callbacks = [start - dt.timedelta(seconds=1), first_minute, second_minute,
                 first_minute, late_finish, start + dt.timedelta(minutes=10)]

    snapshots = run_frame_callbacks(monkeypatch, tmp_path, [early, late], callbacks)

    before_tracks = snapshots[0]
    assert before_tracks['line_x'] == ((), ())
    assert before_tracks['heads'] == ((False, (), ()), (False, (), ()))

    at_one_minute = snapshots[1]
    assert at_one_minute['line_x'] == ((9.8, 9.801), ())
    assert at_one_minute['line_y'] == ((53.5, 53.5), ())
    assert at_one_minute['heads'][0] == (True, (9.801,), (53.5,))
    assert at_one_minute['heads'][1][0] is False
    first_leg_nm = gpxpy.geo.haversine_distance(53.5, 9.8, 53.5, 9.801) / 1000 / 1.852
    assert at_one_minute['distances'][0] == f'{first_leg_nm:.2f} nm'
    assert at_one_minute['speeds'][0] == f'{first_leg_nm * 60:.1f} kt'
    assert at_one_minute['distances'][1:] == ('0.00 nm',)
    assert at_one_minute['speeds'][1:] == ('0.0 kt',)
    assert at_one_minute['time'] == 'Time: 2023-07-01 13:01:00'

    assert snapshots[1] == snapshots[3]

    finished = snapshots[4]
    completed = snapshots[5]
    assert completed['line_x'][1] == (10.0, 10.001)
    assert completed['heads'][1] == (True, (10.001,), (54.0,))
    assert completed['distances'][1] == finished['distances'][1]
    assert completed['speeds'][1] == finished['speeds'][1]


def test_race_start_is_the_video_metrics_baseline(monkeypatch, tmp_path, staggered_tracks):
    start, early, late = staggered_tracks
    race_start = start + dt.timedelta(seconds=30)
    frame = start + dt.timedelta(minutes=1)

    [snapshot] = run_frame_callbacks(
        monkeypatch, tmp_path, [early, late], [frame],
        '--race_start', race_start.strftime('%Y-%m-%dT%H:%M:%S%z'),
    )

    full_leg_nm = gpxpy.geo.haversine_distance(53.5, 9.8, 53.5, 9.801) / 1000 / 1.852
    assert snapshot['distances'][0] == f'{full_leg_nm / 2:.2f} nm'
    [without_baseline] = run_frame_callbacks(
        monkeypatch, tmp_path, [early, late], [frame],
    )
    assert without_baseline['distances'][0] == f'{full_leg_nm:.2f} nm'
    assert snapshot['speeds'][0] == without_baseline['speeds'][0]
    assert snapshot['time'] == 'Time of the race: 00:30'


@pytest.mark.parametrize(('timestamps', 'description'), [
    (['2023-07-01T11:00:00Z', '2023-07-01T11:00:00Z'], 'duplicate'),
    (['2023-07-01T11:00:01Z', '2023-07-01T11:00:00Z'], 'decreasing'),
    (['2023-07-01T11:00:00', '2023-07-01T11:01:00'], 'timezone-aware'),
])
def test_invalid_video_timestamps_fail_before_rendering(tmp_path, timestamps, description):
    bad_track = write_track(tmp_path / 'bad.gpx', [
        (53.5, 9.8, timestamps[0]),
        (53.501, 9.801, timestamps[1]),
    ])

    result = run_cli(tmp_path, MODULE, bad_track, '-g')

    assert result.returncode != 0
    assert description in result.stderr.lower()
    assert 'bad.gpx' in result.stderr
    assert 'Traceback' not in result.stderr
    assert not list(tmp_path.glob('*.gif'))


@pytest.mark.parametrize('command', [CONSOLE, MODULE], ids=['console', 'module'])
def test_empty_window_is_a_clear_failure(tmp_path, track, command):
    result = run_cli(tmp_path, command, track, '-g', '--start', '2024-01-01T00:00:00+0000')
    assert result.returncode != 0
    assert 'No points in the selected window' in result.stderr
    assert 'track.gpx' in result.stderr
    assert 'Traceback' not in result.stderr
    assert not list(tmp_path.glob('*.gif'))


def test_one_empty_track_fails_before_rendering(tmp_path, track):
    empty = tmp_path / 'empty.gpx'
    empty.write_text('<gpx version="1.1" creator="tests"/>', encoding='utf-8')
    result = run_cli(tmp_path, CONSOLE, track, str(empty), '-g')
    assert result.returncode != 0
    assert 'No points in the selected window' in result.stderr
    assert 'empty.gpx' in result.stderr
    assert not list(tmp_path.glob('*.gif'))


@pytest.mark.parametrize('command', [CONSOLE, MODULE], ids=['console', 'module'])
def test_save_failure_is_not_success(tmp_path, track, command):
    result = run_cli(tmp_path, command, track, '-g', '-o', 'missing/output.gif')
    assert result.returncode != 0
    assert 'No such file or directory' in result.stderr
    assert not list(tmp_path.glob('*.gif'))
