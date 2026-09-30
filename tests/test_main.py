"""Exercise video CLI entry points with real, tiny renders."""

import datetime as dt
import os
from pathlib import Path
import subprocess
import sys

from PIL import Image
import pytest


ROOT = Path(__file__).resolve().parents[1]
CONSOLE = [
    sys.executable, '-c',
    'from gpx_player.main import main; import sys; sys.exit(main())',
]
MODULE = [sys.executable, '-m', 'gpx_player.main']


def test_video_metrics_and_line_data_exclude_invalid_track_edges():
    from gpx_player.main import _video_track_edges, _visible_track_data

    start = dt.datetime(2024, 6, 15, 12, 0, tzinfo=dt.timezone.utc)
    points = [
        (0, 0, start),
        (0, 0.0001, start + dt.timedelta(seconds=10)),
        (0, 1, start + dt.timedelta(seconds=20)),
        (0, 0.0002, start + dt.timedelta(seconds=30)),
        (0, 0.0003, start + dt.timedelta(seconds=40)),
    ]
    edges = _video_track_edges(points, [0, 0, 0, 0, 0])
    line_x, line_y = _visible_track_data(points, edges, 0, len(points))

    assert edges[0][0] > 0
    assert edges[0][2] > 0
    assert edges[1:3] == [None, None]
    assert edges[3][2] > 0
    assert line_x[0:2] == [0, 0.0001]
    assert line_x[3] == 1
    assert line_x[-2:] == [0.0002, 0.0003]
    assert [i for i, value in enumerate(line_x) if value != value] == [2, 4]
    assert [i for i, value in enumerate(line_y) if value != value] == [2, 4]
    stopped_points = [points[0], (0, 0, start + dt.timedelta(seconds=10))]
    stopped_edges = _video_track_edges(stopped_points, [0, 0])
    assert stopped_edges[0][0] == 0.0
    assert stopped_edges[0][2] == 0.0


def test_video_metrics_do_not_join_separate_gpx_segments():
    from gpx_player.main import _video_track_edges

    start = dt.datetime(2024, 6, 15, 12, 0, tzinfo=dt.timezone.utc)
    points = [
        (0, 0, start),
        (0, 0.001, start + dt.timedelta(minutes=1)),
        (0, 1, start + dt.timedelta(hours=1)),
    ]
    edges = _video_track_edges(points, [0, 0, 1])

    assert edges[0][0] > 0
    assert edges[0][2] > 0
    assert edges[1] is None


def test_video_callback_holds_at_segment_break_without_drawing_across_it(monkeypatch, tmp_path):
    import importlib

    video_main = importlib.import_module("gpx_player.main")
    start = dt.datetime(2024, 6, 15, 12, 0, tzinfo=dt.timezone.utc)
    next_segment = start + dt.timedelta(hours=1)
    path = tmp_path / "segments.gpx"
    path.write_text(
        '<gpx version="1.1" creator="tests" xmlns="http://www.topografix.com/GPX/1/1">'
        '<trk><trkseg>'
        '<trkpt lat="0" lon="0"><time>2024-06-15T12:00:00Z</time></trkpt>'
        '<trkpt lat="0" lon="0.001"><time>2024-06-15T12:01:00Z</time></trkpt>'
        '</trkseg><trkseg>'
        '<trkpt lat="0" lon="1"><time>2024-06-15T13:00:00Z</time></trkpt>'
        '</trkseg></trk></gpx>',
        encoding="utf-8",
    )
    midpoint = start + dt.timedelta(minutes=30)
    snapshots = []

    class RecordingAnimation:
        def __init__(self, figure, func, frames, fargs, **kwargs):
            self.func = func
            self.fargs = fargs

        def save(self, output, **kwargs):
            for frame_time in (midpoint, next_segment):
                artists = self.func(frame_time, *self.fargs)
                line, head, time_text, distance, speed = artists
                snapshots.append({
                    "line_x": tuple(line.get_xdata()),
                    "head": (head.get_visible(), tuple(head.get_xdata()), tuple(head.get_ydata())),
                    "time": time_text.get_text(),
                    "distance": distance.get_text(),
                    "speed": speed.get_text(),
                })

    monkeypatch.setattr(video_main.animation, "FuncAnimation", RecordingAnimation)
    monkeypatch.setattr(video_main.plt, "show", lambda: None)

    assert video_main.main([str(path), "--gif", "--output", str(tmp_path / "frames.gif")]) == 0

    in_gap, at_new_segment = snapshots
    assert in_gap["line_x"] == (0.0, 0.001)
    assert in_gap["head"] == (True, (0.001,), (0.0,))
    assert at_new_segment["line_x"][:2] == (0.0, 0.001)
    assert at_new_segment["line_x"][2] != at_new_segment["line_x"][2]
    assert at_new_segment["line_x"][3] == 1.0
    assert at_new_segment["head"] == (True, (1.0,), (0.0,))
    assert at_new_segment["distance"] == in_gap["distance"]
    assert at_new_segment["speed"] == "— kt"


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
