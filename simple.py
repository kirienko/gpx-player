import argparse
import gpxpy
import geopandas as gpd
from shapely.geometry import Point, LineString
import contextily as ctx
from contextily import Place
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import matplotlib.colors as mcolors


def parse_gpx(files):
    point_gdfs = []
    line_gdfs = []
    timeline = []

    for file_path in files:
        points = []
        lines = []
        previous_point = None

        with open(file_path, 'r') as gpx_file:
            gpx = gpxpy.parse(gpx_file)

            for track in gpx.tracks:
                for segment in track.segments:
                    for point in segment.points:
                        current_point = Point(point.longitude, point.latitude)
                        points.append({
                            'geometry': current_point,
                            'time': point.time
                        })

                        if previous_point:
                            line = LineString([previous_point, current_point])
                            lines.append({
                                'geometry': line,
                                'time': point.time
                            })

                        previous_point = current_point

                        if point.time:
                            timeline.append(point.time)

        if points:
            point_gdfs.append(gpd.GeoDataFrame(points))
        if lines:
            line_gdfs.append(gpd.GeoDataFrame(lines))

    timeline.sort()
    return point_gdfs, line_gdfs, timeline

def animate(i, point_gdfs, line_gdfs, timeline, ax, colors):
    current_time = timeline[i]
    ax.clear()

    for idx in range(len(point_gdfs)):
        line_subset = line_gdfs[idx][line_gdfs[idx]['time'] <= current_time].to_crs(epsg=3857)
        point_subset = point_gdfs[idx][point_gdfs[idx]['time'] <= current_time].to_crs(epsg=3857)

        line_subset.plot(ax=ax, linestyle='-', linewidth=1.5, color=colors[idx])
        point_subset.plot(ax=ax, markersize=5, color=colors[idx])

    ctx.add_basemap(ax, source=ctx.providers.OpenStreetMap.Mapnik, zoom=19)
    
def get_borders(geodata: gpd.GeoDataFrame):
    margins = 0.05 
    x_min = min([gdf.geometry.x.min() for gdf in geodata])
    x_max = max([gdf.geometry.x.max() for gdf in geodata])
    x_margin = (x_max - x_min) * margins
    y_min = min([gdf.geometry.y.min() for gdf in geodata])
    y_max = max([gdf.geometry.y.max() for gdf in geodata])
    y_margin = (y_max - y_min) * margins
    # print(x_min - x_margin, x_max + x_margin, y_min - y_margin, y_max + y_margin)
    return (x_min - x_margin, x_max + x_margin), (y_min - y_margin, y_max + y_margin) 

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Animate tracks from multiple GPX files using gpxpy, GeoPandas, and contextily.")
    parser.add_argument("file_paths", nargs='+', help="Paths to the GPX files")

    args = parser.parse_args()

    point_gdfs, line_gdfs, timeline = parse_gpx(args.file_paths)
    
    for point_gdf in point_gdfs:
        point_gdf.crs = "EPSG:4326"
    for line_gdf in line_gdfs:
        line_gdf.crs = "EPSG:4326"
    # Define colors for each GPX file
    all_colors = list(mcolors.CSS4_COLORS.keys())
    colors = all_colors[:len(point_gdfs)]

    fig, ax = plt.subplots()
    x_limits, y_limits = get_borders(point_gdfs)
    ax.set_xlim(*x_limits)
    ax.set_ylim(*y_limits)

    ani = animation.FuncAnimation(fig, animate, frames=len(timeline),
                                  fargs=(point_gdfs, line_gdfs, timeline, ax, colors),
                                  interval=25)
    plt.show()
    