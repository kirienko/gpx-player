import gpxpy
import gpxpy.gpx
import folium
import json
import matplotlib.pyplot as plt


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
            if speed > 9:
                print(f"Warning: speed {speed} exceeds 15 kn at time {time1} (dt = {time_diff}s)")
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



def create_map(gpx_files):
    folium_map = folium.Map(location=[0, 0], zoom_start=12)

    folium.TileLayer('openstreetmap').add_to(folium_map)
    folium.TileLayer(
        tiles='https://tiles.openseamap.org/seamark/{z}/{x}/{y}.png',
        attr='OpenSeaMap',
        name='OpenSeaMap',
        overlay=True,
        control=True
    ).add_to(folium_map)

    all_points = []

    for gpx_file in gpx_files:
        points = parse_gpx(gpx_file)
        speeds = calculate_speeds(points)
        all_points.extend(zip(points, speeds))

        # filter out the points with the speed higher than 15 knots:
        all_points = [p for p in all_points if p[1] < 15]

    # Calculate map bounds
    latitudes = [p['lat'] for p, _ in all_points]
    longitudes = [p['lon'] for p, _ in all_points]
    folium_map.fit_bounds([[min(latitudes), min(longitudes)], [max(latitudes), max(longitudes)]])

    max_speed = max(s for _, s in all_points)

    for points in [all_points]:
        lat_lon = [(p['lat'], p['lon']) for p, _ in points]
        speeds = [s for _, s in points]
        times = [p['time'].strftime('%Y-%m-%d %H:%M:%S') for p, _ in points]
        for i in range(len(lat_lon) - 1):
            color = speed_to_color(speeds[i], max_speed)
            tooltip_content = f"Time: {times[i]} UTC<br>Speed: {speeds[i]:.2f} knots"
            folium.PolyLine(
                lat_lon[i:i + 2],
                color=color,
                weight=2.5,
                opacity=1,
                tooltip=folium.Tooltip(tooltip_content)
            ).add_to(folium_map)

    return folium_map, all_points


def add_animation(folium_map, all_points):
    gpx_points_data = json.dumps(
        [{'lat': p['lat'], 'lon': p['lon'], 'time': p['time'].strftime('%Y-%m-%d %H:%M:%S'), 'speed': s} for p, s in
         all_points]
    )

    animation_script = f"""
    <script>
    var gpx_points_data = {gpx_points_data};
    </script>
    <script src="animate_tracks.js"></script>
    """
    folium_map.get_root().html.add_child(folium.Element(animation_script))


def add_legend(folium_map, max_speed):
    legend_html = f"""
    <div style="
        position: fixed; 
        bottom: 50px; left: 50px; width: 250px; height: 90px; 
        background-color: white; z-index:9999; font-size:14px;
        border:2px solid grey; padding: 10px;
    ">
    <h5>Speed (knots)</h5>
    <div style="background: linear-gradient(to right, red, yellow, green); height: 20px;"></div>
    <div style="display: flex; justify-content: space-between;font-size:12px">
        <span>0</span>
        <span>{max_speed/2:.1f}</span>
        <span>{max_speed:.1f}</span>
    </div>
    </div>
    """
    folium_map.get_root().html.add_child(folium.Element(legend_html))


def main():
    gpx_files = [
        # 'data/hanskalbsand/Rund_Hanskalbsand_2021.gpx',
        # 'data/hanskalbsand/Rund_Hanskalbsand_2023_Andreas.gpx',
        # 'data/hanskalbsand/Gin_Sul_Rund_Hanskalbsand_Regatta.gpx',
        # 'data/Bahia_Training_8_2024.gpx'
    ]

    folium_map, all_points = create_map(gpx_files)
    add_animation(folium_map, all_points)

    max_speed = max(s for _, s in all_points)
    add_legend(folium_map, max_speed)

    folium_map.save('boat_tracks.html')
    print('Map has been saved to boat_tracks.html')


if __name__ == "__main__":
    main()
