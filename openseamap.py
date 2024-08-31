import argparse
import json
import folium
import gpxpy
import gpxpy.gpx
import jinja2
import matplotlib.pyplot as plt
from jinja2 import Environment, FileSystemLoader
from typing import List, Tuple


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
        points = [
            {'lat': point.latitude, 'lon': point.longitude, 'time': point.time}
            for track in gpx.tracks
            for segment in track.segments
            for point in segment.points
        ]
    return points


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


def speed_to_color(speed: float, max_speed: float) -> str:
    norm_speed = min(speed / max_speed, 1.0)
    color = plt.cm.RdYlGn(norm_speed)
    return f"rgba({int(color[0] * 255)}, {int(color[1] * 255)}, {int(color[2] * 255)}, {color[3]})"


def create_map(gpx_files: List[str], names: List[str], max_speed: float) -> Tuple[folium.Map, List[List], float, str]:
    folium_map = folium.Map(location=[0, 0], zoom_start=12, control_scale=True, attributionControl=False)
    map_id = folium_map.get_name()

    folium.TileLayer('openstreetmap').add_to(folium_map)
    # Add OpenSeaMap layer directly to the map, not to the layer control
    folium.TileLayer(
        tiles='https://tiles.openseamap.org/seamark/{z}/{x}/{y}.png',
        attr='OpenSeaMap',
        name='OpenSeaMap',
        overlay=False,
        control=False  # Set control to `False` to exclude from layer control
    ).add_to(folium_map)

    all_tracks = []
    for gpx_file in gpx_files:
        points = parse_gpx(gpx_file)
        speeds = calculate_speeds(points, max_speed)
        all_tracks.append(list(zip(points, speeds)))

    max_speed = max(s for track in all_tracks for _, s in track)

    # Calculate map bounds
    latitudes = [p['lat'] for track in all_tracks for p, _ in track]
    longitudes = [p['lon'] for track in all_tracks for p, _ in track]
    folium_map.fit_bounds([[min(latitudes), min(longitudes)], [max(latitudes), max(longitudes)]])

    track_layers = []
    for i, track in enumerate(all_tracks):
        lat_lon = [(p['lat'], p['lon']) for p, _ in track]
        speeds = [s for _, s in track]
        times = [p['time'].strftime('%Y-%m-%d %H:%M:%S') for p, _ in track]
        name = names[i] if names and i < len(names) else gpx_files[i]

        track_layer = folium.FeatureGroup(name=name, show=True)
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
                  all_tracks: List[List],
                  jinja_env: jinja2.Environment,
                  title: str, map_id:str) -> None:
    gpx_points_data = []
    gpx_timestamps = sorted(set(point[0]['time'] for track in all_tracks for point in track))
    min_time, max_time = min(gpx_timestamps), max(gpx_timestamps)
    time_range = (max_time - min_time).total_seconds()

    animation_script = f"""
    <script>
    var gpx_points_data = {json.dumps(gpx_points_data)};
    var gpx_timestamps = {json.dumps([t.strftime('%Y-%m-%d %H:%M:%S') for t in gpx_timestamps])};
    var min_time = new Date('{min_time.strftime('%Y-%m-%dT%H:%M:%S')}').getTime();
    var max_time = new Date('{max_time.strftime('%Y-%m-%dT%H:%M:%S')}').getTime();
    var time_range = {time_range};
    var map_id = "{map_id}";
    document.title = "{title if title else 'GPX Player'}";
    </script>
    <script src="animate_tracks.js"></script>
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


def main():
    args = parse_arguments()
    gpx_files = args.files
    names = args.names

    env = Environment(loader=FileSystemLoader('.'))

    folium_map, all_tracks, max_speed, map_id = create_map(gpx_files, names, args.max_speed)
    add_animation(folium_map, all_tracks, env, args.title, map_id)

    add_legend(folium_map, max_speed, env)

    folium_map.save('boat_tracks.html')
    print('Map has been saved to boat_tracks.html')

if __name__ == "__main__":
    main()
