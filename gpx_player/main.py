import argparse
import datetime as dt
from math import atan2, degrees

import gpxpy
import matplotlib.animation as animation
import matplotlib.pyplot as plt
import pytz
from matplotlib.ticker import FuncFormatter, MultipleLocator

from gpx_player.utils import format_func, gen_arrow_head_marker, km_to_nm, slug, timedelta_to_hms
from gpx_player.track_metrics import DEFAULT_MAX_SPEED_KNOTS, edge_metrics


def _video_track_edges(points, segment_ids):
    track_points = [
        {
            'lat': point[0],
            'lon': point[1],
            'time': point[2],
            'segment_index': segment_ids[index] if segment_ids is not None else 0,
        }
        for index, point in enumerate(points)
    ]
    return edge_metrics(track_points, DEFAULT_MAX_SPEED_KNOTS)


def _visible_track_data(points, edges, start_index, end_index):
    if start_index >= end_index:
        return [], []
    visible = points[start_index:end_index]
    longitudes = [visible[0][1]]
    latitudes = [visible[0][0]]
    for index in range(start_index + 1, end_index):
        if edges[index - 1] is None:
            longitudes.append(float('nan'))
            latitudes.append(float('nan'))
        longitudes.append(points[index][1])
        latitudes.append(points[index][0])
    return longitudes, latitudes


def main(argv=None):
    """Render GPX tracks; return zero after a successful save."""
    # Define argument parser
    parser = argparse.ArgumentParser()
    parser.add_argument('files', nargs='+', help='GPX files to process')
    parser.add_argument('--title', '-t', help='The title of the video')
    parser.add_argument('--output', '-o', help='Output file path (default: slugified title with .gif or .mp4)')
    parser.add_argument('--start', '-s', type=lambda s: dt.datetime.strptime(s, '%Y-%m-%dT%H:%M:%S%z'), help='Start time (YYYY-MM-DDTHH:MM:SS%z)')
    parser.add_argument('--end', '-e', type=lambda s: dt.datetime.strptime(s, '%Y-%m-%dT%H:%M:%S%z'), help='End time (YYYY-MM-DDTHH:MM:SS%z)')
    parser.add_argument('--race_start', '-r', type=lambda s: dt.datetime.strptime(s, '%Y-%m-%dT%H:%M:%S%z'),
                        help='Race start time (YYYY-MM-DDTHH:MM:SS%z)')
    parser.add_argument('--names', '-n', nargs='+', help='Names of the participants')
    parser.add_argument('--marks', '-m', help='The file with the static marks to put onto the map. One pair of coordinates per line')
    parser.add_argument('--gif', '-g', action='store_true', help='Save as GIF moving picture instead of MP4')
    parser.add_argument('--timezone', '-tz', default='Europe/Berlin', help='Timezone to use for processing timestamps')
    args = parser.parse_args(argv)
    local_tz = pytz.timezone(args.timezone)

    start_time = args.start.astimezone(local_tz) if args.start else None
    end_time = args.end.astimezone(local_tz) if args.end else None
    race_start = args.race_start.astimezone(local_tz) if args.race_start else None

    points_list = []
    segment_ids_list = []

    # Parse the GPX files
    for filename in args.files:
        with open(filename, 'r') as gpx_file:
            gpx = gpxpy.parse(gpx_file)
        points = []
        segment_ids = []
        segment_index = 0
        for track in gpx.tracks:
            for segment in track.segments:
                # all timestamps show the local time from this point on:
                for point in segment.points:
                    points.append((point.latitude, point.longitude, point.time.astimezone(local_tz)))
                    segment_ids.append(segment_index)
                segment_index += 1
        if start_time:
            selected = [(point, index) for point, index in zip(points, segment_ids) if point[2] >= start_time]
            points = [point for point, _segment_id in selected]
            segment_ids = [segment_id for _point, segment_id in selected]
        if end_time:
            selected = [(point, index) for point, index in zip(points, segment_ids) if point[2] <= end_time]
            points = [point for point, _segment_id in selected]
            segment_ids = [segment_id for _point, segment_id in selected]
        if not points:
            parser.error(f'No points in the selected window: {filename}')
        points_list.append(points)
        segment_ids_list.append(segment_ids)

    track_edges = [
        _video_track_edges(points, segment_ids)
        for points, segment_ids in zip(points_list, segment_ids_list)
    ]

    title = args.title if args.title else ''

    # Initialize the figure and axis
    fig, ax = plt.subplots()
    try:
        ax.set_title(title)
        # Apply the custom formatter to the x and y axes
        ax.xaxis.set_major_formatter(FuncFormatter(format_func))
        ax.yaxis.set_major_formatter(FuncFormatter(format_func))
        ax.xaxis.set_major_locator(MultipleLocator(1/120))  # locator at every 1/60/2 degrees = 30"
        ax.yaxis.set_major_locator(MultipleLocator(1/360))  # locator at every 1/60/0 degrees = 10"
        ax.tick_params(axis='both', labelsize=5)

        margin = 0.001  # increase to zoom out
        lat_min = min(point[0] for point in [point for points in points_list for point in points]) - margin
        lat_max = max(point[0] for point in [point for points in points_list for point in points]) + margin
        lon_min = min(point[1] for point in [point for points in points_list for point in points]) - margin
        lon_max = max(point[1] for point in [point for points in points_list for point in points]) + margin

        ax.set_xlim(lon_min, lon_max)
        ax.set_ylim(lat_min, lat_max)

        # Initialize the plot with the first data
        lines = [ax.plot(points[0][1], points[0][0], '-', linewidth='0.8', label=filename)[0]
                 for points, filename in zip(points_list, args.files)]

        marker, scale = gen_arrow_head_marker(0)
        markersize = 10
        heads = [ax.plot(points[0][1], points[0][0], marker=marker, markersize=markersize, color=lines[i].get_color())[0]
                 for i, points in enumerate(points_list)]

        if args.names:
            for i, name in enumerate(args.names):
                lines[i].set_label(name)
                ax.text(0.7, 0.95 - 0.03*i,
                        name[:13]+'...' if len(name) > 13 else f'{name:>13}', transform=ax.transAxes,
                        fontsize=6)


        # Add time labels
        time_text = ax.text(0.30, 0.95, '', transform=ax.transAxes)

        # Static points
        if args.marks:
            with open(args.marks) as fd:
                marks = [line.strip().split(',') for line in fd.readlines()]
            for i, (lat, lon) in enumerate(marks, 1):
                ax.plot(float(lon), float(lat), marker='o', markersize=5, color='orange')

        # Initialize counters in number of input files
        ax_dist = [ax.text(0.83, 0.95 - 0.03*i, '', fontsize=7, transform=ax.transAxes) for i in range(len(points_list))]
        ax_speed = [ax.text(0.93, 0.95 - 0.03*i, '', fontsize=7, transform=ax.transAxes) for i in range(len(points_list))]
        counters = [0] * len(points_list)
        dist_counter = [0.0] * len(points_list)
        speeds = [None] * len(points_list)

        # Update function for animation
        def update(current_time, points_list, track_edges, lines, heads, time_text):
            # Only advance in points_list if their time is less than or equal to the current time
            # iterate over points in each file
            for idx, (points, edges, counter, line) in enumerate(zip(points_list, track_edges, counters, lines)):
                pre_start_counter = 0
                while counter < len(points) and points[counter][2] <= current_time:
                    if counter > 0:
                        edge = edges[counter - 1]
                        speeds[idx] = edge[2] if edge is not None else None
                        if race_start or start_time:
                            if points[counter][2] >= (race_start or start_time):
                                if edge is not None:
                                    dist_counter[idx] += edge[0] / 1000.0
                            elif points[counter][2] < (race_start or start_time):
                                pre_start_counter += 1
                    counter += 1
                counters[idx] = counter
                # Update lines
                if race_start:
                    try:
                        # `start_counter` = 0 before start
                        #                 = counter - 60 after start
                        start_counter = 0 if points[counter][2] < race_start else max(pre_start_counter, counter - 60)
                    except IndexError:
                        start_counter = counter - 60
                else:
                    start_counter = 0

                line_x, line_y = _visible_track_data(points, edges, start_counter, counter)
                line.set_data(line_x, line_y)
                if counter > 0:
                    # plot the marker
                    heads[idx].set_data([points[counter - 1][1]], [points[counter - 1][0]])
                # Calculate the marker rotation angle
                if counter > 1 and edges[counter - 2] is not None:
                    y1, x1 = points[counter - 2][1], points[counter - 2][0]
                    y2, x2 = points[counter - 1][1], points[counter - 1][0]
                    theta = degrees(atan2(y2 - y1, x2 - x1))
                    marker, scale = gen_arrow_head_marker(90 - theta)
                    heads[idx].set_marker(marker)
                else:
                    heads[idx].set_marker('o')

                # Update distance/speed table
                ax_dist[idx].set_text(f'{km_to_nm(dist_counter[idx]):.2f} nm')  # Update the displayed distance
                ax_speed[idx].set_text(f'{speeds[idx]:.1f} kt' if speeds[idx] is not None else '— kt')  # Update the displayed speed
                dist_counter[idx] = 0.0

                # Update time text
                if race_start:
                    diff_time = current_time - race_start
                    minutes = diff_time.total_seconds() / 60
                    if minutes < 0:
                        time_text.set_text(f"Time to start: {timedelta_to_hms(-diff_time)}")
                        time_text.set_color('red')
                    else:
                        time_text.set_text(f"Time of the race: {timedelta_to_hms(diff_time)}")
                        time_text.set_color('black')
                else:
                    time_text.set_text(f'Time: {points[counter-1][2]:%Y-%m-%d %H:%M:%S}' if counter > 0 else '')
            return [*lines, *heads, time_text, *ax_dist, *ax_speed]


        # Get common timeline
        # Flatten the list of points from all tracks
        flat_points = [point for points in points_list
                              for point in points]
        # Extract timestamps
        timestamps = [point[2] for point in flat_points]
        # Create a sorted set of unique timestamps
        timeline = sorted(set(timestamps))

        ax.legend(loc='lower right', fontsize=8)

        ani = animation.FuncAnimation(fig, update, frames=timeline,
                                      fargs=[points_list, track_edges, lines, heads, time_text],
                                      interval=25, blit=True)

        # # Save the animation as a movie
        output = args.output or f"{slug(title or 'untitled')}.{'gif' if args.gif else 'mp4'}"
        if args.gif:
            ani.save(output)
        else:
            ani.save(output, fps=10)

        plt.show()
    finally:
        plt.close(fig)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
