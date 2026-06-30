import datetime as dt
import importlib
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import pytest

import gpxpy.geo

from gpx_player.openseamap import (
    add_playback_controls,
    accumulate_distances,
    calculate_average_speeds,
    create_map,
    create_playback_map,
    parse_gpx,
    speed_to_color,
    _parse_iso_datetime,
)


def _write_sample_gpx(n_points=6, step_seconds=60, start="2024-06-15T12:00:00Z", track_name="Test Track"):
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
        f'        <name>{track_name}</name>\n'
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
    folium_map, all_tracks, _max_speed, _map_id = create_map([path], names=None, max_speed=12.0)

    assert len(all_tracks) == 1
    assert len(all_tracks[0]['points']) == 6
    assert all_tracks[0]['track_layer_name'].startswith('feature_group_')
    assert "L.control.layers" in folium_map.get_root().render()


def test_create_map_can_suppress_layer_control():
    path, _t0 = _write_sample_gpx(n_points=6)
    folium_map, all_tracks, _max_speed, _map_id = create_map(
        [path], names=None, max_speed=12.0, show_layer_control=False,
    )

    assert len(all_tracks) == 1
    assert "L.control.layers" not in folium_map.get_root().render()


def test_create_playback_map_renders_from_arbitrary_cwd(tmp_path, monkeypatch):
    path, _t0 = _write_sample_gpx(n_points=4)
    malicious_title = 'Race "</script><script>alert(1)</script>'
    malicious_name = 'Boat "</script><script>alert(2)</script>'

    monkeypatch.chdir(tmp_path)
    openseamap = importlib.import_module("gpx_player.openseamap")
    folium_map = openseamap.create_playback_map(
        [path],
        names=[malicious_name],
        max_speed=12.0,
        title=malicious_title,
    )

    rendered = folium_map.get_root().render()

    assert "window.gpxPlayerPlayback" in rendered
    assert "gpx-player-time-slider" in rendered
    assert "gpx-player-play-pause" in rendered
    assert "⏯️" in rendered
    assert "⏸️" in rendered
    assert "Speed (knots)" in rendered
    assert "Distance / Speed / Avg" in rendered
    assert "Race" in rendered
    assert "Boat" in rendered
    assert "sliderActiveColor" in rendered
    assert '"#6e6e6e"' in rendered
    assert "sliderInactiveColor" in rendered
    assert '"#d0d0d0"' in rendered
    assert '"tailPointCount": 60' in rendered
    assert '"fullTrackLayerNames": ["feature_group_' in rendered
    assert "gpx-player-track-visibility" in rendered
    assert "gpx-player-track-mode-select" in rendered
    assert "gpx-player-direction-marker" in rendered
    assert "L.divIcon" in rendered
    assert "L.marker" in rendered
    assert "L.circleMarker" not in rendered
    assert "Full" in rendered
    assert "Tail" in rendered
    assert "backgroundColor: 'rgba(0, 0, 0, 0.5)'" in rendered
    assert "width: '128px'" in rendered
    assert "width: '38px'" in rendered
    assert "minWidth: '190px'" not in rendered
    assert "L.control.layers" not in rendered
    assert "linear-gradient(" in rendered
    assert "--gpx-slider-progress" in rendered
    assert "outline: 2px solid #ffffff;" in rendered
    assert "outline-offset: 4px;" in rendered
    assert "box-shadow: 0 0 0 3px rgba(0, 0, 0, 0.45);" in rendered
    assert '</script><script>alert(1)</script>' not in rendered
    assert '</script><script>alert(2)</script>' not in rendered
    assert "\\u003c/script\\u003e\\u003cscript\\u003ealert(1)\\u003c/script\\u003e" in rendered
    assert "&lt;/script&gt;&lt;script&gt;alert(2)&lt;/script&gt;" in rendered
    assert 'document.querySelector("button")' not in rendered


def test_create_playback_map_renders_multi_track_boat_legend():
    path1, _ = _write_sample_gpx(n_points=4, track_name="Track One")
    path2, _ = _write_sample_gpx(n_points=4, track_name="Track Two")

    folium_map = create_playback_map(
        [path1, path2],
        names=["Alpha", "Beta"],
        max_speed=12.0,
        title="Fleet",
    )

    rendered = folium_map.get_root().render()

    assert "Alpha" in rendered
    assert "Beta" in rendered
    assert 'class="boat-entry"' in rendered
    assert 'data-index="0"' in rendered
    assert 'data-index="1"' in rendered
    assert rendered.count('class="boat-entry"') == 2


def test_create_playback_map_renders_custom_slider_colors():
    path, _ = _write_sample_gpx(n_points=4, track_name="Track One")

    folium_map = create_playback_map(
        [path],
        max_speed=12.0,
        slider_active_color="#112233",
        slider_inactive_color="rgb(210, 220, 230)",
    )

    rendered = folium_map.get_root().render()

    assert '"sliderActiveColor": "#112233"' in rendered
    assert '"sliderInactiveColor": "rgb(210, 220, 230)"' in rendered


@pytest.mark.parametrize(
    ("tail_length", "expected_points"),
    [
        ("short", 30),
        ("normal", 60),
        ("long", 120),
    ],
)
def test_create_playback_map_renders_tail_length_presets(tail_length, expected_points):
    path, _ = _write_sample_gpx(n_points=4, track_name="Track One")

    folium_map = create_playback_map(
        [path],
        max_speed=12.0,
        tail_length=tail_length,
    )

    rendered = folium_map.get_root().render()

    assert f'"tailPointCount": {expected_points}' in rendered


def test_create_playback_map_rejects_unknown_tail_length():
    path, _ = _write_sample_gpx(n_points=4, track_name="Track One")

    with pytest.raises(ValueError, match="tail_length must be one of"):
        create_playback_map([path], max_speed=12.0, tail_length="tiny")

    with pytest.raises(ValueError, match="tail_length must be one of"):
        create_playback_map(["does-not-exist.gpx"], max_speed=12.0, tail_length="tiny")


def test_add_playback_controls_accepts_custom_track_layer_names():
    path, _ = _write_sample_gpx(n_points=4, track_name="Track One")
    folium_map, all_tracks, max_speed, map_id = create_map(
        [path], names=None, max_speed=12.0, show_layer_control=False,
    )

    add_playback_controls(
        folium_map,
        all_tracks,
        max_speed=max_speed,
        map_id=map_id,
        tail_length="short",
        track_layer_names=["custom_full_track_layer"],
    )

    rendered = folium_map.get_root().render()

    assert '"tailPointCount": 30' in rendered
    assert '"fullTrackLayerNames": ["custom_full_track_layer"]' in rendered


def test_add_playback_controls_accepts_single_track_layer_name_string():
    path, _ = _write_sample_gpx(n_points=4, track_name="Track One")
    folium_map, all_tracks, max_speed, map_id = create_map(
        [path], names=None, max_speed=12.0, show_layer_control=False,
    )

    add_playback_controls(
        folium_map,
        all_tracks,
        max_speed=max_speed,
        map_id=map_id,
        track_layer_names="single_custom_layer",
    )

    rendered = folium_map.get_root().render()

    assert '"fullTrackLayerNames": ["single_custom_layer"]' in rendered


def test_add_playback_controls_rejects_bytes_track_layer_names():
    path, _ = _write_sample_gpx(n_points=4, track_name="Track One")
    folium_map, all_tracks, max_speed, map_id = create_map(
        [path], names=None, max_speed=12.0, show_layer_control=False,
    )

    with pytest.raises(TypeError, match="track_layer_names"):
        add_playback_controls(
            folium_map,
            all_tracks,
            max_speed=max_speed,
            map_id=map_id,
            track_layer_names=b"custom_layer",
        )


def test_playback_js_ignores_invalid_full_track_layer_and_limits_tail_updates():
    if not shutil.which("node"):
        pytest.skip("node is required for playback JS behavior test")

    asset_path = Path(__file__).resolve().parents[1] / "gpx_player" / "assets" / "animate_tracks.js"
    playback_js = asset_path.read_text(encoding="utf-8")
    script = f"""
const assert = require('assert');
const layers = new Set();
const map = {{
  addLayer(layer) {{ layers.add(layer); }},
  removeLayer(layer) {{ layers.delete(layer); }},
  hasLayer(layer) {{ return layers.has(layer); }}
}};
const fullTrackLayer = {{
  addTo(targetMap) {{ targetMap.addLayer(this); return this; }}
}};
layers.add(fullTrackLayer);
function makeElement(tag) {{
  return {{
    tagName: tag,
    style: {{ setProperty(name, value) {{ this[name] = value; }} }},
    children: [],
    listeners: {{}},
    appendChild(child) {{ this.children.push(child); return child; }},
    setAttribute(name, value) {{ this[name] = value; }},
    addEventListener(type, handler) {{ this.listeners[type] = handler; }},
    dispatchEvent(event) {{ if (this.listeners[event.type]) this.listeners[event.type](event); }},
  }};
}}
global.Event = function Event(type) {{ this.type = type; }};
global.window = global;
global.map_test = map;
global.validFullTrackLayer = fullTrackLayer;
global.document = {{
  readyState: 'complete',
  body: makeElement('body'),
  head: makeElement('head'),
  createElement: makeElement,
  createTextNode(text) {{ return {{ textContent: text }}; }},
  getElementById() {{ return null; }},
}};
global.L = {{
  divIcon(options) {{
    return options;
  }},
  marker(latlng, options) {{
    const arrow = {{ style: {{}} }};
    return {{
      latlng,
      icon: options.icon,
      options,
      addTo(targetMap) {{ targetMap.addLayer(this); return this; }},
      setLatLng(nextLatLng) {{ this.latlng = nextLatLng; }},
      setIcon(nextIcon) {{ this.icon = nextIcon; }},
      getElement() {{
        return {{
          querySelector(selector) {{
            return selector === '.gpx-player-direction-marker' ? arrow : null;
          }}
        }};
      }},
      arrow,
    }};
  }},
  polyline(latlngs) {{
    return {{
      latlngs,
      setLatLngCalls: 0,
      addTo(targetMap) {{ targetMap.addLayer(this); return this; }},
      setLatLngs(nextLatLngs) {{ this.setLatLngCalls += 1; this.latlngs = nextLatLngs; }},
    }};
  }},
  control() {{
    return {{
      addTo(targetMap) {{ this.container = this.onAdd(targetMap); return this; }},
    }};
  }},
  DomUtil: {{ create(_tag, className) {{ const element = makeElement(_tag); element.className = className; return element; }} }},
  DomEvent: {{
    disableClickPropagation() {{}},
    disableScrollPropagation() {{}},
    on(element, type, handler) {{ element.addEventListener(type, handler); }},
    stop() {{}},
  }},
}};
window.gpxPlayerPlayback = {{
  map_test: {{
    mapId: 'map_test',
    colors: ['red'],
    points: [[
      {{ lat: 1, lon: 1, time: '2024-06-15T12:00:00Z' }},
      {{ lat: 2, lon: 1, time: '2024-06-15T12:01:00Z' }},
      {{ lat: 2, lon: 2, time: '2024-06-15T12:02:00Z' }},
    ]],
    speeds: [[0, 1, 2]],
    distances: [[0, 1, 2]],
    avgSpeeds: [[0, 1, 2]],
    trackNames: ['Alpha'],
    timestamps: [
      '2024-06-15T12:00:00Z',
      '2024-06-15T12:01:00Z',
      '2024-06-15T12:02:00Z',
    ],
    minTime: '2024-06-15T12:00:00Z',
    maxTime: '2024-06-15T12:02:00Z',
    timeRange: 120,
    title: 'Test',
    sliderId: 'slider',
    timeLegendId: 'time',
    playPauseButtonId: 'play',
    boatLegendId: 'legend',
    sliderActiveColor: '#111',
    sliderInactiveColor: '#ddd',
    tailPointCount: 2,
    fullTrackLayerNames: ['document'],
  }}
}};
{playback_js}
const state = window.gpxPlayerPlayback.map_test;
assert.strictEqual(state.fullTrackLayers[0], null);
assert.ok(state.trackMarkers[0].icon.html.includes('gpx-player-direction-marker'));
assert.ok(state.trackMarkers[0].icon.html.includes('border-bottom: 13px solid red'));
const slider = state.slider;
const tailLayer = state.tailLayers[0];
assert.strictEqual(tailLayer.setLatLngCalls, 1);
assert.strictEqual(state.trackMarkers[0].arrow.style.transform, 'rotate(0deg)');
slider.value = 500;
slider.dispatchEvent(new Event('input'));
assert.strictEqual(tailLayer.setLatLngCalls, 1);
assert.strictEqual(state.trackMarkers[0].arrow.style.transform, 'rotate(0deg)');
state.trackModeControls[0].value = 'tail';
state.trackModeControls[0].dispatchEvent(new Event('change'));
assert.strictEqual(tailLayer.setLatLngCalls, 2);
slider.value = 1000;
slider.dispatchEvent(new Event('input'));
assert.strictEqual(tailLayer.setLatLngCalls, 3);
assert.strictEqual(state.trackMarkers[0].arrow.style.transform, 'rotate(90deg)');
assert.deepStrictEqual(tailLayer.latlngs, [[2, 1], [2, 2]]);
state.trackModeControls[0].value = 'off';
state.trackModeControls[0].dispatchEvent(new Event('change'));
assert.strictEqual(tailLayer.setLatLngCalls, 4);
slider.value = 0;
slider.dispatchEvent(new Event('input'));
assert.strictEqual(tailLayer.setLatLngCalls, 4);
assert.strictEqual(map.hasLayer(state.trackMarkers[0]), false);
"""
    result = subprocess.run(
        ["node", "-e", script],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_playback_js_marker_heading_handles_duplicate_points_and_full_layer_toggle():
    if not shutil.which("node"):
        pytest.skip("node is required for playback JS behavior test")

    asset_path = Path(__file__).resolve().parents[1] / "gpx_player" / "assets" / "animate_tracks.js"
    playback_js = asset_path.read_text(encoding="utf-8")
    script = f"""
const assert = require('assert');
const layers = new Set();
const map = {{
  addLayer(layer) {{ layers.add(layer); }},
  removeLayer(layer) {{ layers.delete(layer); }},
  hasLayer(layer) {{ return layers.has(layer); }}
}};
const fullTrackLayer = {{
  addTo(targetMap) {{ targetMap.addLayer(this); return this; }}
}};
layers.add(fullTrackLayer);
function makeElement(tag) {{
  return {{
    tagName: tag,
    style: {{ setProperty(name, value) {{ this[name] = value; }} }},
    children: [],
    listeners: {{}},
    appendChild(child) {{ this.children.push(child); return child; }},
    setAttribute(name, value) {{ this[name] = value; }},
    addEventListener(type, handler) {{ this.listeners[type] = handler; }},
    dispatchEvent(event) {{ if (this.listeners[event.type]) this.listeners[event.type](event); }},
  }};
}}
global.Event = function Event(type) {{ this.type = type; }};
global.window = global;
global.map_test = map;
global.validFullTrackLayer = fullTrackLayer;
global.document = {{
  readyState: 'complete',
  body: makeElement('body'),
  head: makeElement('head'),
  createElement: makeElement,
  createTextNode(text) {{ return {{ textContent: text }}; }},
  getElementById() {{ return null; }},
}};
global.L = {{
  divIcon(options) {{
    return options;
  }},
  marker(latlng, options) {{
    const arrow = {{ style: {{}} }};
    return {{
      latlng,
      icon: options.icon,
      options,
      addTo(targetMap) {{ targetMap.addLayer(this); return this; }},
      setLatLng(nextLatLng) {{ this.latlng = nextLatLng; }},
      setIcon(nextIcon) {{ this.icon = nextIcon; }},
      getElement() {{
        return {{
          querySelector(selector) {{
            return selector === '.gpx-player-direction-marker' ? arrow : null;
          }}
        }};
      }},
      arrow,
    }};
  }},
  polyline(latlngs) {{
    return {{
      latlngs,
      setLatLngCalls: 0,
      addTo(targetMap) {{ targetMap.addLayer(this); return this; }},
      setLatLngs(nextLatLngs) {{ this.setLatLngCalls += 1; this.latlngs = nextLatLngs; }},
    }};
  }},
  control() {{
    return {{
      addTo(targetMap) {{ this.container = this.onAdd(targetMap); return this; }},
    }};
  }},
  DomUtil: {{ create(_tag, className) {{ const element = makeElement(_tag); element.className = className; return element; }} }},
  DomEvent: {{
    disableClickPropagation() {{}},
    disableScrollPropagation() {{}},
    on(element, type, handler) {{ element.addEventListener(type, handler); }},
    stop() {{ throw new Error('L.DomEvent.stop should not be used for native select clicks'); }},
  }},
}};
window.gpxPlayerPlayback = {{
  map_test: {{
    mapId: 'map_test',
    colors: ['blue', 'green'],
    points: [
      [
        {{ lat: 1, lon: 1, time: '2024-06-15T12:00:00Z' }},
        {{ lat: 1, lon: 1, time: '2024-06-15T12:01:00Z' }},
        {{ lat: 2, lon: 1, time: '2024-06-15T12:02:00Z' }},
        {{ lat: 2, lon: 1, time: '2024-06-15T12:03:00Z' }},
        {{ lat: 2, lon: 2, time: '2024-06-15T12:04:00Z' }},
      ],
      [
        {{ lat: 5, lon: 5, time: '2024-06-15T12:00:00Z' }},
        {{ lat: 5, lon: 5, time: '2024-06-15T12:01:00Z' }},
      ],
    ],
    speeds: [[0, 0, 1, 0, 2], [0, 0]],
    distances: [[0, 0, 1, 1, 2], [0, 0]],
    avgSpeeds: [[0, 0, 1, 1, 2], [0, 0]],
    trackNames: ['Alpha', 'Bravo'],
    timestamps: [
      '2024-06-15T12:00:00Z',
      '2024-06-15T12:01:00Z',
      '2024-06-15T12:02:00Z',
      '2024-06-15T12:03:00Z',
      '2024-06-15T12:04:00Z',
    ],
    minTime: '2024-06-15T12:00:00Z',
    maxTime: '2024-06-15T12:04:00Z',
    timeRange: 240,
    title: 'Test',
    sliderId: 'slider',
    timeLegendId: 'time',
    playPauseButtonId: 'play',
    boatLegendId: 'legend',
    sliderActiveColor: '#111',
    sliderInactiveColor: '#ddd',
    tailPointCount: 2,
    fullTrackLayerNames: ['validFullTrackLayer', null],
  }}
}};
{playback_js}
const state = window.gpxPlayerPlayback.map_test;
const slider = state.slider;
assert.strictEqual(state.trackMarkers[0].arrow.style.transform, 'rotate(0deg)');
assert.strictEqual(state.trackMarkers[1].arrow.style.transform, 'rotate(0deg)');
assert.strictEqual(map.hasLayer(fullTrackLayer), true);

slider.value = 250;
slider.dispatchEvent(new Event('input'));
assert.strictEqual(state.trackMarkers[0].arrow.style.transform, 'rotate(0deg)');

slider.value = 750;
slider.dispatchEvent(new Event('input'));
assert.strictEqual(state.trackMarkers[0].arrow.style.transform, 'rotate(0deg)');

slider.value = 1000;
slider.dispatchEvent(new Event('input'));
assert.strictEqual(state.trackMarkers[0].arrow.style.transform, 'rotate(90deg)');

state.trackModeControls[0].value = 'tail';
state.trackModeControls[0].dispatchEvent(new Event('change'));
assert.strictEqual(map.hasLayer(fullTrackLayer), false);
assert.strictEqual(map.hasLayer(state.trackMarkers[0]), true);

state.trackModeControls[0].value = 'off';
state.trackModeControls[0].dispatchEvent(new Event('change'));
assert.strictEqual(map.hasLayer(fullTrackLayer), false);
assert.strictEqual(map.hasLayer(state.trackMarkers[0]), false);

state.trackModeControls[0].value = 'full';
state.trackModeControls[0].dispatchEvent(new Event('change'));
assert.strictEqual(map.hasLayer(fullTrackLayer), true);
assert.strictEqual(map.hasLayer(state.trackMarkers[0]), true);
"""
    result = subprocess.run(
        ["node", "-e", script],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_wheel_includes_playback_assets(tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    dist_dir = tmp_path / "dist"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            str(project_root),
            "--no-deps",
            "--no-build-isolation",
            "-w",
            str(dist_dir),
        ],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    wheel = next(dist_dir.glob("gpx_player-*.whl"))
    with zipfile.ZipFile(wheel) as zf:
        wheel_files = set(zf.namelist())

    expected_assets = {
        "gpx_player/assets/animate_tracks.js",
        "gpx_player/assets/speed_legend_template.html",
        "gpx_player/assets/boat_legend_template.html",
        "gpx_player/assets/header_template.html",
    }
    assert expected_assets <= wheel_files


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


def test_create_map_keeps_fallback_max_speed_when_no_positive_speed():
    # Every segment exceeds this tiny max_speed and gets clamped to 0 by
    # calculate_speeds. The recompute must keep the caller-supplied fallback
    # instead of collapsing to 0 (which would make speed_to_color divide by zero).
    path, _t0 = _write_sample_gpx(n_points=4, step_seconds=60)
    _map, _all_tracks, max_speed, _map_id = create_map(
        [path], names=None, max_speed=0.1,
    )
    assert max_speed == 0.1


def test_parse_iso_datetime_variants():
    cases = [
        "2026-04-12T17:01:00+0200",
        "2026-04-12T17:01:00+02:00",
        "2026-04-12T17:01:00.500+02:00",
        "2026-04-12T15:01:00Z",
    ]
    for s in cases:
        parsed = _parse_iso_datetime(s)
        assert parsed.tzinfo is not None, f"lost tz for {s!r}"


def test_create_map_rejects_inverted_window():
    path, t0 = _write_sample_gpx(n_points=4)
    start = t0 + dt.timedelta(minutes=10)
    end = t0 + dt.timedelta(minutes=1)
    with pytest.raises(ValueError):
        create_map([path], names=None, max_speed=12.0, start_time=start, end_time=end)


def test_create_map_names_stay_aligned_when_track_skipped():
    # file0 survives; file1's only track is fully outside the window and gets
    # skipped; file2 survives. The remaining tracks must keep their original
    # names positionally — not shift onto names[1].
    t_base = dt.datetime(2024, 6, 15, 12, 0, tzinfo=dt.timezone.utc)
    p0, _ = _write_sample_gpx(n_points=3, start=t_base.strftime("%Y-%m-%dT%H:%M:%SZ"))
    p1, _ = _write_sample_gpx(n_points=3, start=(t_base - dt.timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ"))
    p2, _ = _write_sample_gpx(n_points=3, start=t_base.strftime("%Y-%m-%dT%H:%M:%SZ"))

    start = t_base - dt.timedelta(minutes=1)
    end = t_base + dt.timedelta(hours=1)

    _map, all_tracks, _max_speed, _map_id = create_map(
        [p0, p1, p2], names=["Alex", "Ben", "Cara"], max_speed=12.0,
        start_time=start, end_time=end,
    )

    assert [t['display_name'] for t in all_tracks] == ["Alex", "Cara"]


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
