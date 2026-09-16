"""Exercise video CLI entry points with real, tiny renders."""

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
