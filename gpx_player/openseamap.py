import argparse
import json
from typing import List, Tuple

import folium
import gpxpy
import gpxpy.gpx
import jinja2
import matplotlib.pyplot as plt
from jinja2 import Environment, FileSystemLoader

from gpx_player.utils import track_serializer


def parse_arguments():
    parser = argparse.ArgumentParser(description="Animate GPX tracks on an OpenSeaMap.")
    parser.add_argument('--files', nargs='+', required=True, help='GPX files to process')
    parser.add_argument('--names', '-n', nargs='+', help='Names of the participants')
    parser.add_argument('--max-speed', '-ms', type=float, default=12, help='Maximum speed in knots (default: 12)')
    parser.add_argument('--title', '-t', help='The title of the page')
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


def create_map(gpx_files: List[str], names: List[str], max_speed: float) -> Tuple[folium.Map, List[List], float, str]:
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
    original_names = []
    for gpx_file in gpx_files:
        for track in parse_gpx(gpx_file):
            points = track['points']
            seg_speeds = calculate_speeds(points, max_speed)
            distances = accumulate_distances(points)
            avg_speeds = calculate_average_speeds(points, distances)
            point_speeds = [0.0] + seg_speeds
            all_tracks.append({
                'name': track['name'],
                'points': points,
                'point_speeds': point_speeds,
                'distances': distances,
                'avg_speeds': avg_speeds,
                'seg_speeds': seg_speeds,
            })
            original_names.append(track['name'])

    max_speed = max(s for track in all_tracks for s in track['seg_speeds'])

    # Calculate map bounds
    latitudes = [p['lat'] for track in all_tracks for p in track['points']]
    longitudes = [p['lon'] for track in all_tracks for p in track['points']]
    folium_map.fit_bounds([[min(latitudes), min(longitudes)], [max(latitudes), max(longitudes)]])

    track_layers = []
    colors = ['red', 'green', 'blue', 'orange', 'purple', 'brown', 'pink', 'yellow', 'cyan', 'magenta']
    
    for i, track in enumerate(all_tracks):
        color = colors[i % len(colors)]
        lat_lon = [(p['lat'], p['lon']) for p in track['points']]
        speeds = track['seg_speeds']
        times = [p['time'].strftime('%Y-%m-%d %H:%M:%S') for p in track['points']]
        name = names[i] if names and i < len(names) else original_names[i]

        track_layer = folium.FeatureGroup(name=f"<span style='color:{color};'>&#9679;</span> {name}", show=True)
        for j in range(len(lat_lon) - 1):
            color = speed_to_color(speeds[j], max_speed)
            tooltip_content = f"Name: {name}<br>Time: {times[j]} UTC<br>Speed: {speeds[j]:.2f} knots"
            folium.PolyLine(
                lat_lon[j:j + 2],
                color=color,
                weight=2.5,
                opacity=1,
                tooltip=folium.Tooltip(tooltip_content)
            ).add_to(track_layer)
        track_layers.append(track_layer)
        folium_map.add_child(track_layer)
    
    folium.LayerControl(collapsed=False).add_to(folium_map)

    return folium_map, all_tracks, max_speed, map_id


def add_animation(folium_map: folium.Map,
                  all_tracks: List[dict],
                  jinja_env: jinja2.Environment,
                  title: str, map_id: str) -> None:
    gpx_points_data = [track['points'] for track in all_tracks]
    gpx_speeds_data = [track['point_speeds'] for track in all_tracks]
    gpx_distances_data = [track['distances'] for track in all_tracks]
    gpx_avg_speeds_data = [track['avg_speeds'] for track in all_tracks]
    track_names = [track['name'] for track in all_tracks]
    gpx_timestamps = sorted({p['time'] for track in all_tracks for p in track['points']})
    min_time, max_time = min(gpx_timestamps), max(gpx_timestamps)
    time_range = (max_time - min_time).total_seconds()

    animation_script = f"""
    <script>
    var gpx_points_data = {json.dumps(gpx_points_data, default=track_serializer)};
    var gpx_speeds_data = {json.dumps(gpx_speeds_data)};
    var gpx_distances_data = {json.dumps(gpx_distances_data)};
    var gpx_avg_speeds_data = {json.dumps(gpx_avg_speeds_data)};
    var track_names = {json.dumps(track_names)};
    var gpx_timestamps = {json.dumps([t for t in gpx_timestamps], default=track_serializer)};
    var min_time = new Date('{min_time.strftime('%Y-%m-%dT%H:%M:%S%z')}').getTime();
    var max_time = new Date('{max_time.strftime('%Y-%m-%dT%H:%M:%S%z')}').getTime();
    var time_range = {time_range};
    var map_id = "{map_id}";
    document.title = "{title if title else 'GPX Player'}";
    </script>
    <script>                                                                                                                                                                                                                       
    {open('animate_tracks.js', encoding='UTF-8').read()}                                                                                                                                                                                             
    </script>
    """
    folium_map.get_root().html.add_child(folium.Element(animation_script))

    if title:
        template = jinja_env.get_template('header_template.html')
        header_html = template.render(title=title)
        folium_map.get_root().html.add_child(folium.Element(header_html))


def add_legend(folium_map: folium.Map, max_speed: float, jinja_env: jinja2.Environment) -> None:
    template = jinja_env.get_template('speed_legend_template.html')
    legend_html = template.render(max_speed=max_speed)
    folium_map.get_root().html.add_child(folium.Element(legend_html))


def add_boat_legend(folium_map: folium.Map, names: List[str], jinja_env: jinja2.Environment) -> None:
    colors = ['red', 'green', 'blue', 'orange', 'purple', 'brown', 'pink', 'yellow', 'cyan', 'magenta']
    template = jinja_env.get_template('boat_legend_template.html')
    legend_html = template.render(names=names, colors=colors)
    folium_map.get_root().html.add_child(folium.Element(legend_html))


def main():
    args = parse_arguments()
    gpx_files = args.files
    names = args.names

    env = Environment(loader=FileSystemLoader('.'))

    folium_map, all_tracks, max_speed, map_id = create_map(gpx_files, names, args.max_speed)
    add_animation(folium_map, all_tracks, env, args.title, map_id)

    add_legend(folium_map, max_speed, env)
    add_boat_legend(folium_map, names if names else [t['name'] for t in all_tracks], env)

    folium_map.save('boat_tracks.html')
    print('Map has been saved to boat_tracks.html')

if __name__ == "__main__":
    main()
