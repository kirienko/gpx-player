import argparse
import datetime as dt
import json
import re
from html import escape as html_escape
from importlib import resources
from typing import List, Optional, Sequence, Tuple

import folium
import gpxpy
import gpxpy.gpx
import jinja2
import matplotlib.pyplot as plt
from jinja2 import Environment, PackageLoader, select_autoescape

from gpx_player.gpx_utils import trim_track
from gpx_player.utils import track_serializer

_ASSET_PACKAGE = "gpx_player.assets"
_TRACK_COLORS = ['red', 'green', 'blue', 'orange', 'purple', 'brown', 'pink', 'yellow', 'cyan', 'magenta']
_COMPACT_TZ_RE = re.compile(r"([+-]\d{2})(\d{2})$")
_DEFAULT_SLIDER_ACTIVE_COLOR = "#6e6e6e"
_DEFAULT_SLIDER_INACTIVE_COLOR = "#d0d0d0"
_TAIL_LENGTH_PRESETS = {
    "short": 30,
    "normal": 60,
    "long": 120,
}


def _read_asset_text(filename: str) -> str:
    """Read a bundled static asset from the installed package."""
    try:
        return resources.files(_ASSET_PACKAGE).joinpath(filename).read_text(encoding="utf-8")
    except AttributeError:  # pragma: no cover - Python 3.8 compatibility
        return resources.read_text(_ASSET_PACKAGE, filename, encoding="utf-8")


def _template_env() -> Environment:
    return Environment(
        loader=PackageLoader("gpx_player", "assets"),
        autoescape=select_autoescape(("html", "xml")),
    )


def _json_for_inline_script(data) -> str:
    """Serialize JSON so it cannot terminate an inline script block."""
    return (
        json.dumps(data, default=track_serializer)
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def _display_name(track: dict) -> str:
    return str(track.get('display_name') or track.get('name') or 'Track')


def _boat_legend_id(map_id: Optional[str]) -> str:
    return f"gpx-player-boat-legend-{map_id}" if map_id else "boat-legend"


def _resolve_tail_point_count(tail_length: str) -> int:
    try:
        return _TAIL_LENGTH_PRESETS[tail_length]
    except KeyError:
        choices = ", ".join(_TAIL_LENGTH_PRESETS)
        raise ValueError(f"tail_length must be one of: {choices}") from None


def _normalize_track_layer_names(
    all_tracks: List[dict],
    track_layer_names: Optional[Sequence[Optional[str]]],
) -> List[Optional[str]]:
    if track_layer_names is None:
        names = [track.get('track_layer_name') for track in all_tracks]
    elif isinstance(track_layer_names, str):
        names = [track_layer_names]
    elif isinstance(track_layer_names, bytes):
        raise TypeError("track_layer_names must be a sequence of strings, not bytes")
    else:
        names = list(track_layer_names)
    normalized = [str(name) if name else None for name in names]
    if len(normalized) < len(all_tracks):
        normalized.extend([None] * (len(all_tracks) - len(normalized)))
    return normalized[:len(all_tracks)]


def _parse_iso_datetime(s: str) -> dt.datetime:
    # fromisoformat accepts fractional seconds and common ISO variants;
    # normalise a trailing 'Z' to '+00:00' for Python < 3.11 compatibility.
    normalized = s.replace('Z', '+00:00')
    normalized = _COMPACT_TZ_RE.sub(r"\1:\2", normalized)
    return dt.datetime.fromisoformat(normalized)


def parse_arguments():
    parser = argparse.ArgumentParser(description="Animate GPX tracks on an OpenSeaMap.")
    parser.add_argument('--files', nargs='+', required=True, help='GPX files to process')
    parser.add_argument('--names', '-n', nargs='+', help='Names of the participants')
    parser.add_argument('--max-speed', '-ms', type=float, default=12, help='Maximum speed in knots (default: 12)')
    parser.add_argument('--title', '-t', help='The title of the page')
    parser.add_argument('--start', '-s',
                        type=_parse_iso_datetime,
                        help='Start time (ISO 8601 with timezone, e.g. 2026-04-12T17:01:00+0200)')
    parser.add_argument('--end', '-e',
                        type=_parse_iso_datetime,
                        help='End time (ISO 8601 with timezone, e.g. 2026-04-12T17:33:00+0200)')
    parser.add_argument('--tail-length',
                        choices=tuple(_TAIL_LENGTH_PRESETS),
                        default='normal',
                        help='Tail length preset for map playback mode: short, normal, or long (default: normal)')
    return parser.parse_args()


def parse_gpx(file_path: str) -> List[dict]:
    with open(file_path, 'r') as gpx_file:
        gpx = gpxpy.parse(gpx_file)
        all_tracks = []
        for track in gpx.tracks:
            points = [
                {'lat': point.latitude, 'lon': point.longitude, 'time': point.time}
                for segment in track.segments
                for point in segment.points
            ]
            all_tracks.append({
                'name': track.name,
                'description': track.description,
                'points': points,
                })
    return all_tracks


def calculate_speeds(points: List[dict], max_speed: float) -> List[float]:
    """
    Calculates the speed of each point in the list of points.

    The `max_speed` is used to control the dirty data: if the speed is larger
    than some reasonable value (max_speed), then usually this means zero division,
    that's we simply nullify the speed.
    """
    speeds = []
    for i in range(1, len(points)):
        lat1, lon1, time1 = points[i - 1].values()
        lat2, lon2, time2 = points[i].values()
        distance = gpxpy.geo.haversine_distance(lat1, lon1, lat2, lon2)
        time_diff = (time2 - time1).total_seconds()
        if time_diff > 0:
            speed = (distance / time_diff) * 1.94384  # Convert m/s to knots
            if speed > max_speed:
                print(f"Warning: speed {speed:.2f} exceeds {max_speed} kn at time {time1} (dt = {time_diff:.2f}s)")
                speed = 0
            speeds.append(speed)
        else:
            speeds.append(0)
    return speeds


def accumulate_distances(points: List[dict]) -> List[float]:
    """Return cumulative distance in nautical miles for each point."""
    distances = [0.0]
    total = 0.0
    for i in range(1, len(points)):
        lat1, lon1 = points[i - 1]['lat'], points[i - 1]['lon']
        lat2, lon2 = points[i]['lat'], points[i]['lon']
        total += gpxpy.geo.haversine_distance(lat1, lon1, lat2, lon2) / 1852.0
        distances.append(total)
    return distances


def calculate_average_speeds(points: List[dict], distances: List[float]) -> List[float]:
    """Return average speed in knots for each point."""
    avgs = [0.0]
    start_time = points[0]['time']
    for i in range(1, len(points)):
        hours = (points[i]['time'] - start_time).total_seconds() / 3600.0
        if hours > 0:
            avgs.append(distances[i] / hours)
        else:
            avgs.append(0.0)
    return avgs


def speed_to_color(speed: float, max_speed: float) -> str:
    norm_speed = min(speed / max_speed, 1.0)
    # norm_speed = min(speed / max(1,max_speed), 1.0)
    color = plt.cm.RdYlGn(norm_speed)
    return (
        f"#{int(color[0] * 255):02x}"
        f"{int(color[1] * 255):02x}"
        f"{int(color[2] * 255):02x}"
    )


def create_map(
    gpx_files: List[str],
    names: Optional[List[str]],
    max_speed: float,
    start_time: Optional[dt.datetime] = None,
    end_time: Optional[dt.datetime] = None,
    *,
    show_layer_control: bool = True,
) -> Tuple[folium.Map, List[dict], float, str]:
    """Create an interactive map from GPX files.

    When ``start_time`` and/or ``end_time`` are provided, only points within
    ``[start_time, end_time]`` are rendered. Points outside the window are
    excluded from the map, speed calculations, and distance totals.
    """
    if start_time is not None and end_time is not None and start_time > end_time:
        raise ValueError(
            f"start_time ({start_time}) must be <= end_time ({end_time})"
        )

    folium_map = folium.Map(location=[0, 0], zoom_start=12, control_scale=True, attributionControl=False, tiles=None)
    map_id = folium_map.get_name()

    folium.TileLayer('openstreetmap', control=False).add_to(folium_map)
    # Add OpenSeaMap layer directly to the map, not to the layer control
    folium.TileLayer(
        tiles='https://tiles.openseamap.org/seamark/{z}/{x}/{y}.png',
        attr='OpenSeaMap',
        overlay=False,
        control=False,  # Set control to `False` to exclude from layer control
    ).add_to(folium_map)

    all_tracks = []
    source_index = -1
    for gpx_file in gpx_files:
        for track in parse_gpx(gpx_file):
            # source_index reflects the pre-filter position so that skipping
            # empty-trimmed tracks below cannot shift later names[i] lookups.
            source_index += 1
            display_name = (
                names[source_index]
                if names and source_index < len(names)
                else track.get('name')
            )
            if display_name is None:
                display_name = f"Track {source_index + 1}"
            if start_time is not None or end_time is not None:
                lo = start_time if start_time is not None else dt.datetime.min.replace(tzinfo=dt.timezone.utc)
                hi = end_time if end_time is not None else dt.datetime.max.replace(tzinfo=dt.timezone.utc)
                track = trim_track(track, lo, hi)
            points = track['points']
            if not points:
                print(f"Warning: track '{track.get('name')}' has no points in "
                      f"[{start_time}, {end_time}]; skipping.")
                continue
            seg_speeds = calculate_speeds(points, max_speed)
            distances = accumulate_distances(points)
            avg_speeds = calculate_average_speeds(points, distances)
            point_speeds = [0.0] + seg_speeds
            all_tracks.append({
                'name': track['name'],
                'display_name': display_name,
                'points': points,
                'point_speeds': point_speeds,
                'distances': distances,
                'avg_speeds': avg_speeds,
                'seg_speeds': seg_speeds,
            })

    positive_speeds = [s for track in all_tracks for s in track['seg_speeds'] if s > 0]
    if positive_speeds:
        max_speed = max(positive_speeds)

    # Calculate map bounds
    latitudes = [p['lat'] for track in all_tracks for p in track['points']]
    longitudes = [p['lon'] for track in all_tracks for p in track['points']]
    if latitudes and longitudes:
        folium_map.fit_bounds([[min(latitudes), min(longitudes)], [max(latitudes), max(longitudes)]])

    track_layers = []
    
    for i, track in enumerate(all_tracks):
        color = _TRACK_COLORS[i % len(_TRACK_COLORS)]
        lat_lon = [(p['lat'], p['lon']) for p in track['points']]
        speeds = track['seg_speeds']
        times = [p['time'].strftime('%Y-%m-%d %H:%M:%S') for p in track['points']]
        name = _display_name(track)
        escaped_name = html_escape(name, quote=True)

        track_layer = folium.FeatureGroup(name=f"<span style='color:{color};'>&#9679;</span> {escaped_name}", show=True)
        for j in range(len(lat_lon) - 1):
            color = speed_to_color(speeds[j], max_speed)
            tooltip_content = f"Name: {escaped_name}<br>Time: {times[j]} UTC<br>Speed: {speeds[j]:.2f} knots"
            folium.PolyLine(
                lat_lon[j:j + 2],
                color=color,
                weight=2.5,
                opacity=1,
                tooltip=folium.Tooltip(tooltip_content)
            ).add_to(track_layer)
        track_layers.append(track_layer)
        track['track_layer_name'] = track_layer.get_name()
        folium_map.add_child(track_layer)
    
    if show_layer_control:
        folium.LayerControl(collapsed=False).add_to(folium_map)

    return folium_map, all_tracks, max_speed, map_id


def _add_animation_script(
    folium_map: folium.Map,
    all_tracks: List[dict],
    *,
    title: Optional[str],
    map_id: str,
    boat_legend_id: str,
    slider_active_color: Optional[str] = None,
    slider_inactive_color: Optional[str] = None,
    tail_point_count: int = _TAIL_LENGTH_PRESETS["normal"],
    track_layer_names: Optional[Sequence[Optional[str]]] = None,
) -> None:
    gpx_points_data = [track['points'] for track in all_tracks]
    gpx_speeds_data = [track['point_speeds'] for track in all_tracks]
    gpx_distances_data = [track['distances'] for track in all_tracks]
    gpx_avg_speeds_data = [track['avg_speeds'] for track in all_tracks]
    track_names = [_display_name(track) for track in all_tracks]
    full_track_layer_names = _normalize_track_layer_names(all_tracks, track_layer_names)
    gpx_timestamps = sorted({p['time'] for track in all_tracks for p in track['points']})
    min_time, max_time = min(gpx_timestamps), max(gpx_timestamps)
    time_range = (max_time - min_time).total_seconds()
    payload = {
        "mapId": map_id,
        "colors": _TRACK_COLORS,
        "points": gpx_points_data,
        "speeds": gpx_speeds_data,
        "distances": gpx_distances_data,
        "avgSpeeds": gpx_avg_speeds_data,
        "trackNames": track_names,
        "timestamps": gpx_timestamps,
        "minTime": min_time,
        "maxTime": max_time,
        "timeRange": time_range,
        "title": title or "GPX Player",
        "sliderId": f"gpx-player-slider-{map_id}",
        "timeLegendId": f"gpx-player-time-legend-{map_id}",
        "playPauseButtonId": f"gpx-player-play-pause-{map_id}",
        "boatLegendId": boat_legend_id,
        "sliderActiveColor": slider_active_color or _DEFAULT_SLIDER_ACTIVE_COLOR,
        "sliderInactiveColor": slider_inactive_color or _DEFAULT_SLIDER_INACTIVE_COLOR,
        "tailPointCount": tail_point_count,
        "fullTrackLayerNames": full_track_layer_names,
    }
    map_id_json = _json_for_inline_script(map_id)
    payload_json = _json_for_inline_script(payload)
    animation_script = f"""
    <script>
    window.gpxPlayerPlayback = window.gpxPlayerPlayback || {{}};
    window.gpxPlayerPlayback[{map_id_json}] = {payload_json};
    document.title = window.gpxPlayerPlayback[{map_id_json}].title;
    </script>
    <script>
    {_read_asset_text('animate_tracks.js')}
    </script>
    """
    folium_map.get_root().html.add_child(folium.Element(animation_script))


def _add_header(
    folium_map: folium.Map,
    title: str,
    map_id: str,
    jinja_env: Optional[jinja2.Environment] = None,
) -> None:
    template = (jinja_env or _template_env()).get_template('header_template.html')
    header_html = template.render(title=title, map_id=map_id)
    folium_map.get_root().html.add_child(folium.Element(header_html))


def add_playback_controls(
    folium_map: folium.Map,
    all_tracks: List[dict],
    *,
    max_speed: float,
    map_id: str,
    title: Optional[str] = None,
    slider_active_color: Optional[str] = _DEFAULT_SLIDER_ACTIVE_COLOR,
    slider_inactive_color: Optional[str] = _DEFAULT_SLIDER_INACTIVE_COLOR,
    tail_length: str = "normal",
    track_layer_names: Optional[Sequence[Optional[str]]] = None,
) -> None:
    """Add playback UI, legends, markers, and data to a Folium map.

    The templates and JavaScript are loaded from package resources, so this
    works from an installed wheel regardless of the current working directory.
    """
    tail_point_count = _resolve_tail_point_count(tail_length)
    if not all_tracks:
        return

    env = _template_env()
    boat_legend_id = _boat_legend_id(map_id)
    _add_animation_script(
        folium_map,
        all_tracks,
        title=title,
        map_id=map_id,
        boat_legend_id=boat_legend_id,
        slider_active_color=slider_active_color,
        slider_inactive_color=slider_inactive_color,
        tail_point_count=tail_point_count,
        track_layer_names=track_layer_names,
    )
    if title:
        _add_header(folium_map, title, map_id, env)
    add_legend(folium_map, max_speed, env, map_id=map_id)
    add_boat_legend(
        folium_map,
        [_display_name(track) for track in all_tracks],
        env,
        map_id=map_id,
    )


def create_playback_map(
    gpx_files: List[str],
    names: Optional[List[str]] = None,
    *,
    max_speed: float = 12,
    title: Optional[str] = None,
    start_time: Optional[dt.datetime] = None,
    end_time: Optional[dt.datetime] = None,
    slider_active_color: Optional[str] = _DEFAULT_SLIDER_ACTIVE_COLOR,
    slider_inactive_color: Optional[str] = _DEFAULT_SLIDER_INACTIVE_COLOR,
    tail_length: str = "normal",
) -> folium.Map:
    """Create a static OpenSeaMap with GPX playback controls."""
    _resolve_tail_point_count(tail_length)
    folium_map, all_tracks, actual_max_speed, map_id = create_map(
        gpx_files,
        names,
        max_speed,
        start_time=start_time,
        end_time=end_time,
        show_layer_control=False,
    )
    add_playback_controls(
        folium_map,
        all_tracks,
        max_speed=actual_max_speed,
        map_id=map_id,
        title=title,
        slider_active_color=slider_active_color,
        slider_inactive_color=slider_inactive_color,
        tail_length=tail_length,
    )
    return folium_map


def add_animation(folium_map: folium.Map,
                  all_tracks: List[dict],
                  jinja_env: Optional[jinja2.Environment] = None,
                  title: Optional[str] = None,
                  map_id: Optional[str] = None,
                  slider_active_color: Optional[str] = _DEFAULT_SLIDER_ACTIVE_COLOR,
                  slider_inactive_color: Optional[str] = _DEFAULT_SLIDER_INACTIVE_COLOR,
                  tail_length: str = "normal") -> None:
    """Backward-compatible wrapper for adding playback animation assets."""
    tail_point_count = _resolve_tail_point_count(tail_length)
    if not all_tracks:
        return
    map_id = map_id or folium_map.get_name()
    _add_animation_script(
        folium_map,
        all_tracks,
        title=title,
        map_id=map_id,
        boat_legend_id="boat-legend",
        slider_active_color=slider_active_color,
        slider_inactive_color=slider_inactive_color,
        tail_point_count=tail_point_count,
    )
    if title:
        _add_header(folium_map, title, map_id, jinja_env)


def add_legend(
    folium_map: folium.Map,
    max_speed: float,
    jinja_env: Optional[jinja2.Environment] = None,
    *,
    map_id: Optional[str] = None,
) -> None:
    template = (jinja_env or _template_env()).get_template('speed_legend_template.html')
    legend_html = template.render(max_speed=max_speed, map_id=map_id)
    folium_map.get_root().html.add_child(folium.Element(legend_html))


def add_boat_legend(
    folium_map: folium.Map,
    names: List[str],
    jinja_env: Optional[jinja2.Environment] = None,
    *,
    map_id: Optional[str] = None,
) -> None:
    template = (jinja_env or _template_env()).get_template('boat_legend_template.html')
    legend_html = template.render(
        names=[str(name) for name in names],
        colors=_TRACK_COLORS,
        map_id=map_id,
        boat_legend_id=_boat_legend_id(map_id),
    )
    folium_map.get_root().html.add_child(folium.Element(legend_html))


def main():
    args = parse_arguments()
    gpx_files = args.files
    names = args.names

    folium_map, all_tracks, max_speed, map_id = create_map(
        gpx_files, names, args.max_speed,
        start_time=args.start, end_time=args.end,
        show_layer_control=False,
    )
    if not all_tracks:
        print("No GPX points found in the selected time window; nothing to render.")
        return
    add_playback_controls(
        folium_map,
        all_tracks,
        max_speed=max_speed,
        map_id=map_id,
        title=args.title,
        tail_length=args.tail_length,
    )

    folium_map.save('boat_tracks.html')
    print('Map has been saved to boat_tracks.html')

if __name__ == "__main__":
    main()
