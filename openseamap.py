import argparse
import json

import folium
import gpxpy
import gpxpy.gpx
import matplotlib.pyplot as plt
from jinja2 import Environment, FileSystemLoader

# Define argument parser
parser = argparse.ArgumentParser()
parser.add_argument('--files', nargs='+', help='GPX files to process')
parser.add_argument('--names', '-n', nargs='+', help='Names of the participants')
parser.add_argument('--max-speed', '-ms', nargs='+', help='Maximum speed (default: 12 knots)', default=12, dest='max_speed')
parser.add_argument('--title', '-t', help='The title of the page', dest='title', default=None)
args = parser.parse_args()


def parse_gpx(file_path):
    with open(file_path, 'r') as gpx_file:
        gpx = gpxpy.parse(gpx_file)
        points = []
        for track in gpx.tracks:
            for segment in track.segments:
                for point in segment.points:
                    points.append({
                        'lat': point.latitude,
                        'lon': point.longitude,
                        'time': point.time
                    })
        return points


def calculate_speeds(points):
    speeds = []
    for i in range(1, len(points)):
        lat1, lon1, time1 = points[i - 1]['lat'], points[i - 1]['lon'], points[i - 1]['time']
        lat2, lon2, time2 = points[i]['lat'], points[i]['lon'], points[i]['time']
        distance = gpxpy.geo.haversine_distance(lat1, lon1, lat2, lon2)
        time_diff = (time2 - time1).total_seconds()
        if time_diff > 0:
            speed = distance / time_diff * 1.94384  # Convert m/s to knots
            if speed > args.max_speed:
                print(f"Warning: speed {speed} exceeds {args.max_speed} kn at time {time1} (dt = {time_diff}s)")
                speed = 0.
            speeds.append(speed)
        else:
            speeds.append(0)
    print(f"Max speed: {max(speeds)}")
    return speeds


def speed_to_color(speed, max_speed):
    norm_speed = speed / max_speed
    color = plt.cm.RdYlGn(norm_speed)[:4]  # Use RGBA for opacity
    return "rgba({},{},{},{})".format(int(color[0] * 255), int(color[1] * 255), int(color[2] * 255), color[3])


def create_map(gpx_files, names=None):
    folium_map = folium.Map(location=[0, 0], zoom_start=12)

    folium.TileLayer('openstreetmap').add_to(folium_map)
    folium.TileLayer(
        tiles='https://tiles.openseamap.org/seamark/{z}/{x}/{y}.png',
        attr='OpenSeaMap',
        name='OpenSeaMap',
        overlay=True,
        control=True
    ).add_to(folium_map)

    all_tracks = []

    for gpx_file in gpx_files:
        points = parse_gpx(gpx_file)
        speeds = calculate_speeds(points)
        all_tracks.append(list(zip(points, speeds)))

    # Calculate map bounds
    latitudes = [p['lat'] for track in all_tracks for p, _ in track]
    longitudes = [p['lon'] for track in all_tracks for p, _ in track]
    folium_map.fit_bounds([[min(latitudes), min(longitudes)], [max(latitudes), max(longitudes)]])

    for i, track in enumerate(all_tracks):
        lat_lon = [(p['lat'], p['lon']) for p, _ in track]
        speeds = [s for _, s in track]
        times = [p['time'].strftime('%Y-%m-%d %H:%M:%S') for p, _ in track]
        name = names[i] if names and i < len(names) else gpx_files[i]
        max_speed = max(speeds)
        for j in range(len(lat_lon) - 1):
            color = speed_to_color(speeds[j], max_speed)
            tooltip_content = f"Name: {name}<br>Time: {times[j]} UTC<br>Speed: {speeds[j]:.2f} knots"
            folium.PolyLine(
                lat_lon[j:j + 2],
                color=color,
                weight=2.5,
                opacity=1,
                tooltip=folium.Tooltip(tooltip_content)
            ).add_to(folium_map)

    return folium_map, all_tracks


def add_animation(folium_map, all_tracks, jinja_env):
    gpx_points_data = []
    for track in all_tracks:
        gpx_points_data.extend([{'lat': p['lat'], 'lon': p['lon'],
                                 'time': p['time'].strftime('%Y-%m-%d %H:%M:%S'),
                                 'speed': s}
                                for p, s in track])

    animation_script = f"""
    <script>
    var gpx_points_data = {json.dumps(gpx_points_data)};
    document.title = "{args.title if args.title else 'GPX Player'}";
    </script>
    <script src="animate_tracks.js"></script>
    """
    folium_map.get_root().html.add_child(folium.Element(animation_script))

    # Add the title to the body of the HTML
    if args.title is not None:
        # Add the header with custom styles
        template = jinja_env.get_template('header_template.html')
        header_html = template.render(title=args.title)
        folium_map.get_root().html.add_child(folium.Element(header_html))


def add_legend(folium_map, max_speed, jinja_env):
    template = jinja_env.get_template('speed_legend_template.html')
    legend_html = template.render(max_speed=max_speed)
    folium_map.get_root().html.add_child(folium.Element(legend_html))


def main():
    gpx_files = args.files
    names = args.names

    env = Environment(loader=FileSystemLoader('.'))

    folium_map, all_tracks = create_map(gpx_files, names)
    add_animation(folium_map, all_tracks, env)

    max_speed = max(s for track in all_tracks for _, s in track)
    add_legend(folium_map, max_speed, env)

    folium_map.save('boat_tracks.html')
    print('Map has been saved to boat_tracks.html')


if __name__ == "__main__":
    main()
