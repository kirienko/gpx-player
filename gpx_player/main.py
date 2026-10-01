import argparse
import datetime as dt
from bisect import bisect_right
from math import atan2, degrees

import gpxpy
import matplotlib.animation as animation
import matplotlib.pyplot as plt
import pytz
from matplotlib.ticker import FuncFormatter, MultipleLocator

from gpx_player.utils import format_func, gen_arrow_head_marker, km_to_nm, slug, timedelta_to_hms


def _frame_metrics(points, baseline):
    times = [point[2] for point in points]
    distances = [0.0] * len(points)
    speeds = [0.0] * len(points)
    distance_nm = 0.0
    speed_knots = 0.0

    for index in range(1, len(points)):
        lat1, lon1, time1 = points[index - 1]
        lat2, lon2, time2 = points[index]
        elapsed_seconds = (time2 - time1).total_seconds()
        if elapsed_seconds > 0 and time2 > baseline:
            segment_km = gpxpy.geo.haversine_distance(lat1, lon1, lat2, lon2) / 1000
            included_start = max(time1, baseline)
            included_seconds = (time2 - included_start).total_seconds()
            segment_nm = km_to_nm(segment_km)
            distance_nm += segment_nm * included_seconds / elapsed_seconds
            speed_knots = segment_nm / elapsed_seconds * 3600
        else:
            speed_knots = 0.0
        distances[index] = distance_nm
        speeds[index] = speed_knots

    return times, distances, speeds


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

    # Parse the GPX files
    for filename in args.files:
        with open(filename, 'r') as gpx_file:
            gpx = gpxpy.parse(gpx_file)
        points = []
        for track in gpx.tracks:
            for segment in track.segments:
                for point in segment.points:
                    if point.time is None or point.time.tzinfo is None or point.time.utcoffset() is None:
                        parser.error(f'GPX point timestamps must be timezone-aware: {filename}')
                    points.append((point.latitude, point.longitude, point.time.astimezone(local_tz)))
        for previous, current in zip(points, points[1:]):
            if current[2] == previous[2]:
                parser.error(f'Duplicate timestamps in {filename}: {current[2].isoformat()}')
            if current[2] < previous[2]:
                parser.error(f'Decreasing timestamps in {filename}: {current[2].isoformat()}')
        if start_time:
            points = [(lat, lon, time) for (lat, lon, time) in points if time >= start_time]
        if end_time:
            points = [(lat, lon, time) for (lat, lon, time) in points if time <= end_time]
        if not points:
            parser.error(f'No points in the selected window: {filename}')
        points_list.append(points)

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

        lines = [ax.plot([], [], '-', linewidth='0.8', label=filename)[0]
                 for points, filename in zip(points_list, args.files)]

        marker, scale = gen_arrow_head_marker(0)
        markersize = 10
        heads = [ax.plot([], [], marker=marker, markersize=markersize, color=lines[i].get_color())[0]
                 for i, _ in enumerate(points_list)]
        for head in heads:
            head.set_visible(False)

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

        ax_dist = [ax.text(0.83, 0.95 - 0.03*i, '', fontsize=7, transform=ax.transAxes) for i in range(len(points_list))]
        ax_speed = [ax.text(0.93, 0.95 - 0.03*i, '', fontsize=7, transform=ax.transAxes) for i in range(len(points_list))]
        track_metrics = [
            _frame_metrics(points, race_start or points[0][2])
            for points in points_list
        ]

        # Update function for animation
        def update(current_time, points_list, track_metrics, lines, heads, time_text):
            for idx, (points, metrics, line, head) in enumerate(zip(points_list, track_metrics, lines, heads)):
                times, distances, speeds = metrics
                count = bisect_right(times, current_time)
                start_counter = max(0, count - 60) if race_start and current_time >= race_start else 0
                visible_points = points[start_counter:count]
                line.set_data([point[1] for point in visible_points],
                              [point[0] for point in visible_points])

                if count:
                    head.set_visible(True)
                    head.set_data([points[count - 1][1]], [points[count - 1][0]])
                    if count > 1:
                        y1, x1 = points[count - 2][1], points[count - 2][0]
                        y2, x2 = points[count - 1][1], points[count - 1][0]
                        theta = degrees(atan2(y2 - y1, x2 - x1))
                        marker, scale = gen_arrow_head_marker(90 - theta)
                        head.set_marker(marker)
                    else:
                        head.set_marker('o')
                else:
                    head.set_data([], [])
                    head.set_visible(False)
                    head.set_marker('o')

                ax_dist[idx].set_text(f'{distances[count - 1] if count else 0.0:.2f} nm')
                ax_speed[idx].set_text(f'{speeds[count - 1] if count else 0.0:.1f} kt')

            if race_start:
                diff_time = current_time - race_start
                if diff_time.total_seconds() < 0:
                    time_text.set_text(f"Time to start: {timedelta_to_hms(-diff_time)}")
                    time_text.set_color('red')
                else:
                    time_text.set_text(f"Time of the race: {timedelta_to_hms(diff_time)}")
                    time_text.set_color('black')
            else:
                time_text.set_text(f'Time: {current_time:%Y-%m-%d %H:%M:%S}')
            return [*lines, *heads, time_text, *ax_dist, *ax_speed]


        # Get common timeline
        # Flatten the list of points from all tracks
        flat_points = [point for points in points_list
                              for point in points]
        # Extract timestamps
        timestamps = [point[2] for point in flat_points]
        # Create a sorted set of unique timestamps
        timeline = set(timestamps)
        if race_start and race_start <= max(timestamps) and (start_time is None or race_start >= start_time):
            timeline.add(race_start)
        timeline = sorted(timeline)

        ax.legend(loc='lower right', fontsize=8)

        artists = [*lines, *heads, time_text, *ax_dist, *ax_speed]
        ani = animation.FuncAnimation(fig, update, frames=timeline,
                                      fargs=[points_list, track_metrics, lines, heads, time_text],
                                      init_func=lambda: artists, interval=25, blit=True)

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
